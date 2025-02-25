"""Info cog."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from datasources.queries import InviteQueries, MemberQueries, RoleQueries, ChannelPermissionQueries
from utils.currency import CURRENCY_UNIT
from utils.permissions import is_admin
from utils.premium import PremiumManager
from utils.refund import calculate_refund

logger = logging.getLogger(__name__)


async def remove_premium_role_mod_permissions(session, bot, member_id: int):
    """
    Usuwa uprawnienia moderatora nadane przez użytkownika po utracie roli premium.
    
    Ta funkcja powinna być wywołana w każdym miejscu, gdzie użytkownik traci rolę premium,
    czy to przez wygaśnięcie, czy przez sprzedaż.
    
    Args:
        session: Sesja bazy danych
        bot: Instancja bota
        member_id: ID użytkownika, który traci rolę premium
    """
    # Usuń tylko uprawnienia moderatorów nadane przez tego użytkownika
    await ChannelPermissionQueries.remove_mod_permissions_granted_by_member(session, member_id)
    
    # Loguj informację o usunięciu uprawnień
    member = bot.guild.get_member(member_id)
    display_name = member.display_name if member else f"User {member_id}"
    logger.info(
        "Removed all moderator permissions granted by %s (%d) [via helper function]",
        display_name,
        member_id,
    )


class InfoCog(commands.Cog):
    """Info cog."""

    def __init__(self, bot):
        self.bot = bot
        # Remove default help command
        self.bot.remove_command("help")

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
                self.add_item(SellRoleButton(bot, premium_roles))


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

    def __init__(self, bot, premium_roles, **kwargs):
        super().__init__(style=discord.ButtonStyle.red, label="Sprzedaj rangę", emoji="💰", **kwargs)
        self.bot = bot
        self.premium_roles = premium_roles

    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        member_role, role = self.premium_roles[0]

        # Get role price from config
        role_price = next(
            (r["price"] for r in self.bot.config["premium_roles"] if r["name"] == role.name), None
        )
        if role_price is None:
            await interaction.response.send_message(
                "Nie można znaleźć ceny roli. Skontaktuj się z administracją.", ephemeral=True
            )
            return

        refund_amount = calculate_refund(member_role.expiration_date, role_price)

        embed = discord.Embed(
            title="Sprzedaż rangi",
            description=f"Czy na pewno chcesz sprzedać rangę {role.name}?\n"
            f"Otrzymasz zwrot w wysokości {refund_amount}{CURRENCY_UNIT}.",
            color=discord.Color.red(),
        )

        # Add confirmation buttons
        confirm_button = discord.ui.Button(
            style=discord.ButtonStyle.danger, label="Potwierdź", custom_id="confirm"
        )
        cancel_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary, label="Anuluj", custom_id="cancel"
        )

        async def confirm_callback(interaction: discord.Interaction):
            async with self.bot.get_db() as session:
                # Remove role from database
                await RoleQueries.delete_member_role(session, interaction.user.id, role.id)
                
                # Usuń uprawnienia moderatora nadane przez użytkownika
                await remove_premium_role_mod_permissions(session, self.bot, interaction.user.id)
                
                # Add refund to wallet
                await MemberQueries.add_to_wallet_balance(
                    session, interaction.user.id, refund_amount
                )
                await session.commit()

            # Remove role from member
            await interaction.user.remove_roles(role)
            await interaction.response.edit_message(
                content=f"Sprzedano rangę {role.name} za {refund_amount}{CURRENCY_UNIT}.",
                embed=None,
                view=None,
            )

        async def cancel_callback(interaction: discord.Interaction):
            await interaction.response.edit_message(
                content="Anulowano sprzedaż rangi.", embed=None, view=None
            )

        confirm_button.callback = confirm_callback
        cancel_button.callback = cancel_callback

        view = discord.ui.View()
        view.add_item(confirm_button)
        view.add_item(cancel_button)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


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
