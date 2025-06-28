"""Activity repository for tracking member activities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.base_repository import BaseRepository
from datasources.models import Activity, Member


class ActivityRepository(BaseRepository):
    """Repository for activity tracking operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Activity, session)

    async def add_activity(
        self,
        member_id: int,
        points: int,
        activity_type: str,
        description: Optional[str] = None,
    ) -> Activity:
        """Add a new activity entry."""
        try:
            activity = Activity(
                member_id=member_id,
                points=points,
                activity_type=activity_type,
                description=description,
                created_at=datetime.now(timezone.utc),
            )

            self.session.add(activity)
            await self.session.flush()
            await self.session.refresh(activity)

            self._log_operation(
                "add_activity",
                member_id=member_id,
                points=points,
                activity_type=activity_type,
            )

            return activity

        except Exception as e:
            self._log_error("add_activity", e, member_id=member_id)
            raise

    async def get_member_activity(
        self,
        member_id: int,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Activity]:
        """Get member's activity history."""
        try:
            query = select(Activity).where(Activity.member_id == member_id)

            if activity_type:
                query = query.where(Activity.activity_type == activity_type)

            if start_date:
                query = query.where(Activity.created_at >= start_date)

            query = query.order_by(Activity.created_at.desc()).limit(limit)

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            self._log_error("get_member_activity", e, member_id=member_id)
            return []

    async def get_member_total_points(
        self,
        member_id: int,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
    ) -> int:
        """Get total points for a member."""
        try:
            query = select(func.sum(Activity.points)).where(Activity.member_id == member_id)

            if activity_type:
                query = query.where(Activity.activity_type == activity_type)

            if start_date:
                query = query.where(Activity.created_at >= start_date)

            result = await self.session.execute(query)
            return result.scalar() or 0

        except Exception as e:
            self._log_error("get_member_total_points", e, member_id=member_id)
            return 0

    async def get_leaderboard(
        self,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        limit: int = 10,
    ) -> list[tuple[Member, int]]:
        """Get activity leaderboard."""
        try:
            query = (
                select(Member, func.sum(Activity.points).label("total_points"))
                .join(Activity, Activity.member_id == Member.id)
                .group_by(Member.id)
            )

            if activity_type:
                query = query.where(Activity.activity_type == activity_type)

            if start_date:
                query = query.where(Activity.created_at >= start_date)

            query = query.order_by(func.sum(Activity.points).desc()).limit(limit)

            result = await self.session.execute(query)
            return [(row[0], row[1]) for row in result]

        except Exception as e:
            self._log_error("get_leaderboard", e)
            return []

    async def get_activity_leaderboard_optimized(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Get activity leaderboard with optimized query."""
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            result = await self.session.execute(
                select(
                    Activity.member_id,
                    func.sum(Activity.points).label("total_points"),
                    func.sum(func.case((Activity.activity_type == "voice", Activity.points), else_=0)).label(
                        "voice_points"
                    ),
                    func.sum(func.case((Activity.activity_type == "text", Activity.points), else_=0)).label(
                        "text_points"
                    ),
                )
                .where(Activity.created_at >= start_date)
                .group_by(Activity.member_id)
                .order_by(func.sum(Activity.points).desc())
                .limit(limit)
            )

            leaderboard = []
            for row in result:
                leaderboard.append(
                    {
                        "member_id": row.member_id,
                        "total_points": row.total_points,
                        "voice_points": row.voice_points,
                        "text_points": row.text_points,
                    }
                )

            return leaderboard

        except Exception as e:
            self._log_error("get_activity_leaderboard_optimized", e)
            return []

    async def get_total_points(
        self,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
    ) -> int:
        """Get total points across all members."""
        try:
            query = select(func.sum(Activity.points))

            if activity_type:
                query = query.where(Activity.activity_type == activity_type)

            if start_date:
                query = query.where(Activity.created_at >= start_date)

            result = await self.session.execute(query)
            return result.scalar() or 0

        except Exception as e:
            self._log_error("get_total_points", e)
            return 0

    async def get_active_members_count(
        self,
        start_date: Optional[datetime] = None,
    ) -> int:
        """Get count of active members."""
        try:
            query = select(func.count(func.distinct(Activity.member_id)))

            if start_date:
                query = query.where(Activity.created_at >= start_date)

            result = await self.session.execute(query)
            return result.scalar() or 0

        except Exception as e:
            self._log_error("get_active_members_count", e)
            return 0

    async def cleanup_old_activities(self, days_to_keep: int = 90) -> int:
        """Clean up old activity records."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

            # Get count of records to delete
            count_result = await self.session.execute(
                select(func.count(Activity.id)).where(Activity.created_at < cutoff_date)
            )
            count = count_result.scalar() or 0

            if count > 0:
                # Delete old records
                await self.session.execute(Activity.__table__.delete().where(Activity.created_at < cutoff_date))
                await self.session.flush()

                self._log_operation("cleanup_old_activities", deleted_count=count)

            return count

        except Exception as e:
            self._log_error("cleanup_old_activities", e)
            return 0
