"""On Ready Event"""

import logging

from discord.ext import commands

logger = logging.getLogger(__name__)


class OnReadyEvent(commands.Cog):
    """Class for the On Ready Discord Event"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """On Ready Event"""
        logger.info("Cog: on_ready.py Loaded")


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnReadyEvent(bot))
