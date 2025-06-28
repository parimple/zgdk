"""Admin commands for user management and status checking."""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

from datasources.queries import MemberQueries
from utils.permissions import is_admin

from .helpers import (
    get_member_premium_roles_info,
    get_member_teams_info,
    get_member_voice_permissions_info,
    get_member_active_mutes,
)

logger = logging.getLogger(__name__)


class UserCommands(commands.Cog):
    """Commands for user management."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="addt", description="Dodaje czas T użytkownikowi.")
    @is_admin()
    async def add_t(self, ctx: commands.Context, user: discord.User, hours: int):
        """Dodaje czas T użytkownikowi."""
        async with self.bot.get_db() as session:
            member = await MemberQueries.add_bypass_time(session, user.id, hours)
            await session.commit()
            await ctx.send(
                f"Dodano {hours} godzin czasu T dla {user.mention}. Nowy czas wygaśnięcia: {member.voice_bypass_until}"
            )

    @commands.command(
        name="checkstatus", description="Sprawdź status użytkownika i jego teamy."
    )
    @is_admin()
    async def check_status(self, ctx, member: discord.Member):
        """Sprawdź status użytkownika i jego teamy."""
        logger.info(f"Checking status for member {member.id}")

        embed = discord.Embed(
            title=f"Status: {member.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )

        async with self.bot.get_db() as session:
            # 1. Podstawowe informacje
            embed.add_field(name="ID", value=str(member.id), inline=True)
            embed.add_field(name="Nick", value=member.display_name, inline=True)
            embed.add_field(
                name="Dołączył", value=member.joined_at.strftime("%Y-%m-%d"), inline=True
            )

            # 2. Informacje z bazy danych
            db_member = await MemberQueries.get_or_add_member(
                session, member.id, wallet_balance=0, joined_at=member.joined_at
            )

            embed.add_field(
                name="Portfel",
                value=f"{db_member.wallet_balance if db_member else 0} PLN",
                inline=True,
            )

            # 3. Role premium
            premium_roles = await get_member_premium_roles_info(session, ctx.guild, member)

            if premium_roles:
                embed.add_field(
                    name="Role Premium", value="\n".join(premium_roles), inline=False
                )
            else:
                embed.add_field(name="Role Premium", value="Brak", inline=False)

            # 4. Sprawdź teamy
            owned_teams, member_teams = await get_member_teams_info(self.bot, ctx.guild, member)

            if owned_teams:
                embed.add_field(
                    name="Własne Teamy",
                    value="\n".join(owned_teams)[:1024],
                    inline=False,
                )
            else:
                embed.add_field(name="Własne Teamy", value="Brak", inline=False)

            if member_teams:
                embed.add_field(
                    name="Członek Teamów",
                    value=", ".join(member_teams)[:1024],
                    inline=False,
                )

            # 5. Uprawnienia moderatora kanałów
            voice_channels = await get_member_voice_permissions_info(session, ctx.guild, member)
            if voice_channels:
                embed.add_field(
                    name="Moderator Kanałów",
                    value="\n".join(voice_channels)[:1024],
                    inline=False,
                )

            # 6. Aktywne kary
            active_mutes = get_member_active_mutes(ctx.guild, member)
            if active_mutes:
                embed.add_field(
                    name="Aktywne Kary", value=", ".join(active_mutes), inline=False
                )

            # 7. Status połączenia głosowego
            if member.voice:
                voice_info = f"Kanał: {member.voice.channel.name}"
                if member.voice.self_mute:
                    voice_info += " (wyciszony)"
                if member.voice.self_deaf:
                    voice_info += " (ogłuszony)"
                embed.add_field(name="Połączenie Głosowe", value=voice_info, inline=False)

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text=f"Sprawdzone przez {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url,
        )

        await ctx.send(embed=embed)