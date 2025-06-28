"""Voice commands module."""

from discord.ext import commands

from .admin_commands import AdminCommands
from .channel_commands import ChannelCommands
from .permission_commands import PermissionCommands


class VoiceCog(PermissionCommands, ChannelCommands, AdminCommands, commands.Cog):
    """Voice commands cog for managing voice channel permissions and operations."""

    def __init__(self, bot):
        """Initialize voice cog with all components."""
        # Initialize commands.Cog first
        commands.Cog.__init__(self)

        # Initialize component classes
        PermissionCommands.__init__(self, bot)
        ChannelCommands.__init__(self, bot)
        AdminCommands.__init__(self, bot)

        # Store bot reference
        self.bot = bot


async def setup(bot):
    """Setup function for voice cog."""
    await bot.add_cog(VoiceCog(bot))
