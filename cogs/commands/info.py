""" Info cog. """

import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

from datasources.queries import MemberQueries, RoleQueries
from utils.premium import PremiumManager

CURRENCY_UNIT = "G"

logger = logging.getLogger(__name__)


class InfoCog(commands.Cog):
    """Info cog."""

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: info.py Loaded")

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

    @commands.hybrid_command(name="profile", description="Wyświetla profil użytkownika.")
    @commands.has_permissions(administrator=True)
    async def profile(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Sends user profile when profile is used as a command."""
        if not member:
            member = ctx.author

        if not isinstance(member, discord.Member):
            member = self.bot.guild.get_member(member.id)
            if not member:
                raise commands.UserInputError("Nie można znaleźć członka na tym serwerze.")

        roles = [role for role in member.roles if role.name != "@everyone"]
        db_member = await MemberQueries.get_or_add_member(self.session, member.id)
        await self.session.commit()

        embed = discord.Embed(
            title=f"{member}",
            color=member.color,
            timestamp=ctx.message.created_at,
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID:", value=member.id)
        embed.add_field(name="Nazwa na serwerze:", value=member.display_name)
        embed.add_field(name="Saldo portfela:", value=f"{db_member.wallet_balance}{CURRENCY_UNIT}")
        embed.add_field(name="Konto od:", value=discord.utils.format_dt(member.created_at, "D"))
        embed.add_field(
            name="Dołączył:",
            value=discord.utils.format_dt(member.joined_at, "D")
            if member.joined_at
            else "Brak danych",
        )
        embed.add_field(name="Role:", value=" ".join([role.mention for role in roles]))

        # Fetching premium roles
        premium_roles = await RoleQueries.get_member_premium_roles(self.session, member.id)
        if premium_roles:
            PremiumManager.add_premium_roles_to_embed(ctx, embed, premium_roles)

        if db_member.first_inviter_id is not None:
            first_inviter = self.bot.get_user(db_member.first_inviter_id)
            if first_inviter is not None:
                embed.add_field(name="Werbownik:", value=first_inviter.name)

        if member.banner:
            embed.set_image(url=member.banner.url)

        view = ProfileView(ctx, self.bot, premium_roles)
        await ctx.send(embed=embed, view=view)


class ProfileView(discord.ui.View):
    """Profile view."""

    def __init__(self, ctx: commands.Context, bot, premium_roles):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.session = bot.session
        self.premium_roles = premium_roles

        if premium_roles:
            self.add_item(SellRoleButton(ctx, bot, premium_roles[0]))
        else:
            sell_button = discord.ui.Button(
                label="Sprzedaj rolę", style=discord.ButtonStyle.danger, disabled=True
            )
            self.add_item(sell_button)

    @discord.ui.button(label="Kup rolę", style=discord.ButtonStyle.primary)
    async def shop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Redirect to the shop."""
        await interaction.response.send_message("Przekierowanie do sklepu...", ephemeral=True)
        shop_cog = self.bot.get_cog("ShopCog")
        await shop_cog.shop(self.ctx)


class SellRoleButton(discord.ui.Button):
    """Button to sell a role."""

    def __init__(self, ctx: commands.Context, bot, member_role):
        super().__init__(label="Sprzedaj rolę", style=discord.ButtonStyle.danger)
        self.ctx = ctx
        self.bot = bot
        self.member_role = member_role
        self.session = bot.session

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Sprzedaję rolę...", ephemeral=True)

        async with self.session() as session:
            # Remove the role from the member
            member = self.ctx.author
            role = discord.utils.get(self.bot.guild.roles, id=self.member_role.role_id)
            if role:
                await member.remove_roles(role)

            # Calculate the refund amount
            now = datetime.now(timezone.utc)
            expiration_date = self.member_role.expiration_date.replace(tzinfo=timezone.utc)
            remaining_days = (expiration_date - now).days

            # Get the role price from the config
            role_price_map = {
                role["symbol"]: role["price"] for role in self.bot.config["premium_roles"]
            }
            role_price = role_price_map.get(role.name, 0)
            refund_amount = int(((remaining_days / 30) * (role_price / 2)))

            # Update the member's wallet balance
            await MemberQueries.add_to_wallet_balance(session, member.id, refund_amount)
            await RoleQueries.delete_member_role(session, member.id, self.member_role.role_id)
            await session.commit()

        await interaction.followup.send(
            f"Rola została sprzedana. Zwrot: {refund_amount}{CURRENCY_UNIT}", ephemeral=True
        )


async def setup(bot: commands.Bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(InfoCog(bot))
