"""Main admin info cog that combines all admin commands."""

import logging

from discord.ext import commands

from .invite_commands import InviteCommands
from .role_commands import RoleCommands
from .sync_commands import SyncCommands
from .user_commands import UserCommands

logger = logging.getLogger(__name__)


class AdminInfoCog(InviteCommands, RoleCommands, SyncCommands, UserCommands):
    """Admin info commands cog."""

    def __init__(self, bot):
        """Initialize admin info cog."""
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: admin_info.py Loaded")


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(AdminInfoCog(bot))