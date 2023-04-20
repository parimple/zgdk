"""This is a simple example of a cog."""

import logging

from discord.ext import commands

logger = logging.getLogger(__name__)


class InfoCog(commands.Cog):
    """This is a simple example of a cog."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener which is called when the bot goes online."""
        logger.info("Cog: client.py Loaded")

    @commands.command(name="ping", description="Sends Pong!")
    async def ping(self, ctx: commands.Context):
        """Sends Pong! when ping is used as a command."""
        await ctx.reply("pong")


async def setup(bot: commands.Bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(InfoCog(bot))
