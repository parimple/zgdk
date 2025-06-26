"""
Member queries for the database.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Member

logger = logging.getLogger(__name__)


class MemberQueries:
    """Class for Member Queries"""

    @staticmethod
    async def get_or_add_member(
        session: AsyncSession,
        member_id: int,
        wallet_balance: int = 0,
        first_inviter_id: Optional[int] = None,
        current_inviter_id: Optional[int] = None,
        joined_at: Optional[datetime] = None,
        rejoined_at: Optional[datetime] = None,
    ) -> Member:
        """Get a Member by ID, or add a new one if it doesn't exist"""
        member = await session.get(Member, member_id)
        if member is None:
            member = Member(
                id=member_id,
                wallet_balance=wallet_balance,
                first_inviter_id=first_inviter_id,
                current_inviter_id=current_inviter_id,
                joined_at=joined_at,
                rejoined_at=rejoined_at,
            )
            session.add(member)
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                member = await session.get(Member, member_id)
                if member is None:
                    logger.error(
                        f"Failed to add or retrieve member with ID {member_id}"
                    )
                    raise

        # Update fields for existing members
        if current_inviter_id is not None:
            member.current_inviter_id = current_inviter_id
        if rejoined_at is not None:
            member.rejoined_at = rejoined_at

        return member

    @staticmethod
    async def add_to_wallet_balance(
        session: AsyncSession, member_id: int, amount: int
    ) -> None:
        """Add to the wallet balance of a Member"""
        from sqlalchemy import update
        await session.execute(
            update(Member)
            .where(Member.id == member_id)
            .values(wallet_balance=Member.wallet_balance + amount)
        )

    @staticmethod
    async def extend_voice_bypass(
        session: AsyncSession, member_id: int, duration: timedelta
    ) -> Optional[datetime]:
        """
        Extend the voice bypass duration for a member.
        If member has no active bypass, starts from now.
        If member has active bypass, extends from current expiration.
        Returns the new expiration datetime or None if failed.
        """
        try:
            member = await MemberQueries.get_or_add_member(session, member_id)
            now = datetime.now(timezone.utc)

            if member.voice_bypass_until is None or member.voice_bypass_until < now:
                member.voice_bypass_until = now + duration
            else:
                member.voice_bypass_until += duration

            await session.flush()
            return member.voice_bypass_until
        except Exception as e:
            logger.error(
                f"Failed to extend voice bypass for member {member_id}: {str(e)}"
            )
            return None

    @staticmethod
    async def get_voice_bypass_status(
        session: AsyncSession, member_id: int
    ) -> Optional[datetime]:
        """
        Get the current voice bypass expiration datetime for a member.
        Returns None if member has no bypass or if it's expired.
        """
        member = await session.get(Member, member_id)
        if not member or not member.voice_bypass_until:
            return None

        now = datetime.now(timezone.utc)
        return member.voice_bypass_until if member.voice_bypass_until > now else None

    @staticmethod
    async def clear_voice_bypass(session: AsyncSession, member_id: int) -> bool:
        """
        Clear the voice bypass for a member.
        Returns True if successful, False otherwise.
        """
        try:
            member = await session.get(Member, member_id)
            if member:
                member.voice_bypass_until = None
                await session.flush()
                return True
            return False
        except Exception as e:
            logger.error(
                f"Failed to clear voice bypass for member {member_id}: {str(e)}"
            )
            return False

    @staticmethod
    async def add_bypass_time(
        session: AsyncSession, user_id: int, hours: int
    ) -> Optional[Member]:
        """Add bypass time to a member"""
        member = await session.get(Member, user_id)
        if not member:
            return None

        now = datetime.now(timezone.utc)
        if not member.voice_bypass_until or member.voice_bypass_until < now:
            member.voice_bypass_until = now + timedelta(hours=hours)
        else:
            member.voice_bypass_until += timedelta(hours=hours)

        return member

    @staticmethod
    async def set_voice_bypass_status(
        session: AsyncSession, member_id: int, expiration: datetime
    ) -> Optional[Member]:
        """
        Set the voice bypass status for a member.
        Args:
            session: The database session
            member_id: The ID of the member
            expiration: The expiration datetime for the bypass
        Returns:
            The updated Member object or None if failed
        """
        try:
            member = await MemberQueries.get_or_add_member(session, member_id)
            member.voice_bypass_until = expiration
            await session.flush()
            return member
        except Exception as e:
            logger.error(
                f"Failed to set voice bypass status for member {member_id}: {str(e)}"
            )
            return None