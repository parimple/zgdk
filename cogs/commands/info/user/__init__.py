"""User info commands module."""

from .user_info import UserInfoCog

__all__ = ["UserInfoCog"]


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(UserInfoCog(bot))