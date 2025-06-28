"""Main user info cog that combines all user commands."""

import logging

from discord.ext import commands

from .bypass_commands import BypassCommands
from .profile_commands import ProfileCommands

logger = logging.getLogger(__name__)


class UserInfoCog(ProfileCommands, BypassCommands):
    """User info commands cog."""

    def __init__(self, bot):
        """Initialize user info cog."""
        self.bot = bot
        # Get team symbol from config
        team_config = self.bot.config.get("team", {})
        self.team_symbol = team_config.get("symbol", "☫")
        # Initialize parent classes
        ProfileCommands.__init__(self, bot)
        BypassCommands.__init__(self, bot)

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: user_info.py Loaded")


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(UserInfoCog(bot))
