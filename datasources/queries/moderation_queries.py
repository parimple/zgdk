"""
Moderation queries for the database.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..models import ModerationLog

logger = logging.getLogger(__name__)


class ModerationLogQueries:
    """Class for Moderation Log Queries"""

    @staticmethod
    async def log_mute_action(
        session: AsyncSession,
        target_user_id: int,
        moderator_id: int,
        action_type: str,
        mute_type: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        reason: Optional[str] = None,
        channel_id: int = 0,
    ) -> ModerationLog:
        """Zapisuje akcję moderatorską do bazy danych"""
        # Oblicz datę wygaśnięcia jeśli podano czas trwania
        expires_at = None
        if duration_seconds is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=duration_seconds
            )

        # Stwórz wpis w logu
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

        session.add(moderation_log)
        await session.flush()
        return moderation_log

    @staticmethod
    async def get_user_mute_history(
        session: AsyncSession, user_id: int, limit: int = 50
    ) -> List[ModerationLog]:
        """Pobiera historię mute'ów użytkownika"""
        result = await session.execute(
            select(ModerationLog)
            .options(joinedload(ModerationLog.moderator))
            .where(ModerationLog.target_user_id == user_id)
            .where(ModerationLog.action_type.in_(["mute", "unmute"]))
            .order_by(ModerationLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_user_mute_count(
        session: AsyncSession, user_id: int, days_back: int = 30
    ) -> int:
        """Zlicza ile razy użytkownik był mutowany w ostatnich X dniach"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        result = await session.execute(
            select(func.count(ModerationLog.id))
            .where(ModerationLog.target_user_id == user_id)
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_moderator_actions(
        session: AsyncSession,
        moderator_id: int,
        action_type: Optional[str] = None,
        days_back: int = 30,
        limit: int = 100,
    ) -> List[ModerationLog]:
        """Pobiera akcje wykonane przez moderatora"""
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

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_mute_statistics(
        session: AsyncSession, days_back: int = 30
    ) -> Dict[str, any]:
        """Pobiera statystyki mute'ów z ostatnich X dni"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        # Wszystkie mute'y w okresie
        total_mutes_result = await session.execute(
            select(func.count(ModerationLog.id))
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
        )
        total_mutes = total_mutes_result.scalar() or 0

        # Statystyki według typu mute'a
        mute_types_result = await session.execute(
            select(ModerationLog.mute_type, func.count(ModerationLog.id))
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
            .where(ModerationLog.mute_type.isnot(None))
            .group_by(ModerationLog.mute_type)
            .order_by(func.count(ModerationLog.id).desc())
        )
        mute_types = dict(mute_types_result.all())

        # Top użytkownicy z największą liczbą mute'ów
        top_muted_users_result = await session.execute(
            select(ModerationLog.target_user_id, func.count(ModerationLog.id))
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
            .group_by(ModerationLog.target_user_id)
            .order_by(func.count(ModerationLog.id).desc())
            .limit(10)
        )
        top_muted_users = top_muted_users_result.all()

        # Top moderatorzy z największą aktywnością
        top_moderators_result = await session.execute(
            select(ModerationLog.moderator_id, func.count(ModerationLog.id))
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
            .group_by(ModerationLog.moderator_id)
            .order_by(func.count(ModerationLog.id).desc())
            .limit(10)
        )
        top_moderators = top_moderators_result.all()

        return {
            "total_mutes": total_mutes,
            "mute_types": mute_types,
            "top_muted_users": top_muted_users,
            "top_moderators": top_moderators,
            "period_days": days_back,
        }

    @staticmethod
    async def get_recent_actions(
        session: AsyncSession, limit: int = 20
    ) -> List[ModerationLog]:
        """Pobiera ostatnie akcje moderatorskie"""
        result = await session.execute(
            select(ModerationLog)
            .options(
                joinedload(ModerationLog.target_user),
                joinedload(ModerationLog.moderator),
            )
            .order_by(ModerationLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()