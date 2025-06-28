"""
Activity and ranking system queries for the database.

These are standalone functions for the activity/ranking system that don't belong to a specific model class.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Activity, Member

logger = logging.getLogger(__name__)


async def ensure_member_exists(session: AsyncSession, member_id: int) -> None:
    """Ensure member exists in the database."""
    result = await session.execute(select(Member).where(Member.id == member_id))
    if not result.scalar():
        new_member = Member(id=member_id)
        session.add(new_member)


async def add_activity_points(
    session: AsyncSession,
    member_id: int,
    activity_type: str,
    points: int,
    date: datetime = None,
) -> None:
    """Add points to member's activity for specific date and type."""
    if date is None:
        date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Check if activity record exists for this member, date and type
    activity = await session.get(Activity, (member_id, date, activity_type))

    if activity:
        activity.points += points
    else:
        activity = Activity(member_id=member_id, date=date, activity_type=activity_type, points=points)
        session.add(activity)


async def get_member_total_points(session: AsyncSession, member_id: int, days_back: int = 7) -> int:
    """Get total points for a member from last N days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    result = await session.execute(
        select(func.sum(Activity.points)).where(Activity.member_id == member_id).where(Activity.date >= cutoff_date)
    )
    total = result.scalar()
    return total or 0


async def get_top_members_by_points(
    session: AsyncSession, limit: int = 100, days_back: int = 7
) -> List[Tuple[int, int]]:
    """Get top members by total points from last N days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    result = await session.execute(
        select(Activity.member_id, func.sum(Activity.points).label("total_points"))
        .where(Activity.date >= cutoff_date)
        .group_by(Activity.member_id)
        .order_by(func.sum(Activity.points).desc())
        .limit(limit)
    )
    return result.all()


async def get_member_ranking_position(session: AsyncSession, member_id: int, days_back: int = 7) -> int:
    """Get member's ranking position (1-based)."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    # Get all members with their total points
    result = await session.execute(
        select(Activity.member_id, func.sum(Activity.points).label("total_points"))
        .where(Activity.date >= cutoff_date)
        .group_by(Activity.member_id)
        .order_by(func.sum(Activity.points).desc())
    )

    ranking = result.all()
    for position, (mid, points) in enumerate(ranking, 1):
        if mid == member_id:
            return position
    return 0  # Not found in ranking


async def reset_daily_activity_points(session: AsyncSession, activity_type: str = None) -> None:
    """Reset activity points for today. If activity_type is None, reset all types."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    if activity_type:
        await session.execute(
            update(Activity)
            .where(Activity.date == today)
            .where(Activity.activity_type == activity_type)
            .values(points=0)
        )
    else:
        await session.execute(update(Activity).where(Activity.date == today).values(points=0))


async def get_member_activity_breakdown(session: AsyncSession, member_id: int, days_back: int = 7) -> Dict[str, int]:
    """Get breakdown of points by activity type for a member."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    result = await session.execute(
        select(Activity.activity_type, func.sum(Activity.points).label("total_points"))
        .where(Activity.member_id == member_id)
        .where(Activity.date >= cutoff_date)
        .group_by(Activity.activity_type)
    )

    return {activity_type: total_points for activity_type, total_points in result.all()}


async def cleanup_old_activity_data(session: AsyncSession, days_to_keep: int = 30) -> int:
    """Remove activity data older than specified days. Returns number of deleted records."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

    result = await session.execute(delete(Activity).where(Activity.date < cutoff_date))
    return result.rowcount


async def get_activity_leaderboard_with_names(
    session: AsyncSession, limit: int = 100, days_back: int = 7
) -> List[Tuple[int, int, int]]:
    """Get leaderboard with member_id, points, and position."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    result = await session.execute(
        select(
            Activity.member_id,
            func.sum(Activity.points).label("total_points"),
            func.row_number().over(order_by=func.sum(Activity.points).desc()).label("position"),
        )
        .where(Activity.date >= cutoff_date)
        .group_by(Activity.member_id)
        .order_by(func.sum(Activity.points).desc())
        .limit(limit)
    )
    return result.all()


async def get_ranking_tier(session: AsyncSession, member_id: int, days_back: int = 7) -> str:
    """Get ranking tier for member (100, 200, 300, or None)."""
    position = await get_member_ranking_position(session, member_id, days_back)

    if position == 0:
        return "Unranked"
    elif position <= 100:
        return "100"
    elif position <= 200:
        return "200"
    elif position <= 300:
        return "300"
    else:
        return "Unranked"
