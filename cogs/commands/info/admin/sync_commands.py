"""Admin commands for syncing bot commands."""

import logging

from discord.ext import commands

from utils.permissions import is_admin

logger = logging.getLogger(__name__)


class SyncCommands(commands.Cog):
    """Commands for syncing bot commands."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="sync", description="Syncs commands.")
    @is_admin()
    async def sync(self, ctx) -> None:
        """Sync commands."""
        synced = await ctx.bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} commands globally")