"""Bypass time management commands."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from datasources.queries import MemberQueries
from utils.permissions import is_admin

logger = logging.getLogger(__name__)


class BypassCommands(commands.Cog):
    """Commands for managing bypass time."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.hybrid_command(
        name="bypass", description="Zarządzaj czasem obejścia (T) dla użytkowników."
    )
    @is_admin()
    async def bypass(
        self,
        ctx: commands.Context,
        action: str,
        member: discord.Member,
        hours: Optional[int] = None,
    ):
        """Zarządzaj czasem obejścia (T) dla użytkowników."""
        async with self.bot.get_db() as session:
            if action == "add":
                if hours is None or hours <= 0:
                    await ctx.send("Musisz podać liczbę godzin większą od 0.")
                    return

                updated_member = await MemberQueries.add_bypass_time(
                    session, member.id, hours
                )
                await session.commit()
                await ctx.send(
                    f"✅ Dodano {hours} godzin czasu T dla {member.mention}. Wygasa: {updated_member.voice_bypass_until}"
                )

            elif action == "check":
                bypass_until = await MemberQueries.get_voice_bypass_status(
                    session, member.id
                )
                if bypass_until:
                    await ctx.send(f"⏰ {member.mention} ma czas T do: {bypass_until}")
                else:
                    await ctx.send(f"❌ {member.mention} nie ma aktywnego czasu T.")
            
            else:
                await ctx.send("❌ Nieprawidłowa akcja. Użyj 'add' lub 'check'.")