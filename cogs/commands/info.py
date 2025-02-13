"""Info cog."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from datasources.queries import InviteQueries, MemberQueries, RoleQueries
from utils.currency import CURRENCY_UNIT
from utils.premium import PremiumManager
from utils.refund import calculate_refund

logger = logging.getLogger(__name__)


class InfoCog(commands.Cog):
    """Info cog."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: info.py Loaded")

    @commands.hybrid_command(
        name="invites", description="Wyświetla listę zaproszeń z możliwością sortowania."
    )
    @commands.has_permissions(administrator=True)
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
    @commands.has_permissions(administrator=True)
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
    @commands.has_permissions(administrator=True)
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
    # @commands.has_permissions(administrator=True)
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

        if db_member.first_inviter_id is not None:
            first_inviter = self.bot.get_user(db_member.first_inviter_id)
            if first_inviter is not None:
                embed.add_field(name="Werbownik:", value=first_inviter.name)

        if member.banner:
            embed.set_image(url=member.banner.url)

        view = ProfileView(self.bot, member, premium_roles, ctx.author)
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="roles", description="Lists all roles in the database")
    @commands.has_permissions(administrator=True)
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
    @commands.has_permissions(administrator=True)
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

    @commands.hybrid_command(name="pomoc", description="Wyświetla listę dostępnych komend")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def help_command(self, ctx: commands.Context):
        """Wyświetla listę dostępnych komend"""
        await ctx.send_help()

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

        view = GameListView(games_data)
        final_embed = view.create_embed()
        final_embed.set_footer(
            text=f"{final_embed.footer.text} | Przeanalizowano {total_online} użytkowników online"
        )
        await message.edit(embed=final_embed, view=view)


class ProfileView(discord.ui.View):
    """Profile view."""

    def __init__(self, bot, member: discord.Member, premium_roles, viewer: discord.Member):
        super().__init__()
        self.bot = bot
        self.member = member
        self.premium_roles = premium_roles
        self.viewer = viewer
        self.add_item(
            BuyRoleButton(
                bot=self.bot,
                member=self.member,
                viewer=self.viewer,
                label="Sklep z rangami",
                style=discord.ButtonStyle.success,
            )
        )
        self.add_item(
            SellRoleButton(
                bot=self.bot,
                premium_roles=premium_roles,
                label="Sprzedaj rolę",
                style=discord.ButtonStyle.danger,
                disabled=not bool(premium_roles) or self.viewer != self.member,
            )
        )
        self.add_item(
            discord.ui.Button(
                label="Doładuj konto",
                style=discord.ButtonStyle.link,
                url=self.bot.config["donate_url"],
            )
        )


