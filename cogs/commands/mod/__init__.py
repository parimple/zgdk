"""Moderation commands module."""

import logging

from discord.ext import commands

from .clear_commands import ClearCommands
from .gender_commands import GenderCommands
from .mute_commands import MuteCommands
from .timeout_commands import TimeoutCommands

logger = logging.getLogger(__name__)


class ModCog(ClearCommands, MuteCommands, GenderCommands, TimeoutCommands):
    """Combined moderation commands cog."""

    def __init__(self, bot):
        """Initialize the ModCog."""
        self.bot = bot
        self.config = bot.config

        # Initialize all parent classes
        ClearCommands.__init__(self, bot)
        MuteCommands.__init__(self, bot)
        GenderCommands.__init__(self, bot)
        TimeoutCommands.__init__(self, bot)

        logger.info("ModCog initialized with all moderation commands")

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: mod module Loaded")


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(ModCog(bot))
