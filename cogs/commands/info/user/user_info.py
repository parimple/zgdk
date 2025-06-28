"""Main user info cog that combines all user commands."""

import logging

from discord.ext import commands

from .profile_commands import ProfileCommands
from .bypass_commands import BypassCommands

logger = logging.getLogger(__name__)


class UserInfoCog(ProfileCommands, BypassCommands):
    """User info commands cog."""

    def __init__(self, bot):
        """Initialize user info cog."""
        self.bot = bot
        # Get team symbol from config
        team_config = self.bot.config.get("team", {})
        self.team_symbol = team_config.get("symbol", "☫")

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: user_info.py Loaded")


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(UserInfoCog(bot))