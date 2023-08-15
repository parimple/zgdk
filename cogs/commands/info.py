"""This is a simple example of a cog."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from datasources.queries import MemberQueries, RoleQueries
from utils.premium import PremiumManager

CURRENCY_UNIT = "G"

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

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="roles", description="Lists all roles in the database")
    @commands.has_permissions(administrator=True)
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
