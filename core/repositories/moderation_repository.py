"""Moderation repository implementation for moderation-related operations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.repositories.base_repository import BaseRepository
from datasources.models import ModerationLog

logger = logging.getLogger(__name__)


class ModerationRepository(BaseRepository):
    """Repository for moderation-related operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(ModerationLog, session)

    async def log_action(
        self,
        target_user_id: int,
        moderator_id: int,
        action_type: str,
        mute_type: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        reason: Optional[str] = None,
        channel_id: int = 0,
    ) -> ModerationLog:
        """Log a moderation action to the database."""
        return await self.log_mute_action(
            target_user_id=target_user_id,
            moderator_id=moderator_id,
            action_type=action_type,
            mute_type=mute_type,
            duration_seconds=duration_seconds,
            reason=reason,
            channel_id=channel_id,
        )

    async def log_mute_action(
        self,
        target_user_id: int,
        moderator_id: int,
        action_type: str,
        mute_type: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        reason: Optional[str] = None,
        channel_id: int = 0,
    ) -> ModerationLog:
        """Log a moderation action to the database."""
        try:
            # Calculate expiration date if duration provided
            expires_at = None
            if duration_seconds is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

            # Create log entry
            moderation_log = ModerationLog(
                target_user_id=target_user_id,
                moderator_id=moderator_id,
                action_type=action_type,
                mute_type=mute_type,
                duration_seconds=duration_seconds,
                reason=reason,
                channel_id=channel_id,
                expires_at=expires_at,
            )

            self.session.add(moderation_log)
            await self.session.flush()

            self._log_operation(
                "log_mute_action",
                target_user_id=target_user_id,
                moderator_id=moderator_id,
                action_type=action_type,
                mute_type=mute_type,
            )

            return moderation_log

        except Exception as e:
            self._log_error(
                "log_mute_action",
                e,
                target_user_id=target_user_id,
                moderator_id=moderator_id,
            )
            raise

    async def get_user_mute_history(self, user_id: int, limit: int = 50) -> List[ModerationLog]:
        """Get mute history for a user."""
        try:
            result = await self.session.execute(
                select(ModerationLog)
                .options(joinedload(ModerationLog.moderator))
                .where(ModerationLog.target_user_id == user_id)
                .where(ModerationLog.action_type.in_(["mute", "unmute"]))
                .order_by(ModerationLog.created_at.desc())
                .limit(limit)
            )
            logs = list(result.scalars().all())

            self._log_operation(
                "get_user_mute_history",
                user_id=user_id,
                limit=limit,
                count=len(logs),
            )

            return logs

        except Exception as e:
            self._log_error("get_user_mute_history", e, user_id=user_id)
            return []

    async def get_user_mute_count(self, user_id: int, days_back: int = 30) -> int:
        """Count how many times a user was muted in the last X days."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

            result = await self.session.execute(
                select(func.count(ModerationLog.id))
                .where(ModerationLog.target_user_id == user_id)
                .where(ModerationLog.action_type == "mute")
                .where(ModerationLog.created_at >= cutoff_date)
            )
            count = result.scalar() or 0

            self._log_operation(
                "get_user_mute_count",
                user_id=user_id,
                days_back=days_back,
                count=count,
            )

            return count

        except Exception as e:
            self._log_error("get_user_mute_count", e, user_id=user_id)
            return 0

    async def get_moderator_actions(
        self,
        moderator_id: int,
        action_type: Optional[str] = None,
        days_back: int = 30,
        limit: int = 100,
    ) -> List[ModerationLog]:
        """Get actions performed by a moderator."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

            query = (
                select(ModerationLog)
                .options(joinedload(ModerationLog.target_user))
                .where(ModerationLog.moderator_id == moderator_id)
                .where(ModerationLog.created_at >= cutoff_date)
                .order_by(ModerationLog.created_at.desc())
                .limit(limit)
            )

            if action_type:
                query = query.where(ModerationLog.action_type == action_type)

            result = await self.session.execute(query)
            logs = list(result.scalars().all())

            self._log_operation(
                "get_moderator_actions",
                moderator_id=moderator_id,
                action_type=action_type,
                days_back=days_back,
                count=len(logs),
            )

            return logs

        except Exception as e:
            self._log_error("get_moderator_actions", e, moderator_id=moderator_id)
            return []

    async def get_mute_statistics(self, days_back: int = 30) -> Dict[str, any]:
        """Get mute statistics for the last X days."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

            # Total mutes in period
            total_mutes_result = await self.session.execute(
                select(func.count(ModerationLog.id))
                .where(ModerationLog.action_type == "mute")
                .where(ModerationLog.created_at >= cutoff_date)
            )
            total_mutes = total_mutes_result.scalar() or 0

            # Statistics by mute type
            mute_types_result = await self.session.execute(
                select(ModerationLog.mute_type, func.count(ModerationLog.id))
                .where(ModerationLog.action_type == "mute")
                .where(ModerationLog.created_at >= cutoff_date)
                .where(ModerationLog.mute_type.isnot(None))
                .group_by(ModerationLog.mute_type)
                .order_by(func.count(ModerationLog.id).desc())
            )
            mute_types = dict(mute_types_result.all())

            # Top users with most mutes
            top_muted_users_result = await self.session.execute(
                select(ModerationLog.target_user_id, func.count(ModerationLog.id))
                .where(ModerationLog.action_type == "mute")
                .where(ModerationLog.created_at >= cutoff_date)
                .group_by(ModerationLog.target_user_id)
                .order_by(func.count(ModerationLog.id).desc())
                .limit(10)
            )
            top_muted_users = top_muted_users_result.all()

            # Top moderators with most activity
            top_moderators_result = await self.session.execute(
                select(ModerationLog.moderator_id, func.count(ModerationLog.id))
                .where(ModerationLog.action_type == "mute")
                .where(ModerationLog.created_at >= cutoff_date)
                .group_by(ModerationLog.moderator_id)
                .order_by(func.count(ModerationLog.id).desc())
                .limit(10)
            )
            top_moderators = top_moderators_result.all()

            statistics = {
                "total_mutes": total_mutes,
                "mute_types": mute_types,
                "top_muted_users": top_muted_users,
                "top_moderators": top_moderators,
                "period_days": days_back,
            }

            self._log_operation(
                "get_mute_statistics",
                days_back=days_back,
                total_mutes=total_mutes,
            )

            return statistics

        except Exception as e:
            self._log_error("get_mute_statistics", e, days_back=days_back)
            return {
                "total_mutes": 0,
                "mute_types": {},
                "top_muted_users": [],
                "top_moderators": [],
                "period_days": days_back,
            }

    async def get_recent_actions(self, limit: int = 20) -> List[ModerationLog]:
        """Get recent moderation actions."""
        try:
            result = await self.session.execute(
                select(ModerationLog)
                .options(
                    joinedload(ModerationLog.target_user),
                    joinedload(ModerationLog.moderator),
                )
                .order_by(ModerationLog.created_at.desc())
                .limit(limit)
            )
            logs = list(result.scalars().all())

            self._log_operation(
                "get_recent_actions",
                limit=limit,
                count=len(logs),
            )

            return logs

        except Exception as e:
            self._log_error("get_recent_actions", e, limit=limit)
            return []

    async def get_active_mutes(self) -> List[ModerationLog]:
        """Get all currently active mutes."""
        try:
            now = datetime.now(timezone.utc)
            result = await self.session.execute(
                select(ModerationLog)
                .options(
                    joinedload(ModerationLog.target_user),
                    joinedload(ModerationLog.moderator),
                )
                .where(ModerationLog.action_type == "mute")
                .where((ModerationLog.expires_at.is_(None)) | (ModerationLog.expires_at > now))
                .order_by(ModerationLog.created_at.desc())
            )
            logs = list(result.scalars().all())

            self._log_operation(
                "get_active_mutes",
                count=len(logs),
            )

            return logs

        except Exception as e:
            self._log_error("get_active_mutes", e)
            return []

    async def get_expired_mutes(self) -> List[ModerationLog]:
        """Get all expired mutes that haven't been unmuted."""
        try:
            now = datetime.now(timezone.utc)
            result = await self.session.execute(
                select(ModerationLog)
                .options(
                    joinedload(ModerationLog.target_user),
                    joinedload(ModerationLog.moderator),
                )
                .where(ModerationLog.action_type == "mute")
                .where(ModerationLog.expires_at.isnot(None))
                .where(ModerationLog.expires_at <= now)
                .order_by(ModerationLog.expires_at.asc())
            )
            logs = list(result.scalars().all())

            self._log_operation(
                "get_expired_mutes",
                count=len(logs),
            )

            return logs

        except Exception as e:
            self._log_error("get_expired_mutes", e)
            return []
