"""
Notification Log Queries for the database.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import NotificationLog

logger = logging.getLogger(__name__)


class NotificationLogQueries:
    """Class for Notification Log Queries"""

    GLOBAL_SERVICES = ["disboard"]  # tylko Disboard jest globalny
    MAX_NOTIFICATION_COUNT = 3

    @staticmethod
    async def add_or_update_notification_log(
        session: AsyncSession,
        member_id: int,
        notification_tag: str,
        reset_notification_count: bool = False,
    ) -> NotificationLog:
        """
        Add or update a notification log entry.
        For global services (bumps), member_id should be guild_id.
        For user-specific services, member_id should be user_id.
        """
        notification_log = await session.get(NotificationLog, (member_id, notification_tag))

        if notification_log is None:
            notification_log = NotificationLog(
                member_id=member_id,
                notification_tag=notification_tag,
                sent_at=datetime.now(timezone.utc),
                notification_count=0,
                opted_out=False,
            )
            session.add(notification_log)
        else:
            notification_log.sent_at = datetime.now(timezone.utc)
            if reset_notification_count:
                notification_log.notification_count = 0

        return notification_log

    @staticmethod
    async def increment_notification_count(
        session: AsyncSession, member_id: int, notification_tag: str
    ) -> Tuple[NotificationLog, bool]:
        """
        Increment notification count and return if max count reached.
        Returns (notification_log, should_opt_out)
        """
        notification_log = await session.get(NotificationLog, (member_id, notification_tag))
        if not notification_log:
            return None, False

        notification_log.notification_count += 1
        should_opt_out = notification_log.notification_count >= NotificationLogQueries.MAX_NOTIFICATION_COUNT
        if should_opt_out:
            notification_log.opted_out = True

        return notification_log, should_opt_out

    @staticmethod
    async def get_notification_log(
        session: AsyncSession, member_id: int, notification_tag: str
    ) -> Optional[NotificationLog]:
        """Get a notification log for a specific member and tag"""
        return await session.get(NotificationLog, (member_id, notification_tag))

    @staticmethod
    async def get_service_notification_log(
        session: AsyncSession,
        service: str,
        guild_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[NotificationLog]:
        """Get notification log for a service, handling both global and user-specific services"""
        # For global services (bumps), use guild_id as member_id
        member_id = guild_id if service in NotificationLogQueries.GLOBAL_SERVICES else user_id
        if member_id is None:
            return None

        return await session.get(NotificationLog, (member_id, service))

    @staticmethod
    async def get_service_users(session: AsyncSession, service: str, guild_id: Optional[int] = None) -> List[int]:
        """Get all users who have used a service"""
        from sqlalchemy import select

        query = select(NotificationLog.member_id).where(NotificationLog.notification_tag == service).distinct()

        if guild_id is not None:
            query = query.where(NotificationLog.member_id != guild_id)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def can_use_service(
        session: AsyncSession,
        service: str,
        guild_id: int,
        user_id: Optional[int] = None,
        cooldown_hours: int = 24,
    ) -> bool:
        """Check if service can be used based on cooldown"""
        # For global services (bumps), use guild_id as member_id
        member_id = guild_id if service in NotificationLogQueries.GLOBAL_SERVICES else user_id
        if member_id is None:
            return False

        log = await session.get(NotificationLog, (member_id, service))
        if not log:
            return True

        now = datetime.now(timezone.utc)
        return (now - log.sent_at) >= timedelta(hours=cooldown_hours)

    @staticmethod
    async def process_service_usage(
        session: AsyncSession,
        service: str,
        guild_id: int,
        user_id: int,
        cooldown_hours: int,
        dry_run: bool = False,
    ) -> Tuple[bool, Optional[NotificationLog]]:
        """
        Process service usage and update notification log.
        If dry_run is True, only check if service can be used without updating the log.
        """
        # Get current notification log
        log = await NotificationLogQueries.get_service_notification_log(session, service, guild_id, user_id)

        # If no log exists, service can be used
        if not log:
            if not dry_run:
                log = await NotificationLogQueries.add_or_update_notification_log(session, user_id, service)
            return True, log

        # Check if cooldown has passed
        current_time = datetime.now(timezone.utc)
        if log.sent_at and log.sent_at + timedelta(hours=cooldown_hours) > current_time:
            return False, log

        # Service can be used - update log if not dry run
        if not dry_run:
            log = await NotificationLogQueries.add_or_update_notification_log(session, user_id, service)

        return True, log
