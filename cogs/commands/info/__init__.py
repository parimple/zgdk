"""Info commands module.

This module contains split info commands organized by functionality:
- admin_info.py: Admin-only information commands
- user_info.py: User profile and stats commands
- server_info.py: Server information commands
- help_info.py: Help and documentation commands
"""

from .admin_info import AdminInfoCog
from .help_info import HelpInfoCog
from .server_info import ServerInfoCog
from .user_info import UserInfoCog

__all__ = ["AdminInfoCog", "UserInfoCog", "ServerInfoCog", "HelpInfoCog"]


async def setup(bot):
    """Setup function to add all info cogs to bot."""
    await bot.add_cog(AdminInfoCog(bot))
    await bot.add_cog(UserInfoCog(bot))
    await bot.add_cog(ServerInfoCog(bot))
    await bot.add_cog(HelpInfoCog(bot))
