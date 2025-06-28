"""Premium commands module for premium features like role colors."""

import logging
from discord.ext import commands

from .color_commands import ColorCommands

logger = logging.getLogger(__name__)


class PremiumCog(ColorCommands):
    """Premium commands cog for color management."""
    
    def __init__(self, bot):
        """Initialize the PremiumCog."""
        self.bot = bot
        self.prefix = self.bot.command_prefix[0] if self.bot.command_prefix else ","
        
        # Initialize parent class
        ColorCommands.__init__(self, bot)
        
        logger.info("PremiumCog initialized with color commands")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: premium module Loaded")


async def setup(bot: commands.Bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(PremiumCog(bot))