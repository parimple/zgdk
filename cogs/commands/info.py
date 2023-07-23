"""This is a simple example of a cog."""

import logging
from typing import Optional, Sequence

import discord
from discord.ext import commands

from ...datasources.models import HandledPayment
from ...datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries
from ...utils.timestamp import DiscordTimestamp

logger = logging.getLogger(__name__)


class InfoCog(commands.Cog):
    """This is a simple example of a cog."""

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: client.py Loaded")

    @commands.hybrid_command(name="ping", description="Sends Pong!")
    async def ping(self, ctx: commands.Context):
        """Sends Pong! when ping is used as a command."""
        logging.info("ping")
        await ctx.reply("pong")

    @commands.hybrid_command(name="payments", description="Lists all payments")
    async def all_payments(self, ctx: commands.Context):
        """Fetch and display all payments."""
        payments: Sequence[HandledPayment] = await HandledPaymentQueries.get_last_payments(
            self.session,
            limit=15,
        )
        embed = discord.Embed(title="All Payments")
        for payment in payments:
            name = f"Payment ID: {payment.id}"
            value = (
                f"Member ID: {payment.member_id}\n"
                f"Name: {payment.name}\n"
                f"Amount: {payment.amount}\n"
                f"Paid at: {payment.paid_at}\n"
                f"Payment type: {payment.payment_type}"
            )
            embed.add_field(name=name, value=value, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="guildinfo", description="Displays the current guild.")
    async def guild_info(self, ctx: commands.Context):
        """Sends the current guild when guildinfo is used as a command."""
        guild = self.bot.guild
        if isinstance(guild, discord.Guild):
            await ctx.send(f"Current guild: {guild.name} (ID: {guild.id})")
        else:
            await ctx.send(f"Guild ID: {guild}")

    @commands.hybrid_command(name="profile", description="Wyświetla profil użytkownika.")
    async def profile(self, ctx: commands.Context, member: Optional[discord.Member]):
        """Sends user profile when profile is used as a command."""
        if not isinstance(member, discord.Member):
            raise commands.UserInputError("Komenda musi być użyta na serwerze.")
        member = member or ctx.author
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
        embed.add_field(name="Saldo portfela:", value=db_member.wallet_balance)
        embed.add_field(name="Konto od:", value=DiscordTimestamp.format(member.created_at, "D"))
        embed.add_field(
            name="Dołączył:",
            value=DiscordTimestamp.format(member.joined_at, "D")
            if member.joined_at
            else "Brak danych",
        )
        embed.add_field(name="Role:", value=" ".join([role.mention for role in roles]))

        if db_member.first_inviter_id is not None:
            first_inviter = self.bot.get_user(db_member.first_inviter_id)
            if first_inviter is not None:
                embed.add_field(name="Werbownik:", value=first_inviter.name)

        if member.banner:
            embed.set_image(url=member.banner.url)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="roles", description="Lists all roles in the database")
    async def all_roles(self, ctx: commands.Context):
        """Fetch and display all roles in the database."""
        roles = await RoleQueries.get_all_roles(self.session)
        embed = discord.Embed(title="All Roles")
        for role in roles:
            embed.add_field(
                name=f"Role ID: {role.id}",
                value=f"Role Name: {role.name}\nRole Type: {role.role_type}",
                inline=False,
            )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(InfoCog(bot))
