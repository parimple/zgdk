"""Admin info commands module."""

from .admin_info import AdminInfoCog

__all__ = ["AdminInfoCog"]


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(AdminInfoCog(bot))
