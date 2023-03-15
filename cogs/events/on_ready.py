"""On Ready Event"""

from discord.ext import commands


class EventOnReady(commands.Cog):
    """Class for the On Ready Discord Event"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """On Ready Event"""
        print("Cog: on_ready.py Loaded")


async def setup(bot):
    """Setup Function"""
    await bot.add_cog(EventOnReady(bot))
