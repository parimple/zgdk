"""Activity repository implementation for activity tracking operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.repositories.base_repository import BaseRepository
from datasources.models import Activity, Member


class ActivityRepository(BaseRepository):
    """Repository for activity tracking operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Activity, session)

    async def get_member_activity(
        self,
        member_id: int,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Activity]:
        """Get member activity records with optional filtering."""
        try:
            query = select(Activity).where(Activity.member_id == member_id)
            
            if activity_type:
                query = query.where(Activity.activity_type == activity_type)
            
            if start_date:
                query = query.where(Activity.date >= start_date)
            
            if end_date:
                query = query.where(Activity.date <= end_date)
            
            query = query.order_by(Activity.date.desc())
            
            result = await self.session.execute(query)
            activities = list(result.scalars().all())
            
            self._log_operation(
                "get_member_activity",
                member_id=member_id,
                activity_type=activity_type,
                count=len(activities)
            )
            
            return activities

        except Exception as e:
            self._log_error("get_member_activity", e, member_id=member_id)
            return []

    async def add_activity(
        self,
        member_id: int,
        points: int,
        activity_type: str,
        date: Optional[datetime] = None,
    ) -> Activity:
        """Add activity record for member."""
        try:
            if date is None:
                date = datetime.now(timezone.utc)

            # Create new activity record
            activity = Activity(
                member_id=member_id,
                points=points,
                activity_type=activity_type,
                date=date
            )

            self.session.add(activity)
            await self.session.flush()

            self._log_operation(
                "add_activity",
                member_id=member_id,
                points=points,
                activity_type=activity_type
            )

            return activity

        except Exception as e:
            self._log_error("add_activity", e, member_id=member_id)
            raise

    async def get_member_total_points(
        self,
        member_id: int,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Get total points for member with optional filtering."""
        try:
            query = select(func.sum(Activity.points)).where(Activity.member_id == member_id)
            
            if activity_type:
                query = query.where(Activity.activity_type == activity_type)
            
            if start_date:
                query = query.where(Activity.date >= start_date)
            
            if end_date:
                query = query.where(Activity.date <= end_date)

            result = await self.session.execute(query)
            total = result.scalar()
            
            total_points = total or 0
            
            self._log_operation(
                "get_member_total_points",
                member_id=member_id,
                activity_type=activity_type,
                total_points=total_points
            )
            
            return total_points

        except Exception as e:
            self._log_error("get_member_total_points", e, member_id=member_id)
            return 0

    async def get_leaderboard(
        self,
        activity_type: Optional[str] = None,
        limit: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[tuple[Member, int]]:
        """Get activity leaderboard with optimized single query."""
        try:
            # Optimized query that joins with Member to avoid N+1
            query = select(
                Member,
                func.sum(Activity.points).label("total_points")
            ).select_from(
                Activity
            ).join(
                Member, Activity.member_id == Member.id
            )
            
            if activity_type:
                query = query.where(Activity.activity_type == activity_type)
            
            if start_date:
                query = query.where(Activity.date >= start_date)
            
            if end_date:
                query = query.where(Activity.date <= end_date)
            
            query = query.group_by(Member.id).order_by(
                func.sum(Activity.points).desc()
            ).limit(limit)

            result = await self.session.execute(query)
            
            leaderboard = []
            for row in result:
                member = row.Member
                points = row.total_points or 0
                leaderboard.append((member, points))

            self._log_operation(
                "get_leaderboard",
                activity_type=activity_type,
                limit=limit,
                count=len(leaderboard)
            )

            return leaderboard

        except Exception as e:
            self._log_error("get_leaderboard", e, activity_type=activity_type)
            return []

    async def get_total_points(
        self,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Get total points across all members with optional filtering."""
        try:
            query = select(func.sum(Activity.points))
            
            if activity_type:
                query = query.where(Activity.activity_type == activity_type)
            
            if start_date:
                query = query.where(Activity.date >= start_date)
            
            if end_date:
                query = query.where(Activity.date <= end_date)

            result = await self.session.execute(query)
            total = result.scalar()
            
            total_points = total or 0
            
            self._log_operation(
                "get_total_points",
                activity_type=activity_type,
                total_points=total_points
            )
            
            return total_points

        except Exception as e:
            self._log_error("get_total_points", e, activity_type=activity_type)
            return 0

    async def get_active_members_count(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Get count of members with activity in the given period."""
        try:
            query = select(func.count(func.distinct(Activity.member_id)))
            
            if start_date:
                query = query.where(Activity.date >= start_date)
            
            if end_date:
                query = query.where(Activity.date <= end_date)

            result = await self.session.execute(query)
            count = result.scalar() or 0
            
            self._log_operation(
                "get_active_members_count",
                count=count
            )
            
            return count

        except Exception as e:
            self._log_error("get_active_members_count", e)
            return 0

    async def get_member_activity_summary(
        self, member_id: int, days: int = 30
    ) -> dict[str, any]:
        """Get comprehensive activity summary for a member (optimized single query)."""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)

            # Single query to get all activity breakdown
            query = select(
                Activity.activity_type,
                func.sum(Activity.points).label("points"),
                func.count(Activity.member_id).label("sessions")
            ).where(
                Activity.member_id == member_id,
                Activity.date >= cutoff_date
            ).group_by(
                Activity.activity_type
            )

            result = await self.session.execute(query)
            
            breakdown = {}
            total_points = 0
            total_sessions = 0
            
            for row in result:
                points = row.points or 0
                sessions = row.sessions or 0
                breakdown[row.activity_type] = {
                    "points": points,
                    "sessions": sessions
                }
                total_points += points
                total_sessions += sessions

            summary = {
                "total_points": total_points,
                "total_sessions": total_sessions,
                "breakdown": breakdown,
                "period_days": days
            }

            self._log_operation(
                "get_member_activity_summary",
                member_id=member_id,
                days=days,
                total_points=total_points
            )

            return summary

        except Exception as e:
            self._log_error("get_member_activity_summary", e, member_id=member_id)
            return {
                "total_points": 0,
                "total_sessions": 0,
                "breakdown": {},
                "period_days": days
            }