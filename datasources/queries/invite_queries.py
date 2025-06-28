"""
Invite-related database queries.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import and_, asc, case, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Invite, Member

logger = logging.getLogger(__name__)


class InviteQueries:
    """Class for Invite Queries"""

    @staticmethod
    async def add_or_update_invite(
        session: AsyncSession,
        invite_id: str,
        creator_id: Optional[int],
        uses: int,
        created_at: datetime,
        last_used_at: Optional[datetime] = None,
    ) -> Invite:
        try:
            # Import here to avoid circular imports
            from .member_queries import MemberQueries

            if creator_id:
                await MemberQueries.get_or_add_member(session, creator_id)
            invite = await session.get(Invite, invite_id)
            if invite is None:
                invite = Invite(
                    id=invite_id,
                    creator_id=creator_id,
                    uses=uses,
                    created_at=created_at,
                    last_used_at=last_used_at,
                )
                session.add(invite)
            else:
                # Update existing invite
                if creator_id is not None:  # Only update if new creator_id is not None
                    invite.creator_id = creator_id
                invite.uses = uses
                if last_used_at is not None:
                    invite.last_used_at = last_used_at
            await session.flush()
            return invite
        except IntegrityError as e:
            logger.error(f"Error adding or updating invite {invite_id}: {str(e)}")
            await session.rollback()
            return None

    @staticmethod
    async def get_inactive_invites(
        session: AsyncSession,
        days: int = 30,
        max_uses: int = 5,
        limit: int = 100,
        sort_by: str = "uses",
        order: str = "asc",
    ) -> List[Invite]:
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=days)

        query = select(Invite).where(and_(Invite.last_used_at < cutoff_date, Invite.uses <= max_uses))

        if sort_by == "uses":
            query = query.order_by(Invite.uses.asc() if order == "asc" else Invite.uses.desc())
        elif sort_by == "last_used_at":
            query = query.order_by(Invite.last_used_at.asc() if order == "asc" else Invite.last_used_at.desc())
        else:
            query = query.order_by(Invite.uses.asc(), Invite.last_used_at.asc())

        query = query.limit(limit)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def delete_invite(session: AsyncSession, invite_id: str) -> None:
        invite = await session.get(Invite, invite_id)
        if invite:
            await session.delete(invite)
            await session.flush()

    @staticmethod
    async def get_invite_count(session: AsyncSession) -> int:
        result = await session.execute(select(func.count()).select_from(Invite))
        return result.scalar_one()

    @staticmethod
    async def get_sorted_invites(session: AsyncSession, sort_by: str = "uses", order: str = "desc") -> List[Invite]:
        query = select(Invite)
        if sort_by == "uses":
            query = query.order_by(desc(Invite.uses) if order == "desc" else asc(Invite.uses))
        elif sort_by == "created_at":
            query = query.order_by(desc(Invite.created_at) if order == "desc" else asc(Invite.created_at))

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_all_invites(session: AsyncSession) -> List[Invite]:
        result = await session.execute(select(Invite))
        return result.scalars().all()

    @staticmethod
    async def get_invites_for_cleanup(
        session: AsyncSession,
        limit: int = 100,
        inactive_threshold: timedelta = timedelta(days=1),
    ) -> List[Invite]:
        now = datetime.now(timezone.utc)
        threshold_date = now - inactive_threshold

        query = (
            select(Invite)
            .where(
                or_(
                    and_(
                        Invite.last_used_at.is_(None),
                        Invite.created_at < threshold_date,
                    ),
                    Invite.last_used_at.isnot(None),
                )
            )
            .order_by(
                case(
                    (
                        and_(
                            Invite.last_used_at.is_(None),
                            Invite.created_at < threshold_date,
                        ),
                        0,
                    ),
                    else_=1,
                ),
                Invite.last_used_at.asc().nulls_first(),
                Invite.created_at.asc(),
            )
            .limit(limit)
        )

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_member_invite_count(session: AsyncSession, member_id: int) -> int:
        """Get total count of invites (uses) for a specific member."""
        try:
            query = select(func.sum(Invite.uses)).where(Invite.creator_id == member_id)
            result = await session.execute(query)
            count = result.scalar()
            return count if count is not None else 0
        except Exception as e:
            logger.error(f"Error getting invite count for member {member_id}: {e}")
            return 0

    @staticmethod
    async def get_member_valid_invite_count(session: AsyncSession, member_id: int, guild, min_days: int = 7) -> int:
        """
        Get count of valid invites for a specific member (like in legacy system).
        Only counts users who:
        - Are still on the server
        - Have an avatar
        - Have joined_at timestamp
        - Account age difference (joined_at - created_at) > min_days

        :param session: Database session
        :param member_id: ID of the member whose invites to count
        :param guild: Discord guild object
        :param min_days: Minimum account age difference in days (default 7)
        :return: Count of valid invites
        """
        try:
            # Get all members invited by this user from database
            query = select(Member).where(Member.current_inviter_id == member_id)
            result = await session.execute(query)
            invited_members = result.scalars().all()

            valid_count = 0

            for db_member in invited_members:
                # Get Discord member object
                discord_member = guild.get_member(db_member.id)

                if not discord_member:
                    # User is no longer on the server
                    continue

                if not discord_member.avatar:
                    # User has no avatar
                    continue

                if not discord_member.joined_at:
                    # No joined_at timestamp
                    continue

                # Check account age difference
                account_age_diff = discord_member.joined_at - discord_member.created_at
                if account_age_diff <= timedelta(days=min_days):
                    # Account too new (potential bot/fake account)
                    continue

                valid_count += 1

            logger.debug(
                f"Valid invite count for member {member_id}: {valid_count} (from {len(invited_members)} total)"
            )
            return valid_count

        except Exception as e:
            logger.error(f"Error getting valid invite count for member {member_id}: {e}")
            return 0
