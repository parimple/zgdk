"""Info cog."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from datasources.models import Role
from datasources.queries import (
    ChannelPermissionQueries,
    InviteQueries,
    MemberQueries,
    NotificationLogQueries,
    RoleQueries,
)
from utils.currency import CURRENCY_UNIT
from utils.decorators import is_zagadka_owner
from utils.permissions import is_admin
from utils.premium import PremiumManager
from utils.refund import calculate_refund
from utils.team_manager import TeamManager

logger = logging.getLogger(__name__)


async def remove_premium_role_mod_permissions(session, bot, member_id: int):
    """
    Remove moderator permissions granted by a user and delete their teams.

    This function is called both when a premium role is manually sold and
    when a premium role automatically expires.

    :param session: Database session
    :param bot: Bot instance
    :param member_id: User ID
    """
    logger.info(f"Removing premium role-related privileges for user {member_id}")

    # 1. Usuń uprawnienia moderatorów kanałów głosowych
    await ChannelPermissionQueries.remove_mod_permissions_granted_by_member(session, member_id)
    logger.info(f"Voice channel permissions granted by {member_id} removed")

    # 2. Usuń teamy należące do tego użytkownika - używamy bezpieczniejszej metody SQL
    deleted_teams = await TeamManager.delete_user_teams_by_sql(session, bot, member_id)
    if deleted_teams > 0:
        logger.info(f"Deleted {deleted_teams} teams owned by {member_id} using SQL method")

    return deleted_teams


class InfoCog(commands.Cog):
    """Info cog."""

    def __init__(self, bot):
        """Info cog."""
        self.bot = bot
        # Remove default help command
        self.bot.remove_command("help")
        # Get team symbol from config
        team_config = self.bot.config.get("team", {})
        self.team_symbol = team_config.get("symbol", "☫")

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: info.py Loaded")

    @commands.hybrid_command(
        name="invites", description="Wyświetla listę zaproszeń z możliwością sortowania."
    )
    @is_admin()
    @app_commands.describe(
        sort_by="Pole do sortowania (uses, created_at, last_used)",
        order="Kolejność sortowania (desc lub asc)",
        target="Użytkownik, którego zaproszenia chcesz wyświetlić",
    )
    async def list_invites(
        self,
        ctx: commands.Context,
        sort_by: Optional[Literal["uses", "created_at", "last_used"]] = "last_used",
        order: Optional[Literal["desc", "asc"]] = "desc",
        target: Optional[discord.Member] = None,
    ):
        """
        Wyświetla listę zaproszeń z możliwością sortowania.

        :param ctx: Kontekst komendy
        :param sort_by: Pole do sortowania (uses, created_at lub last_used)
        :param order: Kolejność sortowania (desc lub asc)
        :param target: Użytkownik, którego zaproszenia chcesz wyświetlić
        """
        discord_invites = await ctx.guild.invites()

        async with self.bot.get_db() as session:
            db_invites = await InviteQueries.get_all_invites(session)

        db_invites_dict = {invite.id: invite for invite in db_invites}

        combined_invites = [
            InviteInfo(discord_invite, db_invites_dict.get(discord_invite.code))
            for discord_invite in discord_invites
        ]

        if target:
            combined_invites = [
                inv for inv in combined_invites if inv.inviter and inv.inviter.id == target.id
            ]

        view = InviteListView(self.bot, combined_invites, sort_by, order, target)
        view.sort_invites()
        await ctx.send(embed=view.create_embed(), view=view)

    @commands.hybrid_command(name="sync", description="Syncs commands.")
    @is_admin()
    async def sync(self, ctx) -> None:
        """Syncs the current guild."""
        synced = await ctx.bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} commands")

    @commands.hybrid_command(name="ping", description="Sends Pong!")
    async def ping(self, ctx: commands.Context):
        """Sends Pong! when ping is used as a command."""
        logging.info("ping")
        await ctx.reply("pong")

    @commands.hybrid_command(name="guildinfo", description="Displays the current guild.")
    @is_admin()
    async def guild_info(self, ctx: commands.Context):
        """Sends the current guild when guildinfo is used as a command."""
        guild = self.bot.guild
        if isinstance(guild, discord.Guild):
            await ctx.send(f"Current guild: {guild.name} (ID: {guild.id})")
        else:
            await ctx.send(f"Guild ID: {guild}")

    @commands.hybrid_command(
        name="profile", aliases=["p"], description="Wyświetla profil użytkownika."
    )
    async def profile(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Sends user profile when profile is used as a command."""
        if not member:
            member = ctx.author

        if not isinstance(member, discord.Member):
            member = self.bot.guild.get_member(member.id)
            if not member:
                raise commands.UserInputError("Nie można znaleźć członka na tym serwerze.")

        roles = [role for role in member.roles if role.name != "@everyone"]

        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, member.id)
            premium_roles = await RoleQueries.get_member_premium_roles(session, member.id)
            bypass_until = await MemberQueries.get_voice_bypass_status(session, member.id)

            # Get owned teams from database
            owned_teams_query = await session.execute(
                select(Role).where((Role.role_type == "team") & (Role.name == str(member.id)))
            )
            owned_teams = owned_teams_query.scalars().all()

            # Get teams from database
            teams_query = await session.execute(
                select(Role).where((Role.role_type == "team") & (Role.name == str(member.id)))
            )
            teams = teams_query.scalars().all()

            colors_query = await session.execute(
                select(Role).where((Role.role_type == "color") & (Role.name == str(member.id)))
            )
            colors = colors_query.scalars().all()

        current_time = datetime.now(timezone.utc)
        logger.info(f"Current time: {current_time}")
        for member_role, role in premium_roles:
            logger.info(
                f"Role {role.id} expiration: {member_role.expiration_date}, Is expired: {member_role.expiration_date <= current_time}"
            )

        embed = discord.Embed(
            title=f"{member}",
            color=member.color,
            timestamp=ctx.message.created_at,
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID:", value=member.id)
        embed.add_field(name="Nazwa na serwerze:", value=member.display_name)
        embed.add_field(name="Saldo G:", value=f"{db_member.wallet_balance}{CURRENCY_UNIT}")

        # Add bypass time info if active
        if bypass_until and bypass_until > current_time:
            time_left = bypass_until - current_time
            # Convert to hours and round down to nearest integer
            hours = int(time_left.total_seconds() // 3600)
            embed.add_field(name="Saldo T:", value=f"{hours}T")

        embed.add_field(name="Konto od:", value=discord.utils.format_dt(member.created_at, "D"))
        embed.add_field(
            name="Dołączył:",
            value=discord.utils.format_dt(member.joined_at, "D")
            if member.joined_at
            else "Brak danych",
        )

        if premium_roles:
            premium_role = premium_roles[0][1]
            roles = [role for role in roles if role.id != premium_role.id]

        if roles:
            embed.add_field(name="Role:", value=" ".join([role.mention for role in roles]))

        if premium_roles:
            PremiumManager.add_premium_roles_to_embed(ctx, embed, premium_roles)

        # Add team ownership information right after premium roles
        if owned_teams:
            team_roles = []
            for team in owned_teams:
                team_role = ctx.guild.get_role(team.id)
                if team_role:
                    team_roles.append(team_role.mention)
            if team_roles:
                embed.add_field(name="Właściciel Drużyny:", value=" ".join(team_roles), inline=True)

        if db_member.first_inviter_id is not None:
            first_inviter = self.bot.get_user(db_member.first_inviter_id)
            if first_inviter is not None:
                embed.add_field(name="Werbownik:", value=first_inviter.name)

        if member.banner:
            embed.set_image(url=member.banner.url)

        view = ProfileView(self.bot, member, premium_roles, ctx.author)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="roles", description="Lists all roles in the database")
    @is_admin()
    async def all_roles(self, ctx: commands.Context):
        """Fetch and display all roles in the database."""
        async with self.bot.get_db() as session:
            roles = await RoleQueries.get_all_roles(session)

        embed = discord.Embed(title="All Roles")
        for role in roles:
            embed.add_field(
                name=f"Role ID: {role.id}",
                value=f"Role Name: {role.name}\nRole Type: {role.role_type}",
                inline=False,
            )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="bypass", description="Zarządza czasem bypassa (T) użytkownika.")
    @is_admin()
    async def bypass(
        self, ctx: commands.Context, member: discord.Member, hours: Optional[int] = None
    ):
        """
        Zarządza czasem bypassa (T) użytkownika.
        :param member: Użytkownik, któremu chcemy zmienić czas bypassa
        :param hours: Liczba godzin bypassa. Jeśli nie podano, bypass zostanie usunięty.
        """
        current_time = datetime.now(timezone.utc)

        async with self.bot.get_db() as session:
            if hours is None or hours == 0:
                # Zerowanie bypassa
                await MemberQueries.set_voice_bypass_status(session, member.id, None)
                await ctx.send(f"Usunięto bypass dla {member.mention}.")
            else:
                # Dodawanie nowego bypassa
                bypass_until = current_time + timedelta(hours=hours)
                await MemberQueries.set_voice_bypass_status(session, member.id, bypass_until)
                await ctx.send(f"Ustawiono bypass dla {member.mention} na {hours}T.")

    @commands.hybrid_command(
        name="pomoc", aliases=["help"], description="Wyświetla listę dostępnych komend"
    )
    @is_admin()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def help_command(self, ctx: commands.Context):
        """Wyświetla listę dostępnych komend"""
        embed = discord.Embed(
            title="Lista dostępnych komend",
            color=discord.Color.blue(),
            description="Poniżej znajdziesz listę dostępnych komend:",
        )

        # Komendy głosowe
        voice_commands = (
            "**Komendy głosowe:**\n"
            "• `speak` - Zarządzanie uprawnieniami do mówienia\n"
            "• `connect` - Zarządzanie uprawnieniami do połączenia\n"
            "• `view` - Zarządzanie widocznością kanału\n"
            "• `text` - Zarządzanie uprawnieniami do pisania\n"
            "• `live` - Zarządzanie uprawnieniami do streamowania\n"
            "• `mod` - Zarządzanie moderatorami kanału\n"
            "• `limit` - Ustawianie limitu użytkowników\n"
            "• `voicechat` - Informacje o kanale\n"
            "• `reset` - Reset uprawnień kanału\n"
            "• `autokick` - Zarządzanie autokickiem"
        )
        embed.add_field(name="\u200b", value=voice_commands, inline=False)

        # Komendy informacyjne
        info_commands = (
            "**Komendy informacyjne:**\n"
            "• `profile` - Wyświetla profil użytkownika\n"
            "• `shop` - Wyświetla sklep z rolami\n"
            "• `games` - Lista aktywnych gier\n"
            "• `bump` - Status bumpów"
        )
        embed.add_field(name="\u200b", value=info_commands, inline=False)

        # Stopka z informacją o prefixie
        embed.set_footer(
            text=f"Prefix: {self.bot.config['prefix']} | Możesz też używać komend slash (/)"
        )

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="games", description="Wyświetla listę aktywnych gier na serwerze wraz z liczbą graczy."
    )
    async def games(self, ctx: commands.Context):
        """Wyświetla listę gier, w które aktualnie grają członkowie serwera."""
        # Send initial message
        loading_embed = discord.Embed(
            title="Ładowanie...",
            description="Trwa zbieranie informacji o grach...",
            color=discord.Color.blue(),
        )
        message = await ctx.send(embed=loading_embed)

        games_data = {}
        online_members = [m for m in ctx.guild.members if m.status != discord.Status.offline]
        total_online = len(online_members)

        for member in online_members:
            if member.activities:
                for activity in member.activities:
                    if activity.type == discord.ActivityType.playing:
                        game_name = activity.name
                        games_data[game_name] = games_data.get(game_name, 0) + 1

        if not games_data:
            await message.edit(content="Aktualnie nikt nie gra w żadne gry.", embed=None)
            return

        # Sort games by player count (descending)
        sorted_games = sorted(games_data.items(), key=lambda x: x[1], reverse=True)

        # Split into chunks of 15 games to avoid embed size limit
        games_per_page = 15
        total_pages = (len(sorted_games) + games_per_page - 1) // games_per_page
        current_page = 1

        def create_games_embed(page):
            start_idx = (page - 1) * games_per_page
            end_idx = start_idx + games_per_page
            current_games = sorted_games[start_idx:end_idx]

            embed = discord.Embed(title="Aktywne gry na serwerze")

            # Calculate total players in games
            total_players = sum(count for _, count in current_games)

            for game_name, player_count in current_games:
                percentage = (player_count / total_online) * 100
                embed.add_field(
                    name=game_name,
                    value=f"Graczy: {player_count} ({percentage:.1f}%)",
                    inline=False,
                )

            embed.set_footer(
                text=f"Strona {page}/{total_pages} | {total_online} użytkowników online"
            )
            return embed

        # Create view for pagination
        class GamesPaginator(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                self.page = 1

            @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
            async def previous_page(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                if self.page > 1:
                    self.page -= 1
                    await interaction.response.edit_message(embed=create_games_embed(self.page))

            @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
            async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.page < total_pages:
                    self.page += 1
                    await interaction.response.edit_message(embed=create_games_embed(self.page))

            async def on_timeout(self):
                try:
                    for item in self.children:
                        item.disabled = True
                    await message.edit(view=self)
                except:
                    pass

        view = GamesPaginator() if total_pages > 1 else None
        await message.edit(embed=create_games_embed(1), view=view)

    @commands.command(name="addt", description="Dodaje czas T użytkownikowi.")
    @is_admin()
    async def add_t(self, ctx: commands.Context, user: discord.User, hours: int):
        """Add T time to a user."""
        async with self.bot.get_db() as session:
            await MemberQueries.extend_voice_bypass(session, user.id, timedelta(hours=hours))
            await session.commit()

        await ctx.reply(f"Dodano {hours}T do konta {user.mention}.")

    @commands.command(name="checkroles", description="Sprawdza role użytkownika w logach.")
    @is_admin()
    async def check_roles(self, ctx: commands.Context, user: discord.Member):
        """Sprawdza role użytkownika i wypisuje je w logach."""
        roles = user.roles
        role_names = [r.name for r in roles]
        role_ids = [r.id for r in roles]

        logger.info(f"[CHECK_ROLES] Role użytkownika {user.display_name} ({user.id}):")
        logger.info(f"[CHECK_ROLES] Nazwy ról: {role_names}")
        logger.info(f"[CHECK_ROLES] ID ról: {role_ids}")

        # Sprawdza też w bazie danych
        async with self.bot.get_db() as session:
            premium_roles = await RoleQueries.get_member_premium_roles(session, user.id)
            logger.info(f"[CHECK_ROLES] Role premium w bazie danych dla {user.display_name}:")
            for member_role, role in premium_roles:
                logger.info(
                    f"[CHECK_ROLES] Rola {role.name} (ID: {role.id}), wygasa: {member_role.expiration_date}"
                )

                # Sprawdź czy użytkownik ma tę rolę na Discord
                has_role = role.id in role_ids
                logger.info(
                    f"[CHECK_ROLES] Czy użytkownik ma rolę {role.name} na Discord: {has_role}"
                )

        await ctx.reply(
            f"Informacje o rolach użytkownika {user.mention} zostały zapisane w logach."
        )

    @commands.command(
        name="checkstatus", description="Sprawdza status premium i teamy użytkownika."
    )
    @is_admin()
    async def check_status(self, ctx, member: discord.Member):
        """Sprawdza status premium i teamy użytkownika."""
        logger.info(
            f"Checking premium status and teams for {member.display_name} (ID: {member.id})"
        )

        premium_roles = []
        team_roles = []
        team_channels = []

        # 1. Sprawdź role Discord
        for role in member.roles:
            for premium_config in self.bot.config["premium_roles"]:
                if role.name == premium_config["name"]:
                    premium_roles.append(role)
                    break

            # Sprawdź czy to rola teamu
            if (
                role.name.startswith(self.team_symbol)
                and len(role.name) > len(self.team_symbol)
                and role.name[len(self.team_symbol)] == " "
            ):
                team_roles.append(role)

        # 2. Sprawdź kanały z topikiem zawierającym ID użytkownika
        for channel in ctx.guild.channels:
            if hasattr(channel, "topic") and channel.topic and str(member.id) in channel.topic:
                if "Team Channel" in channel.topic or (
                    len(channel.topic.split()) >= 2 and channel.topic.split()[0] == str(member.id)
                ):
                    team_channels.append(channel)

        # 3. Sprawdź role w bazie danych
        roles_db_info = []
        teams_db_info = []

        async with self.bot.get_db() as session:
            # Pobierz role premium z bazy danych
            premium_roles_db = await RoleQueries.get_member_premium_roles(session, member.id)
            for member_role, role in premium_roles_db:
                expiry = (
                    member_role.expiration_date.strftime("%d.%m.%Y %H:%M")
                    if member_role.expiration_date
                    else "bez wygaśnięcia"
                )
                roles_db_info.append(f"Rola: {role.name}, ID: {role.id}, wygasa: {expiry}")

            # Pobierz teamy z bazy danych
            teams_query = await session.execute(
                select(Role).where((Role.role_type == "team") & (Role.name == str(member.id)))
            )
            teams = teams_query.scalars().all()

            for team in teams:
                teams_db_info.append(f"Team ID: {team.id}")

        # 4. Przygotuj i wyślij embed z informacjami
        embed = discord.Embed(
            title=f"Status użytkownika {member.display_name}", color=discord.Color.blue()
        )
        embed.add_field(
            name="Role premium (Discord)",
            value="\n".join([f"{role.name} (ID: {role.id})" for role in premium_roles]) or "Brak",
            inline=False,
        )
        embed.add_field(
            name="Role premium (baza danych)",
            value="\n".join(roles_db_info) or "Brak",
            inline=False,
        )
        embed.add_field(
            name="Role teamów (Discord)",
            value="\n".join([f"{role.name} (ID: {role.id})" for role in team_roles]) or "Brak",
            inline=False,
        )
        embed.add_field(
            name="Kanały teamów",
            value="\n".join([f"{channel.name} (ID: {channel.id})" for channel in team_channels])
            or "Brak",
            inline=False,
        )
        embed.add_field(
            name="Teamy (baza danych)", value="\n".join(teams_db_info) or "Brak", inline=False
        )

        await ctx.send(embed=embed)
        logger.info(f"Status check completed for {member.display_name}")

        # 5. Jeśli wykryto niespójności, zasugeruj rozwiązania
        inconsistencies = []

        # Sprawdź, czy użytkownik ma teamy ale nie ma roli premium
        if (team_roles or team_channels or teams_db_info) and not premium_roles:
            inconsistencies.append("Użytkownik ma teamy, ale nie ma aktywnej roli premium.")

        # Sprawdź, czy są teamy w bazie danych, ale nie ma ich na Discord
        if teams_db_info and not team_roles:
            inconsistencies.append(
                "Użytkownik ma teamy w bazie danych, ale brakuje ról na Discord."
            )

        # Sprawdź, czy są role teamów na Discord, ale nie ma ich w bazie danych
        if team_roles and not teams_db_info:
            inconsistencies.append(
                "Użytkownik ma role teamów na Discord, ale brakuje ich w bazie danych."
            )

        if inconsistencies:
            embed = discord.Embed(
                title="⚠️ Wykryto niespójności",
                description="Wykryto niespójności w statusie użytkownika:",
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="Problemy",
                value="\n".join([f"- {issue}" for issue in inconsistencies]),
                inline=False,
            )
            embed.add_field(
                name="Sugerowane działania",
                value=(
                    f"- Możesz użyć komendy `,team admin_delete @{member.display_name}` aby usunąć teamy użytkownika\n"
                    f"- Możesz ręcznie usunąć role teamów użytkownika z serwera Discord\n"
                    f"- Możesz sprawdzić role premium użytkownika używając komendy `,checkroles @{member.display_name}`"
                ),
                inline=False,
            )
            await ctx.send(embed=embed)


class ProfileView(discord.ui.View):
    """View for profile command."""

    def __init__(self, bot, member: discord.Member, premium_roles, viewer: discord.Member):
        super().__init__()
        self.bot = bot
        self.member = member
        self.premium_roles = premium_roles
        self.viewer = viewer

        # Add buttons based on conditions
        if viewer.id == member.id:
            self.add_item(BuyRoleButton(bot, member, viewer))
            if premium_roles:
                self.add_item(SellRoleButton(bot, premium_roles, member.id))


class BuyRoleButton(discord.ui.Button):
    """Button for buying roles."""

    def __init__(self, bot, member, viewer, **kwargs):
        super().__init__(style=discord.ButtonStyle.green, label="Kup rangę", emoji="🛒", **kwargs)
        self.bot = bot
        self.member = member
        self.viewer = viewer

    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        ctx = await self.bot.get_context(interaction.message)
        ctx.author = interaction.user
        await ctx.invoke(self.bot.get_command("shop"))


class SellRoleButton(discord.ui.Button):
    """Button for selling roles."""

    def __init__(self, bot, premium_roles, owner_id: int, **kwargs):
        super().__init__(style=discord.ButtonStyle.red, label="Sprzedaj rangę", emoji="💰", **kwargs)
        self.bot = bot
        self.premium_roles = premium_roles
        self.owner_id = owner_id
        self.is_selling = False

    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        # Verify if the user is the owner of the role
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Nie możesz sprzedać cudzej roli.", ephemeral=True
            )
            return

        if self.is_selling:
            await interaction.response.send_message(
                "Transakcja jest już w toku. Poczekaj na jej zakończenie.", ephemeral=True
            )
            return

        self.is_selling = True
        try:
            member_role, role = self.premium_roles[0]

            # Verify if user still has the role by checking role IDs
            user_role_ids = [r.id for r in interaction.user.roles]
            if role.id not in user_role_ids:
                await interaction.response.send_message(
                    "Nie posiadasz już tej roli.", ephemeral=True
                )
                return

            # Get role price from config
            role_price = next(
                (r["price"] for r in self.bot.config["premium_roles"] if r["name"] == role.name),
                None,
            )
            if role_price is None:
                await interaction.response.send_message(
                    "Nie można znaleźć ceny roli. Skontaktuj się z administracją.", ephemeral=True
                )
                return

            refund_amount = calculate_refund(member_role.expiration_date, role_price, role.name)

            embed = discord.Embed(
                title="Sprzedaż rangi",
                description=f"Czy na pewno chcesz sprzedać rangę {role.name}?\n"
                f"Otrzymasz zwrot w wysokości {refund_amount}{CURRENCY_UNIT}.",
                color=interaction.user.color
                if interaction.user.color.value != 0
                else discord.Color.red(),
            )

            # Create a new view with a timeout
            class ConfirmView(discord.ui.View):
                """View for confirming role sale."""

                def __init__(
                    self,
                    bot,
                    owner_id: int,
                    role: discord.Role,
                    refund_amount: int,
                    interaction: discord.Interaction,
                ):
                    super().__init__(timeout=60.0)
                    self.bot = bot
                    self.owner_id = owner_id
                    self.role = role
                    self.refund_amount = refund_amount
                    self.original_interaction = interaction
                    self.value = None
                    self.message = None

                async def on_timeout(self):
                    if self.message:
                        for item in self.children:
                            item.disabled = True
                        try:
                            await self.message.edit(
                                content="Czas na potwierdzenie minął.", embed=None, view=self
                            )
                        except:
                            pass

                @discord.ui.button(label="Potwierdź", style=discord.ButtonStyle.danger)
                async def confirm(
                    self, confirm_interaction: discord.Interaction, button: discord.ui.Button
                ):
                    # Wyłączamy przyciski
                    for item in self.children:
                        item.disabled = True

                    try:
                        await confirm_interaction.response.defer()
                        logger.info(
                            f"[SELL_ROLE] Interakcja defer wykonany pomyślnie dla użytkownika {confirm_interaction.user.display_name}"
                        )
                    except Exception as e:
                        # Interakcja może być już wykonana
                        logger.warning(f"[SELL_ROLE] Nie można wykonać defer: {e}")
                        pass

                    if confirm_interaction.user.id != self.original_interaction.user.id:
                        try:
                            await confirm_interaction.followup.send(
                                "Nie możesz potwierdzić tej transakcji.", ephemeral=True
                            )
                        except:
                            pass
                        return

                    # 1. Zapisujemy dane przed jakimikolwiek modyfikacjami w bazie
                    member_id = self.original_interaction.user.id
                    role_id = self.role.id
                    role_name = self.role.name
                    refund_amount = self.refund_amount

                    logger.info(
                        f"[SELL_ROLE] Rozpoczęto sprzedaż roli {role_name} (ID: {role_id}) przez użytkownika {confirm_interaction.user.display_name} (ID: {member_id})"
                    )

                    # 2. Sprawdź, czy użytkownik ma rolę na Discord - z dodatkowym fetching dla pewności
                    logger.info(
                        f"[SELL_ROLE] Oczekiwanie 2 sekundy na synchronizację API Discord..."
                    )
                    await asyncio.sleep(2)

                    member = confirm_interaction.guild.get_member(member_id)

                    # Logujemy wszystkie role użytkownika, aby zobaczyć co faktycznie ma
                    user_roles = []
                    user_role_ids = []

                    if member:
                        user_roles = [r.name for r in member.roles]
                        user_role_ids = [r.id for r in member.roles]
                        logger.info(f"[SELL_ROLE] Role użytkownika z cache: {user_roles}")
                        logger.info(f"[SELL_ROLE] ID ról użytkownika z cache: {user_role_ids}")
                        logger.info(f"[SELL_ROLE] ID szukanej roli: {role_id}")

                    # Jeśli nie znaleziono członka lub nie wykryto roli, spróbuj pobrać go jeszcze raz bezpośrednio z API
                    has_role = False
                    if member and self.role in member.roles:
                        has_role = True
                        logger.info(
                            f"[SELL_ROLE] Znaleziono rolę {role_name} w cache Discord dla {member.display_name}"
                        )
                    else:
                        logger.warning(
                            f"[SELL_ROLE] Nie znaleziono roli {role_name} w cache Discord dla {member.display_name if member else 'nieznany'}, próbuję pobrać bezpośrednio z API"
                        )
                        try:
                            # Próba pobrania członka bezpośrednio z API zamiast cache'u
                            fresh_member = await confirm_interaction.guild.fetch_member(member_id)

                            # Logujemy role pobrane bezpośrednio z API
                            fresh_user_roles = [r.name for r in fresh_member.roles]
                            fresh_user_role_ids = [r.id for r in fresh_member.roles]
                            logger.info(f"[SELL_ROLE] Role użytkownika z API: {fresh_user_roles}")
                            logger.info(
                                f"[SELL_ROLE] ID ról użytkownika z API: {fresh_user_role_ids}"
                            )

                            if fresh_member and self.role in fresh_member.roles:
                                has_role = True
                                member = fresh_member  # Zastąp member świeżymi danymi
                                logger.info(
                                    f"[SELL_ROLE] Znaleziono rolę {role_name} przez bezpośrednie API dla {member.display_name}"
                                )
                            else:
                                logger.warning(
                                    f"[SELL_ROLE] Nawet przez API nie znaleziono roli {role_name} dla {fresh_member.display_name if fresh_member else 'nieznany'}"
                                )

                                # Próba alternatywnego sprawdzenia ról - być może ID roli się zmieniło
                                all_roles = confirm_interaction.guild.roles
                                matching_roles = [r for r in all_roles if r.name == role_name]
                                if matching_roles:
                                    for matching_role in matching_roles:
                                        logger.info(
                                            f"[SELL_ROLE] Znaleziono rolę o nazwie {role_name} z ID: {matching_role.id}"
                                        )
                                        if matching_role in fresh_member.roles:
                                            logger.info(
                                                f"[SELL_ROLE] Użytkownik ma rolę o nazwie {role_name} ale z ID: {matching_role.id} zamiast {role_id}"
                                            )
                                            # Przypisujemy nowe ID roli jeśli się zmieniło
                                            self.role = matching_role
                                            has_role = True
                                            break
                        except Exception as e:
                            logger.error(f"[SELL_ROLE] Błąd podczas pobierania członka z API: {e}")

                    if not has_role:
                        try:
                            await confirm_interaction.followup.send(
                                "Nie masz już tej roli na Discord.", ephemeral=True
                            )
                            logger.warning(
                                f"[SELL_ROLE] Przerwano sprzedaż - użytkownik nie ma roli {role_name} na Discord"
                            )
                        except:
                            pass
                        return

                    # 3. KROK 1: Sprawdź bazę danych
                    has_role_in_db = False
                    db_role = None
                    async with self.bot.get_db() as session:
                        try:
                            # Standardowe sprawdzenie po ID roli
                            db_role = await RoleQueries.get_member_role(session, member_id, role_id)
                            has_role_in_db = db_role is not None
                            logger.info(
                                f"[SELL_ROLE] Sprawdzenie roli w bazie danych po ID {role_id}: {has_role_in_db}"
                            )

                            # Jeśli nie znaleziono roli po ID, ale mamy już nowe ID (bo wykryliśmy rolę o tej samej nazwie)
                            if (
                                not has_role_in_db
                                and hasattr(self, "role")
                                and self.role.id != role_id
                            ):
                                # Sprawdzamy czy użytkownik ma rolę o tej samej nazwie w bazie danych
                                logger.info(
                                    f"[SELL_ROLE] Nie znaleziono roli po ID {role_id}, sprawdzam czy jest rola o ID {self.role.id}"
                                )
                                alternative_db_role = await RoleQueries.get_member_role(
                                    session, member_id, self.role.id
                                )
                                if alternative_db_role is not None:
                                    logger.info(
                                        f"[SELL_ROLE] Znaleziono alternatywną rolę w bazie danych o ID {self.role.id}"
                                    )
                                    has_role_in_db = True
                                    db_role = alternative_db_role
                                    role_id = self.role.id  # Zaktualizuj ID roli

                            await session.commit()
                        except Exception as e:
                            logger.error(
                                f"[SELL_ROLE] Błąd podczas sprawdzania roli w bazie danych: {e}"
                            )
                            await session.rollback()

                    if not has_role_in_db:
                        try:
                            await confirm_interaction.followup.send(
                                "Nie jesteś już właścicielem tej roli w bazie danych.",
                                ephemeral=True,
                            )
                            logger.warning(
                                f"[SELL_ROLE] Przerwano sprzedaż - użytkownik nie ma roli {role_name} w bazie danych"
                            )
                        except:
                            pass
                        return

                    # 4. KROK 2: Usuń rolę z Discord (bez dostępu do bazy danych)
                    try:
                        await member.remove_roles(self.role)
                        logger.info(
                            f"[SELL_ROLE] Usunięto rolę {role_name} z Discord dla {member.display_name}"
                        )
                    except Exception as e:
                        logger.error(f"[SELL_ROLE] Błąd podczas usuwania roli Discord: {e}")

                    # 5. KROK 3: Usuń teamy i uprawnienia moderatora
                    # WAŻNA ZMIANA: Najpierw usuwamy teamy i uprawnienia, a dopiero potem rolę z bazy
                    permissions_removed = False
                    try:
                        async with self.bot.get_db() as session:
                            await remove_premium_role_mod_permissions(session, self.bot, member_id)
                            await session.commit()
                            permissions_removed = True
                            logger.info(
                                f"[SELL_ROLE] Usunięto uprawnienia moderatora i teamy dla {member.display_name}"
                            )
                    except Exception as e:
                        logger.error(f"[SELL_ROLE] Błąd podczas usuwania uprawnień: {e}")
                        # Nawet jeśli wystąpił błąd, kontynuujemy (to nie jest krytyczne)

                    # 6. KROK 4: Usuń rolę z bazy danych jedną niezależną operacją (bez obsługi innych relacji)
                    db_deleted = False
                    try:
                        async with self.bot.get_db() as session:
                            from sqlalchemy import text

                            # Używamy aktualnego role_id, które mogło zostać zaktualizowane wcześniej
                            sql = text(
                                "DELETE FROM member_roles WHERE member_id = :member_id AND role_id = :role_id"
                            )
                            result = await session.execute(
                                sql, {"member_id": member_id, "role_id": role_id}
                            )
                            rows_deleted = result.rowcount if hasattr(result, "rowcount") else 0
                            logger.info(
                                f"[SELL_ROLE] Wynik SQL DELETE: usunięto {rows_deleted} wierszy"
                            )
                            await session.commit()
                            db_deleted = rows_deleted > 0
                            logger.info(
                                f"[SELL_ROLE] Usunięto rolę {role_name} (ID: {role_id}) z bazy danych dla {member.display_name}"
                            )
                    except Exception as e:
                        logger.error(f"[SELL_ROLE] Błąd podczas usuwania roli z bazy danych: {e}")
                        db_deleted = False

                    if not db_deleted:
                        # Przywróć rolę Discord i zakończ
                        try:
                            await member.add_roles(self.role)
                            logger.info(
                                f"[SELL_ROLE] Przywrócono rolę {role_name} na Discord po błędzie bazy danych"
                            )
                        except Exception as e:
                            logger.error(f"[SELL_ROLE] Nie można przywrócić roli na Discord: {e}")
                        try:
                            await confirm_interaction.followup.send(
                                "Wystąpił błąd podczas usuwania roli z bazy danych.", ephemeral=True
                            )
                        except:
                            pass
                        return

                    # 7. KROK 5: Dodaj zwrot do portfela
                    refund_added = False
                    try:
                        async with self.bot.get_db() as session:
                            await MemberQueries.add_to_wallet_balance(
                                session, member_id, refund_amount
                            )
                            await session.commit()
                            refund_added = True
                            logger.info(
                                f"[SELL_ROLE] Dodano zwrot {refund_amount}G do portfela użytkownika {member.display_name}"
                            )
                    except Exception as e:
                        logger.error(f"[SELL_ROLE] Błąd podczas dodawania zwrotu: {e}")

                    if not refund_added:
                        try:
                            await confirm_interaction.followup.send(
                                "Rola została usunięta, ale wystąpił błąd podczas dodawania zwrotu do portfela. Skontaktuj się z administracją.",
                                ephemeral=True,
                            )
                            logger.error(
                                f"[SELL_ROLE] Nie można dodać zwrotu do portfela użytkownika {member.display_name}"
                            )
                        except:
                            pass
                        return

                    # 8. Wyślij wiadomość o sukcesie
                    try:
                        # Log success
                        logger.info(
                            f"[SELL_ROLE] Zakończono pomyślnie sprzedaż roli {role_name} za {refund_amount}G dla {member.display_name}"
                        )

                        # Próba automatycznego odświeżenia profilu użytkownika
                        try:
                            # Utwórz kontekst dla komendy profile
                            ctx = await self.bot.get_context(self.original_interaction.message)
                            if ctx:
                                ctx.author = member
                                logger.info(
                                    f"[SELL_ROLE] Próba wywołania komendy profile dla użytkownika {member.display_name}"
                                )

                                # Odczekaj 1 sekundę aby dać czas na aktualizację bazy danych
                                await asyncio.sleep(1)

                                # Wyślij publiczną wiadomość o udanej sprzedaży
                                embed = discord.Embed(
                                    title="Sprzedaż rangi",
                                    description=f"{member.mention} sprzedał rangę **{role_name}** za **{refund_amount}{CURRENCY_UNIT}**.\nSaldo zostało zaktualizowane.",
                                    color=member.color
                                    if member.color.value != 0
                                    else discord.Color.green(),
                                )
                                await ctx.send(embed=embed)
                        except Exception as e:
                            logger.error(f"[SELL_ROLE] Błąd podczas odświeżania profilu: {e}")
                    except Exception as e:
                        logger.error(f"[SELL_ROLE] Nie można wysłać wiadomości o sukcesie: {e}")

                    # 9. Zaktualizuj wiadomość
                    if self.message:
                        try:
                            await self.message.edit(view=self)
                        except Exception as e:
                            logger.error(f"[SELL_ROLE] Nie można zaktualizować wiadomości: {e}")

                    self.value = True
                    self.stop()

                @discord.ui.button(label="Anuluj", style=discord.ButtonStyle.secondary)
                async def cancel(
                    self, cancel_interaction: discord.Interaction, button: discord.ui.Button
                ):
                    if cancel_interaction.user.id != self.original_interaction.user.id:
                        try:
                            await cancel_interaction.response.send_message(
                                "Nie możesz anulować tej transakcji.", ephemeral=True
                            )
                        except:
                            pass
                        return

                    # Wyłącz wszystkie przyciski
                    for item in self.children:
                        item.disabled = True

                    try:
                        await cancel_interaction.response.send_message(
                            "Anulowano sprzedaż rangi.", ephemeral=True
                        )
                    except:
                        pass

                    # Zaktualizuj oryginalną wiadomość jeśli to możliwe
                    if self.message:
                        try:
                            await self.message.edit(view=self)
                        except:
                            pass

                    self.value = False
                    self.stop()

            view = ConfirmView(self.bot, self.owner_id, role, refund_amount, interaction)
            message = await interaction.response.send_message(
                "Potwierdź sprzedaż rangi:", embed=embed, view=view
            )
            view.message = await interaction.original_response()
            # Wait for the view to finish
            await view.wait()

        finally:
            self.is_selling = False


class InviteInfo:
    def __init__(self, discord_invite, db_invite):
        self.code = discord_invite.code
        self.uses = discord_invite.uses
        self.created_at = discord_invite.created_at
        self.inviter = discord_invite.inviter
        self.last_used = db_invite.last_used if db_invite else None


class InviteListView(discord.ui.View):
    def __init__(self, bot, invites, sort_by="last_used", order="desc", target_user=None):
        super().__init__()
        self.bot = bot
        self.invites = invites
        self.sort_by = sort_by
        self.order = order
        self.target_user = target_user
        self.page = 1
        self.items_per_page = 10
        self.update_buttons()

    def update_buttons(self):
        # Clear existing items
        self.clear_items()

        # Add sort buttons
        sort_uses = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Sortuj po użyciach",
            custom_id="sort_uses",
        )
        sort_created = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Sortuj po dacie utworzenia",
            custom_id="sort_created",
        )
        sort_last_used = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Sortuj po ostatnim użyciu",
            custom_id="sort_last_used",
        )
        toggle_order = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Zmień kolejność",
            custom_id="toggle_order",
        )

        async def sort_callback(interaction: discord.Interaction, sort_type):
            self.sort_by = sort_type
            self.sort_invites()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

        async def order_callback(interaction: discord.Interaction):
            self.order = "asc" if self.order == "desc" else "desc"
            self.sort_invites()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)

        sort_uses.callback = lambda i: sort_callback(i, "uses")
        sort_created.callback = lambda i: sort_callback(i, "created_at")
        sort_last_used.callback = lambda i: sort_callback(i, "last_used")
        toggle_order.callback = order_callback

        self.add_item(sort_uses)
        self.add_item(sort_created)
        self.add_item(sort_last_used)
        self.add_item(toggle_order)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message(
            "Nie masz uprawnień do używania tych przycisków!", ephemeral=True
        )
        return False

    def sort_invites(self):
        def get_sort_key(invite):
            if self.sort_by == "uses":
                return invite.uses or 0
            elif self.sort_by == "created_at":
                return invite.created_at or datetime.min.replace(tzinfo=timezone.utc)
            else:  # last_used
                return invite.last_used or datetime.min.replace(tzinfo=timezone.utc)

        self.invites.sort(key=get_sort_key, reverse=(self.order == "desc"))

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Lista zaproszeń")

        if not self.invites:
            embed.description = "Brak zaproszeń do wyświetlenia."
            return embed

        for invite in self.invites:
            name = f"Kod: {invite.code}"
            value = []

            if invite.inviter:
                value.append(f"Zapraszający: {invite.inviter.mention}")

            value.append(f"Użycia: {invite.uses or 0}")

            if invite.created_at:
                value.append(f"Utworzono: {discord.utils.format_dt(invite.created_at, style='R')}")

            if invite.last_used:
                value.append(
                    f"Ostatnio użyto: {discord.utils.format_dt(invite.last_used, style='R')}"
                )

            embed.add_field(name=name, value="\n".join(value), inline=False)

        # Add sorting info to footer
        sort_type = {
            "uses": "użyciach",
            "created_at": "dacie utworzenia",
            "last_used": "ostatnim użyciu",
        }.get(self.sort_by, "")
        order_type = "malejąco" if self.order == "desc" else "rosnąco"
        embed.set_footer(text=f"Sortowanie po {sort_type} {order_type}")

        return embed


async def setup(bot: commands.Bot):
    """Setup function for InfoCog."""
    await bot.add_cog(InfoCog(bot))
