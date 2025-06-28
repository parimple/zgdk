"""Bump event module."""

from .bump_event import OnBumpEvent


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(OnBumpEvent(bot))


__all__ = ["OnBumpEvent", "setup"]
