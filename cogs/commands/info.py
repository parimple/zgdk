"""Info cog."""

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
    RoleQueries,
)
from utils.currency import CURRENCY_UNIT
from utils.message_sender import MessageSender
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
    await ChannelPermissionQueries.remove_mod_permissions_granted_by_member(
        session, member_id
    )
    logger.info(f"Voice channel permissions granted by {member_id} removed")

    # 2. Usuń teamy należące do tego użytkownika - używamy bezpieczniejszej metody SQL
    deleted_teams = await TeamManager.delete_user_teams_by_sql(session, bot, member_id)
    if deleted_teams > 0:
        logger.info(
            f"Deleted {deleted_teams} teams owned by {member_id} using SQL method"
        )

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
        name="invites",
        description="Wyświetla listę zaproszeń z możliwością sortowania.",
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
                inv
                for inv in combined_invites
                if inv.inviter and inv.inviter.id == target.id
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

    @commands.hybrid_command(
        name="guildinfo", description="Displays the current guild."
    )
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
    async def profile(
        self, ctx: commands.Context, member: Optional[discord.Member] = None
    ):
        """Sends user profile when profile is used as a command."""
        if not member:
            member = ctx.author

        if not isinstance(member, discord.Member):
            member = self.bot.guild.get_member(member.id)
            if not member:
                raise commands.UserInputError(
                    "Nie można znaleźć członka na tym serwerze."
                )

        roles = [role for role in member.roles if role.name != "@everyone"]

        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, member.id)
            all_member_premium_roles = await RoleQueries.get_member_premium_roles(
                session, member.id
            )
            bypass_until = await MemberQueries.get_voice_bypass_status(
                session, member.id
            )

            # Get owned teams from database
            owned_teams_query = await session.execute(
                select(Role).where(
                    (Role.role_type == "team") & (Role.name == str(member.id))
                )
            )
            owned_teams = owned_teams_query.scalars().all()

            # Get teams from database
            teams_query = await session.execute(
                select(Role).where(
                    (Role.role_type == "team") & (Role.name == str(member.id))
                )
            )
            teams = teams_query.scalars().all()

            colors_query = await session.execute(
                select(Role).where(
                    (Role.role_type == "color") & (Role.name == str(member.id))
                )
            )
            colors = colors_query.scalars().all()

            # Get invite count for this member (with validation like legacy system)
            # Use 7 days as minimum account age (like in legacy with GUILD["join_days"])
            invite_count = await InviteQueries.get_member_valid_invite_count(
                session, member.id, ctx.guild, min_days=7
            )

        current_time = datetime.now(timezone.utc)
        logger.info(f"Current time: {current_time}")
        # Filtruj role premium, aby przetwarzać tylko aktywne w logice profilu
        active_premium_roles = []
        if all_member_premium_roles:
            active_premium_roles = [
                (mr, r)
                for mr, r in all_member_premium_roles
                if mr.expiration_date is None or mr.expiration_date > current_time
            ]
            logger.info(
                f"All premium roles for {member.id}: {all_member_premium_roles}"
            )
            logger.info(f"Active premium roles for {member.id}: {active_premium_roles}")

        # Logowanie wygasłych ról dla celów diagnostycznych, jeśli jakieś są
        expired_premium_roles_in_profile_check = [
            (mr, r)
            for mr, r in all_member_premium_roles
            if mr.expiration_date is not None and mr.expiration_date <= current_time
        ]
        if expired_premium_roles_in_profile_check:
            logger.info(
                f"Found expired premium roles in DB for {member.id} during profile check: {expired_premium_roles_in_profile_check}"
            )

        # Check for active mute roles
        mute_roles_config = self.bot.config.get("mute_roles", [])
        active_mutes = []
        has_any_mute = False

        for mute_config in mute_roles_config:
            mute_role = ctx.guild.get_role(mute_config["id"])
            if mute_role and mute_role in member.roles:
                has_any_mute = True
                # Map role descriptions to user-friendly names
                mute_display_names = {
                    "stream_off": "Stream",
                    "send_messages_off": "Wiadomości",
                    "attach_files_off": "Obrazki/Linki",
                    "points_off": "Ranking",
                }
                display_name = mute_display_names.get(
                    mute_config["description"], mute_config["name"]
                )
                active_mutes.append(display_name)

        embed = discord.Embed(
            title=f"{member}",
            color=member.color,
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID:", value=member.id)
        embed.add_field(name="Nazwa na serwerze:", value=member.display_name)
        embed.add_field(
            name="Saldo G:", value=f"{db_member.wallet_balance}{CURRENCY_UNIT}"
        )

        # Add bypass time info if active
        if bypass_until and bypass_until > current_time:
            time_left = bypass_until - current_time
            # Convert to hours and round down to nearest integer
            hours = int(time_left.total_seconds() // 3600)
            embed.add_field(name="Saldo T:", value=f"{hours}T")

        embed.add_field(
            name="Konto od:", value=discord.utils.format_dt(member.created_at, "D")
        )
        embed.add_field(
            name="Dołączył:",
            value=discord.utils.format_dt(member.joined_at, "D")
            if member.joined_at
            else "Brak danych",
        )

        # Add invite count
        embed.add_field(name="Zaproszenia:", value=f"{invite_count}", inline=True)

        # Add mute information if user has any mutes
        if active_mutes:
            mutes_text = ", ".join(active_mutes)
            embed.add_field(name="Aktywne muty:", value=mutes_text, inline=True)

        if active_premium_roles:  # Użyj przefiltrowanych aktywnych ról
            # Jeśli są aktywne role premium, usuń je z ogólnej listy ról, aby uniknąć duplikacji
            # Zakładamy, że interesuje nas tylko jedna, najwyższa aktywna rola premium do specjalnego wyświetlenia
            # Ta logika może wymagać dostosowania, jeśli użytkownik może mieć wiele aktywnych ról premium jednocześnie
            if active_premium_roles:  # Dodatkowe sprawdzenie, czy lista nie jest pusta
                # Sortuj role premium (jeśli jest ich wiele aktywnych) np. po ID, nazwie lub specjalnym polu, jeśli istnieje
                # Dla uproszczenia, bierzemy pierwszą z listy aktywnych
                # Można by tu dodać logikę wyboru 'najważniejszej' aktywnej roli, jeśli jest ich więcej
                main_active_premium_role_obj = active_premium_roles[0][
                    1
                ]  # Obiekt discord.Role
                roles = [
                    role for role in roles if role.id != main_active_premium_role_obj.id
                ]

            PremiumManager.add_premium_roles_to_embed(
                ctx, embed, active_premium_roles
            )  # Przekaż listę aktywnych ról

        # Add team ownership information right after premium roles
        if owned_teams:
            team_roles = []
            for team in owned_teams:
                team_role = ctx.guild.get_role(team.id)
                if team_role:
                    team_roles.append(team_role.mention)
            if team_roles:
                embed.add_field(
                    name="Właściciel Drużyny:", value=" ".join(team_roles), inline=True
                )

        if db_member.first_inviter_id is not None:
            first_inviter = self.bot.get_user(db_member.first_inviter_id)
            if first_inviter is not None:
                embed.add_field(name="Werbownik:", value=first_inviter.name)

        if member.banner:
            embed.set_image(url=member.banner.url)

        # Add "Wybierz swój plan" info (always shown)
        _, premium_text = MessageSender._get_premium_text(ctx)
        if premium_text:
            embed.add_field(name="\u200b", value=premium_text, inline=False)

        # Add footer with mute removal info if user has any mutes
        if active_mutes:
            embed.set_footer(
                text="💡 Zakup dowolnej rangi premium automatycznie usuwa wszystkie muty",
                icon_url=self.bot.user.display_avatar.url,
            )

        view = ProfileView(
            self.bot, member, active_premium_roles, ctx.author
        )  # Przekaż aktywne role do widoku
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="roles", description="Lists all roles in the database"
    )
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

    @commands.hybrid_command(
        name="bypass", description="Zarządza czasem bypassa (T) użytkownika."
    )
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
                await MemberQueries.set_voice_bypass_status(
                    session, member.id, bypass_until
                )
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
        name="games",
        description="Wyświetla listę aktywnych gier na serwerze wraz z liczbą graczy.",
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
        online_members = [
            m for m in ctx.guild.members if m.status != discord.Status.offline
        ]
        total_online = len(online_members)

        for member in online_members:
            if member.activities:
                for activity in member.activities:
                    if activity.type == discord.ActivityType.playing:
                        game_name = activity.name
                        games_data[game_name] = games_data.get(game_name, 0) + 1

        if not games_data:
            await message.edit(
                content="Aktualnie nikt nie gra w żadne gry.", embed=None
            )
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
                    await interaction.response.edit_message(
                        embed=create_games_embed(self.page)
                    )

            @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
            async def next_page(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                if self.page < total_pages:
                    self.page += 1
                    await interaction.response.edit_message(
                        embed=create_games_embed(self.page)
                    )

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
            await MemberQueries.extend_voice_bypass(
                session, user.id, timedelta(hours=hours)
            )
            await session.commit()

        await ctx.reply(f"Dodano {hours}T do konta {user.mention}.")

    @commands.command(
        name="checkroles", description="Sprawdza role użytkownika w logach."
    )
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
            logger.info(
                f"[CHECK_ROLES] Role premium w bazie danych dla {user.display_name}:"
            )
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
            if (
                hasattr(channel, "topic")
                and channel.topic
                and str(member.id) in channel.topic
            ):
                if "Team Channel" in channel.topic or (
                    len(channel.topic.split()) >= 2
                    and channel.topic.split()[0] == str(member.id)
                ):
                    team_channels.append(channel)

        # 3. Sprawdź role w bazie danych
        roles_db_info = []
        teams_db_info = []

        async with self.bot.get_db() as session:
            # Pobierz role premium z bazy danych
            premium_roles_db = await RoleQueries.get_member_premium_roles(
                session, member.id
            )
            for member_role, role in premium_roles_db:
                expiry = (
                    member_role.expiration_date.strftime("%d.%m.%Y %H:%M")
                    if member_role.expiration_date
                    else "bez wygaśnięcia"
                )
                roles_db_info.append(
                    f"Rola: {role.name}, ID: {role.id}, wygasa: {expiry}"
                )

            # Pobierz teamy z bazy danych
            teams_query = await session.execute(
                select(Role).where(
                    (Role.role_type == "team") & (Role.name == str(member.id))
                )
            )
            teams = teams_query.scalars().all()

            for team in teams:
                teams_db_info.append(f"Team ID: {team.id}")

        # 4. Przygotuj i wyślij embed z informacjami
        embed = discord.Embed(
            title=f"Status użytkownika {member.display_name}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Role premium (Discord)",
            value="\n".join([f"{role.name} (ID: {role.id})" for role in premium_roles])
            or "Brak",
            inline=False,
        )
        embed.add_field(
            name="Role premium (baza danych)",
            value="\n".join(roles_db_info) or "Brak",
            inline=False,
        )
        embed.add_field(
            name="Role teamów (Discord)",
            value="\n".join([f"{role.name} (ID: {role.id})" for role in team_roles])
            or "Brak",
            inline=False,
        )
        embed.add_field(
            name="Kanały teamów",
            value="\n".join(
                [f"{channel.name} (ID: {channel.id})" for channel in team_channels]
            )
            or "Brak",
            inline=False,
        )
        embed.add_field(
            name="Teamy (baza danych)",
            value="\n".join(teams_db_info) or "Brak",
            inline=False,
        )

        await ctx.send(embed=embed)
        logger.info(f"Status check completed for {member.display_name}")

        # 5. Jeśli wykryto niespójności, zasugeruj rozwiązania
        inconsistencies = []

        # Sprawdź, czy użytkownik ma teamy ale nie ma roli premium
        if (team_roles or team_channels or teams_db_info) and not premium_roles:
            inconsistencies.append(
                "Użytkownik ma teamy, ale nie ma aktywnej roli premium."
            )

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

    @commands.command(name="force_check_user_premium_roles", aliases=["fcpr"])
    @is_admin()
    async def force_check_user_premium_roles(
        self, ctx: commands.Context, member: discord.Member
    ):
        """Ręcznie sprawdza i usuwa wygasłe role premium dla danego użytkownika."""
        now = datetime.now(timezone.utc)
        removed_roles_count = 0
        checked_roles_count = 0
        messages = []

        async with self.bot.get_db() as session:
            # Pobierz wszystkie role premium użytkownika (aktywne i wygasłe)
            member_premium_roles = await RoleQueries.get_member_premium_roles(
                session, member.id
            )
            checked_roles_count = len(member_premium_roles)

            if not member_premium_roles:
                await ctx.send(
                    f"{member.mention} nie ma żadnych ról premium w bazie danych."
                )
                return

            for member_role_db, role_db in member_premium_roles:
                if member_role_db.expiration_date <= now:
                    # Rola wygasła
                    discord_role = ctx.guild.get_role(role_db.id)
                    if not discord_role:
                        messages.append(
                            f"⚠️ Rola premium `{role_db.name}` (ID: {role_db.id}) znaleziona w bazie jako wygasła, ale nie istnieje na serwerze Discord. Pomijam."
                        )
                        # Rozważ usunięcie z bazy danych, jeśli rola nie istnieje na serwerze
                        # await RoleQueries.delete_member_role(session, member.id, role_db.id)
                        continue

                    if discord_role in member.roles:
                        try:
                            # 1. Usuń rolę z Discord
                            await member.remove_roles(
                                discord_role,
                                reason="Ręczne usunięcie wygasłej roli premium",
                            )
                            messages.append(
                                f"✅ Usunięto wygasłą rolę premium `{discord_role.name}` z {member.mention}."
                            )
                            logger.info(
                                f"ForceCheck: Removed expired premium role {discord_role.name} (ID: {discord_role.id}) from {member.display_name} (ID: {member.id})"
                            )

                            # 2. Usuń powiązane uprawnienia (teamy, mod voice)
                            await remove_premium_role_mod_permissions(
                                session, self.bot, member.id
                            )
                            messages.append(
                                f"ℹ️ Usunięto powiązane uprawnienia (teamy, mod voice) dla {member.mention}."
                            )
                            logger.info(
                                f"ForceCheck: Removed associated mod permissions and teams for {member.display_name} (ID: {member.id})"
                            )

                            # 3. Usuń rolę z bazy danych
                            await RoleQueries.delete_member_role(
                                session, member.id, discord_role.id
                            )
                            await session.commit()  # Commit po każdej udanej operacji usunięcia z DB
                            messages.append(
                                f"✅ Usunięto wpis roli `{discord_role.name}` z bazy danych dla {member.mention}."
                            )
                            logger.info(
                                f"ForceCheck: Deleted role {discord_role.name} (ID: {discord_role.id}) from database for {member.display_name} (ID: {member.id})"
                            )
                            removed_roles_count += 1

                        except discord.Forbidden:
                            messages.append(
                                f"❌ Błąd uprawnień: Nie można usunąć roli `{discord_role.name}` od {member.mention}."
                            )
                            logger.error(
                                f"ForceCheck: Permission error removing role {discord_role.name} from {member.display_name}"
                            )
                        except Exception as e:
                            messages.append(
                                f"❌ Wystąpił nieoczekiwany błąd podczas usuwania roli `{discord_role.name}`: {e}"
                            )
                            logger.error(
                                f"ForceCheck: Unexpected error removing role {discord_role.name} from {member.display_name}: {e}",
                                exc_info=True,
                            )
                            await session.rollback()  # Wycofaj zmiany w razie błędu
                    else:
                        messages.append(
                            f"ℹ️ Wygasła rola premium `{discord_role.name}` znaleziona w bazie, ale {member.mention} jej nie posiada na Discord. Rozważam usunięcie z bazy."
                        )
                        # Można dodać logikę automatycznego czyszczenia takich wpisów z bazy
                        try:
                            await RoleQueries.delete_member_role(
                                session, member.id, discord_role.id
                            )
                            await session.commit()
                            messages.append(
                                f'✅ Usunięto "niepotrzebny" wpis roli `{discord_role.name}` z bazy danych dla {member.mention}.'
                            )
                            logger.info(
                                f"ForceCheck: Cleaned up non-possessed expired role {discord_role.name} (ID: {discord_role.id}) from database for {member.display_name} (ID: {member.id})"
                            )
                        except Exception as e:
                            messages.append(
                                f"❌ Błąd podczas czyszczenia wpisu roli `{discord_role.name}` z bazy: {e}"
                            )
                            logger.error(
                                f"ForceCheck: Error cleaning up database for role {discord_role.name} for {member.display_name}: {e}",
                                exc_info=True,
                            )
                            await session.rollback()
                else:
                    # Rola nie wygasła
                    messages.append(
                        f"ℹ️ Rola premium `{role_db.name}` (ID: {role_db.id}) jest nadal aktywna dla {member.mention} (wygasa: {discord.utils.format_dt(member_role_db.expiration_date, 'R')})."
                    )

            # Końcowy commit jeśli były jakieś operacje bez indywidualnych commitów (choć staramy się ich unikać w pętli)
            # await session.commit() # Raczej niepotrzebne jeśli commitujemy po każdym usunięciu z DB

        final_message = (
            f"Sprawdzono {checked_roles_count} ról premium dla {member.mention}. Usunięto {removed_roles_count} wygasłych ról.\n\nSzczegóły:\n"
            + "\n".join(messages)
        )

        if len(final_message) > 2000:
            await ctx.send(
                f"Sprawdzono {checked_roles_count} ról premium dla {member.mention}. Usunięto {removed_roles_count} wygasłych ról. Logi są zbyt długie, sprawdź konsolę bota."
            )
            logger.info(
                f"ForceCheck Summary for {member.display_name}:\n" + "\n".join(messages)
            )
        else:
            await ctx.send(final_message)


class ProfileView(discord.ui.View):
    """View for profile command."""

    def __init__(
        self, bot, member: discord.Member, active_premium_roles, viewer: discord.Member
    ):
        super().__init__()
        self.bot = bot
        self.member = member
        self.active_premium_roles = active_premium_roles  # Zmieniono nazwę atrybutu
        self.viewer = viewer

        # Add buttons based on conditions
        # Always add "Kup rangę" button - it will open shop for the person who clicks it
        self.add_item(BuyRoleButton(bot, member, viewer))

        # Only add "Sprzedaj rangę" button if viewing own profile and has premium roles
        if viewer.id == member.id and active_premium_roles:
            self.add_item(SellRoleButton(bot, active_premium_roles))


class BuyRoleButton(discord.ui.Button):
    """Button for buying roles."""

    def __init__(self, bot, member, viewer, **kwargs):
        super().__init__(
            style=discord.ButtonStyle.green,
            label="Kup rangę",
            emoji=bot.config.get("emojis", {}).get("mastercard", "💳"),
            **kwargs,
        )
        self.bot = bot
        self.member = member
        self.viewer = viewer

    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        # Always open shop for the user who clicked the button (not the profile owner)
        ctx = await self.bot.get_context(interaction.message)
        ctx.author = interaction.user  # Set the clicking user as author
        await ctx.invoke(self.bot.get_command("shop"))


class SellRoleButton(discord.ui.Button):
    """Button for selling roles."""

    def __init__(self, bot, active_premium_roles, **kwargs):
        super().__init__(
            style=discord.ButtonStyle.red, label="Sprzedaj rangę", emoji="💰", **kwargs
        )
        self.bot = bot
        self.active_premium_roles = active_premium_roles
        self.is_selling = False

    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        if self.is_selling:
            await interaction.response.send_message(
                "Transakcja jest już w toku. Poczekaj na jej zakończenie.",
                ephemeral=True,
            )
            return

        self.is_selling = True
        try:
            # Używamy pierwszej roli z listy aktywnych ról premium do sprzedaży
            if not self.active_premium_roles:
                await interaction.response.send_message(
                    "Nie masz żadnych aktywnych ról premium do sprzedania.",
                    ephemeral=True,
                )
                return

            member_role, role = self.active_premium_roles[0]

            # Verify if user still has the role by checking role IDs
            user_role_ids = [r.id for r in interaction.user.roles]
            if role.id not in user_role_ids:
                await interaction.response.send_message(
                    "Nie posiadasz już tej roli.", ephemeral=True
                )
                return

            # Get role price from config
            role_price = next(
                (
                    r["price"]
                    for r in self.bot.config["premium_roles"]
                    if r["name"] == role.name
                ),
                None,
            )
            if role_price is None:
                await interaction.response.send_message(
                    "Nie można znaleźć ceny roli. Skontaktuj się z administracją.",
                    ephemeral=True,
                )
                return

            refund_amount = calculate_refund(
                member_role.expiration_date, role_price, role.name
            )

            # Use MessageSender for consistent formatting
            description = f"Czy na pewno chcesz sprzedać rangę **{role.name}**?\nOtrzymasz zwrot w wysokości **{refund_amount}{CURRENCY_UNIT}**."
            embed = MessageSender._create_embed(
                title="Sprzedaż rangi",
                description=description,
                ctx=interaction.user,
            )

            # Create a simplified confirmation view
            class ConfirmSaleView(discord.ui.View):
                """Simplified view for confirming role sale."""

                def __init__(self, bot, role: discord.Role, member: discord.Member):
                    super().__init__(timeout=60.0)
                    self.bot = bot
                    self.role = role
                    self.member = member
                    self.value = None

                @discord.ui.button(label="Potwierdź", style=discord.ButtonStyle.danger)
                async def confirm(
                    self,
                    confirm_interaction: discord.Interaction,
                    button: discord.ui.Button,
                ):
                    if confirm_interaction.user.id != self.member.id:
                        await confirm_interaction.response.send_message(
                            "Nie możesz potwierdzić tej transakcji.", ephemeral=True
                        )
                        return

                    # Disable buttons
                    for item in self.children:
                        item.disabled = True

                    await confirm_interaction.response.defer()

                    # Use the new role sale manager
                    from utils.role_sale import RoleSaleManager

                    sale_manager = RoleSaleManager(self.bot)

                    success, message, refund_amount = await sale_manager.sell_role(
                        self.member, self.role, confirm_interaction
                    )

                    if success:
                        # Send success message using MessageSender system for consistency

                        success_description = f"🔄 Operacja zakończona! Sprzedałeś rangę **{self.role.name}** za **{refund_amount}{CURRENCY_UNIT}**. Saldo uaktualnione – wróć, kiedy zechcesz!"

                        # Add premium text directly to description like MessageSender does
                        _, premium_text = MessageSender._get_premium_text(
                            self.member  # Pass context for premium text
                        )
                        if premium_text:
                            success_description = (
                                f"{success_description}\n{premium_text}"
                            )

                        success_embed = MessageSender._create_embed(
                            title="Sprzedaż rangi",
                            description=success_description,
                            ctx=self.member,
                        )

                        await confirm_interaction.followup.send(embed=success_embed)
                    else:
                        # Send error message using MessageSender system for consistency

                        error_embed = MessageSender._create_embed(
                            title="Błąd sprzedaży rangi",
                            description=message,
                            color="error",
                            ctx=self.member,
                        )
                        await confirm_interaction.followup.send(
                            embed=error_embed, ephemeral=True
                        )

                    # Update the message
                    try:
                        await confirm_interaction.message.edit(view=self)
                    except:
                        pass

                    self.value = success
                    self.stop()

                @discord.ui.button(label="Anuluj", style=discord.ButtonStyle.secondary)
                async def cancel(
                    self,
                    cancel_interaction: discord.Interaction,
                    button: discord.ui.Button,
                ):
                    if cancel_interaction.user.id != self.member.id:
                        # Use embed for consistency

                        error_embed = MessageSender._create_embed(
                            description="Nie możesz anulować tej transakcji.",
                            color="error",  # Keep error color for unauthorized access
                            ctx=self.member,
                        )
                        await cancel_interaction.response.send_message(
                            embed=error_embed, ephemeral=True
                        )
                        return

                    for item in self.children:
                        item.disabled = True

                    # Use embed for consistency

                    cancel_embed = MessageSender._create_embed(
                        description="Anulowano sprzedaż rangi.",
                        ctx=self.member,  # Use member's color instead of "info"
                    )
                    await cancel_interaction.response.send_message(
                        embed=cancel_embed, ephemeral=True
                    )

                    try:
                        await cancel_interaction.message.edit(view=self)
                    except:
                        pass

                    self.value = False
                    self.stop()

                async def on_timeout(self):
                    for item in self.children:
                        item.disabled = True
                    try:
                        # Use embed for timeout message consistency

                        timeout_embed = MessageSender._create_embed(
                            description="Czas na potwierdzenie minął.",
                            ctx=self.member,  # Use member's color instead of "warning"
                        )
                        await self.message.edit(embed=timeout_embed, view=self)
                    except:
                        pass

            view = ConfirmSaleView(self.bot, role, interaction.user)
            await interaction.response.send_message(
                "Potwierdź sprzedaż rangi:", embed=embed, view=view
            )
            view.message = await interaction.original_response()
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
    def __init__(
        self, bot, invites, sort_by="last_used", order="desc", target_user=None
    ):
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
            await interaction.response.edit_message(
                embed=self.create_embed(), view=self
            )

        async def order_callback(interaction: discord.Interaction):
            self.order = "asc" if self.order == "desc" else "desc"
            self.sort_invites()
            await interaction.response.edit_message(
                embed=self.create_embed(), view=self
            )

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
                value.append(
                    f"Utworzono: {discord.utils.format_dt(invite.created_at, style='R')}"
                )

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