class BuyRoleButton(discord.ui.Button):
    """Button to buy a role."""

    def __init__(self, bot, member, viewer, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.member = member
        self.viewer = viewer

    async def callback(self, interaction: discord.Interaction):
        ctx = await self.bot.get_context(interaction.message)
        ctx.author = interaction.user
        await ctx.invoke(self.bot.get_command("shop"))


class SellRoleButton(discord.ui.Button):
    """Button to sell a role."""

    def __init__(self, bot, premium_roles, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.premium_roles = premium_roles

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        role_price_map = {role["name"]: role["price"] for role in self.bot.config["premium_roles"]}

        # Disable the button immediately to prevent multiple clicks
        self.disabled = True
        await interaction.message.edit(view=self.view)

        async with self.bot.get_db() as session:
            try:
                # Get current premium roles again to ensure they still exist
                current_premium_roles = await RoleQueries.get_member_premium_roles(
                    session, member.id
                )
                if not current_premium_roles:
                    await interaction.response.send_message(
                        "Nie masz już żadnej roli premium do sprzedania."
                    )
                    return

                for member_role, role in current_premium_roles:
                    role_price = role_price_map.get(role.name)
                    if not role_price:
                        continue

                    refund_amount = calculate_refund(member_role.expiration_date, role_price)

                    # Remove role from Discord
                    await member.remove_roles(role)
                    # Remove role from database
                    await RoleQueries.delete_member_role(session, member.id, role.id)
                    # Add refund to wallet
                    await MemberQueries.add_to_wallet_balance(session, member.id, refund_amount)

                    await interaction.response.send_message(
                        f"Sprzedano rolę {role.name} za {refund_amount}{CURRENCY_UNIT}. "
                        f"Kwota zwrotu została dodana do twojego salda."
                    )
                    break  # Only sell one role at a time

                await session.commit()

            except discord.DiscordException as error:
                logger.error("Error while selling role: %s", error, exc_info=True)
                await interaction.response.send_message(
                    "Wystąpił błąd podczas sprzedawania roli. Proszę spróbować ponownie później."
                )


class InviteInfo:
    def __init__(self, discord_invite, db_invite):
        self.code = discord_invite.code
        self.inviter = discord_invite.inviter
        self.uses = discord_invite.uses
        self.max_uses = discord_invite.max_uses
        self.max_age = discord_invite.max_age
        self.created_at = discord_invite.created_at
        self.last_used_at = db_invite.last_used_at if db_invite else None


class InviteListView(discord.ui.View):
    def __init__(self, bot, invites, sort_by="last_used", order="desc", target_user=None):
        super().__init__(timeout=60)
        self.bot = bot
        self.invites = invites
        self.sort_by = sort_by
        self.order = order
        self.target_user = target_user
        self.current_page = 0
        self.per_page = 5
        self.total_pages = max(1, (len(self.invites) - 1) // self.per_page + 1)
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        self.add_item(
            discord.ui.Button(
                label="◀",
                style=discord.ButtonStyle.primary,
                custom_id="prev",
            )
        )
        self.add_item(
            discord.ui.Button(
                label="▶",
                style=discord.ButtonStyle.primary,
                custom_id="next",
            )
        )
        self.add_item(
            discord.ui.Button(
                label="Użycia", style=discord.ButtonStyle.secondary, custom_id="sort_uses"
            )
        )
        self.add_item(
            discord.ui.Button(
                label="Utworzone", style=discord.ButtonStyle.secondary, custom_id="sort_created_at"
            )
        )
        self.add_item(
            discord.ui.Button(
                label="Ostatnie użycie",
                style=discord.ButtonStyle.secondary,
                custom_id="sort_last_used",
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] in ["prev", "next"]:
            if interaction.data["custom_id"] == "prev":
                self.current_page = (self.current_page - 1) % self.total_pages
            elif interaction.data["custom_id"] == "next":
                self.current_page = (self.current_page + 1) % self.total_pages
        elif interaction.data["custom_id"].startswith("sort_"):
            new_sort_by = interaction.data["custom_id"].split("_", 1)[1]
            if new_sort_by == self.sort_by:
                self.order = "asc" if self.order == "desc" else "desc"
            else:
                self.sort_by = new_sort_by
                self.order = "desc"
            self.sort_invites()
            self.current_page = 0

        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
        return True

    def sort_invites(self):
        if self.sort_by == "uses":
            self.invites.sort(key=lambda x: x.uses, reverse=(self.order == "desc"))
        elif self.sort_by == "created_at":
            self.invites.sort(key=lambda x: x.created_at, reverse=(self.order == "desc"))
        elif self.sort_by == "last_used":
            self.invites.sort(
                key=lambda x: x.last_used_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=(self.order == "desc"),
            )

    def create_embed(self) -> discord.Embed:
        start = self.current_page * self.per_page
        end = start + self.per_page
        current_invites = self.invites[start:end]

        title = f"Lista zaproszeń ({len(self.invites)}/1000 aktywnych zaproszeń)"
        if self.target_user:
            title += f" użytkownika {self.target_user.display_name}"

        embed = discord.Embed(title=title, color=discord.Color.blue())
        for invite in current_invites:
            creator = self.bot.get_user(invite.inviter.id) if invite.inviter else None
            creator_mention = creator.mention if creator else "Nieznany"

            invite_type = "Stałe"
            if invite.max_age > 0:
                expiry_time = timedelta(seconds=invite.max_age)
                invite_type = f"Wygasa {discord.utils.format_dt(datetime.now(timezone.utc) + expiry_time, 'R')}"
            elif invite.max_uses > 0:
                invite_type = f"Wygasa po {invite.max_uses} użyciach"

            value = (
                f"Twórca: {creator_mention}\n"
                f"Użycia: {invite.uses}/{invite.max_uses if invite.max_uses else '∞'}\n"
                f"Utworzono: {discord.utils.format_dt(invite.created_at, 'R')}\n"
                f"Ostatnie użycie: {discord.utils.format_dt(invite.last_used_at, 'R') if invite.last_used_at else 'Nigdy'}\n"
                f"Typ: {invite_type}"
            )
            embed.add_field(name=f"Kod: {invite.code}", value=value, inline=False)

        embed.set_footer(
            text=f"Strona {self.current_page + 1}/{self.total_pages} | Sortowanie: {self.sort_by}, Kolejność: {self.order}"
        )
        return embed


class GameListView(discord.ui.View):
    """View for displaying and sorting game list."""

    def __init__(self, games_data):
        super().__init__(timeout=60)
        self.games_data = games_data
        self.sort_by_count = True
        self.current_page = 0
        self.per_page = 15  # Number of games per page
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        self.add_item(
            discord.ui.Button(
                label="◀",
                style=discord.ButtonStyle.primary,
                custom_id="prev",
                disabled=self.current_page == 0,
            )
        )
        self.add_item(
            discord.ui.Button(
                label="Sortuj po liczbie graczy"
                if not self.sort_by_count
                else "Sortuj alfabetycznie",
                style=discord.ButtonStyle.primary,
                custom_id="toggle_sort",
            )
        )
        sorted_games = self.sort_games()
        max_pages = (len(sorted_games) - 1) // self.per_page + 1
        self.add_item(
            discord.ui.Button(
                label="▶",
                style=discord.ButtonStyle.primary,
                custom_id="next",
                disabled=self.current_page >= max_pages - 1,
            )
        )

    def sort_games(self):
        if self.sort_by_count:
            return sorted(self.games_data.items(), key=lambda x: (-x[1], x[0].lower()))
        else:
            return sorted(self.games_data.items(), key=lambda x: x[0].lower())

    def create_embed(self) -> discord.Embed:
        sorted_games = self.sort_games()
        total_games = len(sorted_games)
        max_pages = (total_games - 1) // self.per_page + 1

        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, total_games)
        current_games = sorted_games[start_idx:end_idx]

        embed = discord.Embed(
            title="Aktywne gry na serwerze",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )

        total_players = sum(count for _, count in self.games_data.items())
        description = f"Łącznie graczy: {total_players}\nŁącznie gier: {total_games}\n\n"

        for game_name, player_count in current_games:
            description += (
                f"**{game_name}**: {player_count} {'gracz' if player_count == 1 else 'graczy'}\n"
            )

        embed.description = description

        # Footer will be extended in the games command with the total processed users
        embed.set_footer(
            text=f"Strona {self.current_page + 1}/{max_pages} | "
            f"Sortowanie: {'Liczba graczy' if self.sort_by_count else 'Alfabetycznie'}"
        )
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] == "toggle_sort":
            self.sort_by_count = not self.sort_by_count
            self.current_page = 0  # Reset to first page when sorting changes
        elif interaction.data["custom_id"] == "prev":
            self.current_page = max(0, self.current_page - 1)
        elif interaction.data["custom_id"] == "next":
            sorted_games = self.sort_games()
            max_pages = (len(sorted_games) - 1) // self.per_page + 1
            self.current_page = min(self.current_page + 1, max_pages - 1)

        self.update_buttons()
        embed = self.create_embed()
        # Preserve the extended footer if it exists
        if interaction.message.embeds[0].footer.text.endswith("użytkowników"):
            embed.set_footer(text=interaction.message.embeds[0].footer.text)
        await interaction.response.edit_message(embed=embed, view=self)
        return True


async def setup(bot: commands.Bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(InfoCog(bot))
