"""Admin commands module."""

from discord.ext import commands

from .activity_rank_commands import ActivityRankCommands
from .category_commands import CategoryCommands


async def setup(bot: commands.Bot) -> None:
    """Setup admin cogs."""
    await bot.add_cog(CategoryCommands(bot))
    await bot.add_cog(ActivityRankCommands(bot))