"""Team commands module."""

from discord.ext import commands
from .team_management import TeamManagementCommands
from .member_management import MemberManagementCommands


class TeamCog(
    TeamManagementCommands,
    MemberManagementCommands,
    commands.Cog
):
    """Team commands cog combining all team-related functionality."""
    
    def __init__(self, bot):
        """Initialize team cog with all components."""
        self.bot = bot
        # Initialize parent classes
        TeamManagementCommands.__init__(self, bot)
        MemberManagementCommands.__init__(self, bot)


async def setup(bot):
    """Setup function for team cog."""
    await bot.add_cog(TeamCog(bot))