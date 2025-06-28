"""
AutoKick-related database queries.
"""

import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AutoKick, Member

logger = logging.getLogger(__name__)


class AutoKickQueries:
    """Class for AutoKick Queries"""

    @staticmethod
    async def ensure_members_exist(session: AsyncSession, owner_id: int, target_id: int) -> None:
        """Ensure both owner and target exist in members table"""
        # Check if owner exists
        owner_exists = await session.scalar(select(Member.id).where(Member.id == owner_id))
        if not owner_exists:
            await session.merge(Member(id=owner_id))

        # Check if target exists
        target_exists = await session.scalar(select(Member.id).where(Member.id == target_id))
        if not target_exists:
            await session.merge(Member(id=target_id))

        await session.commit()

    @staticmethod
    async def add_autokick(session: AsyncSession, owner_id: int, target_id: int) -> None:
        """Add an autokick entry"""
        # Ensure both members exist
        await AutoKickQueries.ensure_members_exist(session, owner_id, target_id)

        # Add autokick entry
        autokick = AutoKick(
            owner_id=owner_id,
            target_id=target_id,
            created_at=datetime.now(timezone.utc),
        )
        session.add(autokick)
        await session.commit()

    @staticmethod
    async def remove_autokick(session: AsyncSession, owner_id: int, target_id: int) -> None:
        """Remove an autokick entry"""
        await session.execute(
            delete(AutoKick).where((AutoKick.owner_id == owner_id) & (AutoKick.target_id == target_id))
        )
        await session.commit()

    @staticmethod
    async def get_all_autokicks(session: AsyncSession) -> List[AutoKick]:
        """Get all autokick entries"""
        result = await session.execute(select(AutoKick))
        return result.scalars().all()

    @staticmethod
    async def get_owner_autokicks(session: AsyncSession, owner_id: int) -> List[AutoKick]:
        """Get all autokicks for a specific owner"""
        result = await session.execute(select(AutoKick).where(AutoKick.owner_id == owner_id))
        return result.scalars().all()

    @staticmethod
    async def get_target_autokicks(session: AsyncSession, target_id: int) -> List[AutoKick]:
        """Get all autokicks targeting a specific member"""
        result = await session.execute(select(AutoKick).where(AutoKick.target_id == target_id))
        return result.scalars().all()
