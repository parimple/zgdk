"""
Manager for handling voice bypass functionality.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from datasources.queries import MemberQueries

logger = logging.getLogger(__name__)


class BypassManager:
    """Manager for handling voice bypass functionality."""

    def __init__(self, bot):
        self.bot = bot

    async def extend_bypass_for_bump(self, member_id: int) -> Optional[datetime]:
        """
        Extend voice bypass duration for a member after bumping the server.
        Returns new expiration datetime or None if failed.
        """
        return await self._extend_bypass(member_id, hours=12)

    async def extend_bypass_for_activity(self, member_id: int) -> Optional[datetime]:
        """
        Extend voice bypass duration for a member after significant activity.
        Returns new expiration datetime or None if failed.
        """
        return await self._extend_bypass(member_id, hours=6)

    async def _extend_bypass(
        self, member_id: int, hours: int = 12
    ) -> Optional[datetime]:
        """
        Internal method to extend voice bypass duration.
        Returns new expiration datetime or None if failed.
        """
        try:
            async with self.bot.get_db() as session:
                return await MemberQueries.extend_voice_bypass(
                    session, member_id, timedelta(hours=hours)
                )
        except Exception as e:
            logger.error(f"Failed to extend bypass for member {member_id}: {str(e)}")
            return None

    async def get_bypass_status(self, member_id: int) -> Optional[datetime]:
        """
        Get current bypass status for a member.
        Returns expiration datetime or None if no active bypass.
        """
        try:
            async with self.bot.get_db() as session:
                return await MemberQueries.get_voice_bypass_status(session, member_id)
        except Exception as e:
            logger.error(
                f"Failed to get bypass status for member {member_id}: {str(e)}"
            )
            return None

    async def clear_bypass(self, member_id: int) -> bool:
        """
        Clear bypass for a member.
        Returns True if successful, False otherwise.
        """
        try:
            async with self.bot.get_db() as session:
                return await MemberQueries.clear_voice_bypass(session, member_id)
        except Exception as e:
            logger.error(f"Failed to clear bypass for member {member_id}: {str(e)}")
            return False
