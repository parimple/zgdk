"""On Command Event"""

import logging

from discord.ext import commands

logger = logging.getLogger(__name__)


class OnCommandEvent(commands.Cog):
    """Class for the On Command Error Discord Event"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        """On Command Event"""
        logger.info(
            "Command '%s' was executed by '%s' in '%s'",
            ctx.command,
            ctx.author,
            ctx.guild,
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, exception: commands.CommandError):
        """On Command Error Event"""
        if isinstance(exception, commands.CommandNotFound):
            return
        elif isinstance(exception, commands.MemberNotFound):
            logger.warning(f"MemberNotFound error for command '{ctx.command}': {exception}")
            await ctx.send(f"Nie znaleziono użytkownika: {exception.argument}")
            return

        logger.error(
            "An error occurred while executing command '%s': %s",
            ctx.command,
            exception,
            exc_info=True,
        )


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnCommandEvent(bot))
