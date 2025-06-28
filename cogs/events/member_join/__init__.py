"""Member join event module."""

from .member_join_event import OnMemberJoinEvent

async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(OnMemberJoinEvent(bot))

__all__ = ["OnMemberJoinEvent", "setup"]