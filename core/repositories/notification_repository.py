"""
Notification repository for managing notification logs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datasources.models import NotificationLog
from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class NotificationRepository(BaseRepository):
    """Repository for NotificationLog entity operations."""
    
    GLOBAL_SERVICES = ["disboard"]  # Only Disboard is global
    MAX_NOTIFICATION_COUNT = 3
    
    def __init__(self, session: AsyncSession):
        """Initialize notification repository.
        
        Args:
            session: Database session
        """
        super().__init__(NotificationLog, session)
    
    async def add_or_update_notification_log(
        self,
        member_id: int,
        notification_tag: str,
        reset_notification_count: bool = False,
    ) -> NotificationLog:
        """Add or update a notification log entry.
        
        For global services (bumps), member_id should be guild_id.
        For user-specific services, member_id should be user_id.
        
        Args:
            member_id: Member or guild ID
            notification_tag: Service tag
            reset_notification_count: Whether to reset the count
            
        Returns:
            NotificationLog entry
        """
        notification_log = await self.session.get(
            NotificationLog, (member_id, notification_tag)
        )

        if notification_log is None:
            notification_log = NotificationLog(
                member_id=member_id,
                notification_tag=notification_tag,
                sent_at=datetime.now(timezone.utc),
                notification_count=0,
                opted_out=False,
            )
            self.session.add(notification_log)
        else:
            notification_log.sent_at = datetime.now(timezone.utc)
            if reset_notification_count:
                notification_log.notification_count = 0

        await self.session.commit()
        await self.session.refresh(notification_log)
        
        logger.info(
            f"Updated notification log: member={member_id}, tag={notification_tag}"
        )
        return notification_log
    
    async def increment_notification_count(
        self, member_id: int, notification_tag: str
    ) -> Tuple[Optional[NotificationLog], bool]:
        """Increment notification count and return if max count reached.
        
        Args:
            member_id: Member or guild ID
            notification_tag: Service tag
            
        Returns:
            Tuple of (notification_log, should_opt_out)
        """
        notification_log = await self.session.get(
            NotificationLog, (member_id, notification_tag)
        )
        if not notification_log:
            return None, False

        notification_log.notification_count += 1
        should_opt_out = (
            notification_log.notification_count >= self.MAX_NOTIFICATION_COUNT
        )
        if should_opt_out:
            notification_log.opted_out = True
            logger.info(
                f"Auto opt-out for member={member_id}, tag={notification_tag}"
            )

        await self.session.commit()
        await self.session.refresh(notification_log)
        
        return notification_log, should_opt_out
    
    async def get_notification_log(
        self, member_id: int, notification_tag: str
    ) -> Optional[NotificationLog]:
        """Get a notification log for a specific member and tag.
        
        Args:
            member_id: Member or guild ID
            notification_tag: Service tag
            
        Returns:
            NotificationLog if found, None otherwise
        """
        return await self.session.get(NotificationLog, (member_id, notification_tag))
    
    async def get_service_notification_log(
        self,
        service: str,
        guild_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[NotificationLog]:
        """Get notification log for a service.
        
        Handles both global and user-specific services.
        
        Args:
            service: Service name
            guild_id: Guild ID
            user_id: User ID (for non-global services)
            
        Returns:
            NotificationLog if found, None otherwise
        """
        # For global services (bumps), use guild_id as member_id
        member_id = guild_id if service in self.GLOBAL_SERVICES else user_id
        if member_id is None:
            return None

        return await self.session.get(NotificationLog, (member_id, service))
    
    async def get_service_users(
        self, service: str, guild_id: Optional[int] = None
    ) -> List[int]:
        """Get all users who have used a service.
        
        Args:
            service: Service name
            guild_id: Optional guild ID to exclude
            
        Returns:
            List of user IDs
        """
        query = (
            select(NotificationLog.member_id)
            .where(NotificationLog.notification_tag == service)
            .distinct()
        )

        if guild_id is not None:
            query = query.where(NotificationLog.member_id != guild_id)

        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def can_use_service(
        self,
        service: str,
        guild_id: int,
        user_id: Optional[int] = None,
        cooldown_hours: int = 24,
    ) -> bool:
        """Check if service can be used based on cooldown.
        
        Args:
            service: Service name
            guild_id: Guild ID
            user_id: User ID (for non-global services)
            cooldown_hours: Cooldown period in hours
            
        Returns:
            True if service can be used, False otherwise
        """
        # For global services (bumps), use guild_id as member_id
        member_id = guild_id if service in self.GLOBAL_SERVICES else user_id
        if member_id is None:
            return False

        log = await self.session.get(NotificationLog, (member_id, service))
        if not log:
            return True

        now = datetime.now(timezone.utc)
        return (now - log.sent_at) >= timedelta(hours=cooldown_hours)
    
    async def process_service_usage(
        self,
        service: str,
        guild_id: int,
        user_id: int,
        cooldown_hours: int,
        dry_run: bool = False,
    ) -> Tuple[bool, Optional[NotificationLog]]:
        """Process service usage and update notification log.
        
        If dry_run is True, only check if service can be used without updating.
        
        Args:
            service: Service name
            guild_id: Guild ID
            user_id: User ID
            cooldown_hours: Cooldown period in hours
            dry_run: Whether to only check without updating
            
        Returns:
            Tuple of (can_use, notification_log)
        """
        # Get current notification log
        log = await self.get_service_notification_log(
            service, guild_id, user_id
        )

        # If no log exists, service can be used
        if not log:
            if not dry_run:
                log = await self.add_or_update_notification_log(
                    user_id, service
                )
            return True, log

        # Check if cooldown has passed
        current_time = datetime.now(timezone.utc)
        if log.sent_at and log.sent_at + timedelta(hours=cooldown_hours) > current_time:
            return False, log

        # Service can be used - update log if not dry run
        if not dry_run:
            log = await self.add_or_update_notification_log(
                user_id, service
            )

        return True, log