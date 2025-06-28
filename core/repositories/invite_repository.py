"""Invite repository implementation for invite tracking operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.base_repository import BaseRepository
from datasources.models import Invite, Member


class InviteRepository(BaseRepository):
    """Repository for invite tracking operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Invite, session)

    async def get_invite_stats(self, creator_id: int) -> dict[str, Any]:
        """Get invite statistics for a creator (optimized single query)."""
        try:
            # Single query to get all invite stats
            query = select(
                func.count(Invite.id).label("total_invites"),
                func.sum(Invite.uses).label("total_uses"),
                func.min(Invite.created_at).label("first_invite"),
                func.max(Invite.last_used_at).label("last_used"),
            ).where(Invite.creator_id == creator_id)

            result = await self.session.execute(query)
            row = result.first()

            stats = {
                "total_invites": row.total_invites or 0,
                "total_uses": row.total_uses or 0,
                "first_invite": row.first_invite,
                "last_used": row.last_used,
            }

            self._log_operation("get_invite_stats", creator_id=creator_id, **stats)

            return stats

        except Exception as e:
            self._log_error("get_invite_stats", e, creator_id=creator_id)
            return {"total_invites": 0, "total_uses": 0, "first_invite": None, "last_used": None}

    async def create_invite(
        self,
        invite_code: str,
        creator_id: int,
        uses: int = 0,
        created_at: Optional[datetime] = None,
    ) -> Invite:
        """Create a new invite record."""
        try:
            if created_at is None:
                created_at = datetime.now(timezone.utc)

            invite = Invite(id=invite_code, creator_id=creator_id, uses=uses, created_at=created_at)

            self.session.add(invite)
            await self.session.flush()

            self._log_operation("create_invite", invite_code=invite_code, creator_id=creator_id, uses=uses)

            return invite

        except Exception as e:
            self._log_error("create_invite", e, invite_code=invite_code)
            raise

    async def update_invite_usage(
        self, invite_code: str, new_uses: int, last_used_at: Optional[datetime] = None
    ) -> bool:
        """Update invite usage count and last used timestamp."""
        try:
            invite = await self.get_by_id(invite_code)
            if not invite:
                return False

            invite.uses = new_uses
            if last_used_at:
                invite.last_used_at = last_used_at
            else:
                invite.last_used_at = datetime.now(timezone.utc)

            await self.session.flush()

            self._log_operation("update_invite_usage", invite_code=invite_code, new_uses=new_uses)

            return True

        except Exception as e:
            self._log_error("update_invite_usage", e, invite_code=invite_code)
            return False

    async def get_invites_by_creator(self, creator_id: int) -> list[Invite]:
        """Get all invites created by a specific member."""
        try:
            query = select(Invite).where(Invite.creator_id == creator_id).order_by(Invite.created_at.desc())

            result = await self.session.execute(query)
            invites = list(result.scalars().all())

            self._log_operation("get_invites_by_creator", creator_id=creator_id, count=len(invites))

            return invites

        except Exception as e:
            self._log_error("get_invites_by_creator", e, creator_id=creator_id)
            return []

    async def get_most_used_invites(self, limit: int = 10) -> list[Invite]:
        """Get invites with highest usage."""
        try:
            query = select(Invite).where(Invite.uses > 0).order_by(Invite.uses.desc()).limit(limit)

            result = await self.session.execute(query)
            invites = list(result.scalars().all())

            self._log_operation("get_most_used_invites", limit=limit, count=len(invites))

            return invites

        except Exception as e:
            self._log_error("get_most_used_invites", e)
            return []

    async def get_invite_leaderboard(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get invite leaderboard (optimized single query)."""
        try:
            # Single aggregated query
            query = (
                select(
                    Invite.creator_id,
                    func.count(Invite.id).label("total_invites"),
                    func.sum(Invite.uses).label("total_uses"),
                )
                .group_by(Invite.creator_id)
                .order_by(func.sum(Invite.uses).desc())
                .limit(limit)
            )

            result = await self.session.execute(query)

            leaderboard = []
            for row in result:
                leaderboard.append(
                    {
                        "creator_id": row.creator_id,
                        "total_invites": row.total_invites or 0,
                        "total_uses": row.total_uses or 0,
                    }
                )

            self._log_operation("get_invite_leaderboard", limit=limit, count=len(leaderboard))

            return leaderboard

        except Exception as e:
            self._log_error("get_invite_leaderboard", e)
            return []

    async def cleanup_unused_invites(self, days_old: int = 30) -> int:
        """Remove invites that haven't been used in specified days."""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(day=datetime.now(timezone.utc).day - days_old)

            # Find unused invites older than cutoff
            query = select(Invite).where(Invite.uses == 0, Invite.created_at < cutoff_date)

            result = await self.session.execute(query)
            old_invites = list(result.scalars().all())

            count = len(old_invites)

            # Delete them
            for invite in old_invites:
                await self.session.delete(invite)

            await self.session.flush()

            self._log_operation("cleanup_unused_invites", days_old=days_old, cleaned=count)

            return count

        except Exception as e:
            self._log_error("cleanup_unused_invites", e)
            return 0

    async def get_by_code(self, invite_code: str) -> Optional[Invite]:
        """Get invite by code."""
        return await self.get_by_id(invite_code)

    async def add_or_update_invite(
        self,
        invite_id: str,
        creator_id: Optional[int],
        uses: int,
        created_at: datetime,
        last_used_at: Optional[datetime] = None,
    ) -> Optional[Invite]:
        """Add or update an invite."""
        try:
            # Get or create creator member if provided
            if creator_id:
                from .member_repository import MemberRepository

                member_repo = MemberRepository(self.session)
                await member_repo.get_or_create(creator_id)

            invite = await self.get_by_id(invite_id)
            if invite is None:
                invite = Invite(
                    id=invite_id,
                    creator_id=creator_id,
                    uses=uses,
                    created_at=created_at,
                    last_used_at=last_used_at,
                )
                self.session.add(invite)
            else:
                # Update existing invite
                if creator_id is not None:  # Only update if new creator_id is not None
                    invite.creator_id = creator_id
                invite.uses = uses
                if last_used_at is not None:
                    invite.last_used_at = last_used_at

            await self.session.flush()

            self._log_operation("add_or_update_invite", invite_id=invite_id, creator_id=creator_id, uses=uses)

            return invite

        except Exception as e:
            self._log_error("add_or_update_invite", e, invite_id=invite_id)
            await self.session.rollback()
            return None

    async def get_inactive_invites(
        self,
        days: int = 30,
        max_uses: int = 5,
        limit: int = 100,
        sort_by: str = "uses",
        order: str = "asc",
    ) -> list[Invite]:
        """Get inactive invites based on criteria."""
        try:
            from datetime import timedelta

            now = datetime.now(timezone.utc)
            cutoff_date = now - timedelta(days=days)

            query = select(Invite).where(Invite.last_used_at < cutoff_date, Invite.uses <= max_uses)

            if sort_by == "uses":
                query = query.order_by(Invite.uses.asc() if order == "asc" else Invite.uses.desc())
            elif sort_by == "last_used_at":
                query = query.order_by(Invite.last_used_at.asc() if order == "asc" else Invite.last_used_at.desc())
            else:
                query = query.order_by(Invite.uses.asc(), Invite.last_used_at.asc())

            query = query.limit(limit)

            result = await self.session.execute(query)
            invites = list(result.scalars().all())

            self._log_operation("get_inactive_invites", days=days, max_uses=max_uses, count=len(invites))

            return invites

        except Exception as e:
            self._log_error("get_inactive_invites", e)
            return []

    async def delete_invite(self, invite_id: str) -> bool:
        """Delete an invite by ID."""
        try:
            invite = await self.get_by_id(invite_id)
            if invite:
                await self.session.delete(invite)
                await self.session.flush()

                self._log_operation("delete_invite", invite_id=invite_id)
                return True
            return False

        except Exception as e:
            self._log_error("delete_invite", e, invite_id=invite_id)
            return False

    async def get_invite_count(self) -> int:
        """Get total count of invites."""
        try:
            result = await self.session.execute(select(func.count()).select_from(Invite))
            count = result.scalar_one()

            self._log_operation("get_invite_count", count=count)
            return count

        except Exception as e:
            self._log_error("get_invite_count", e)
            return 0

    async def get_sorted_invites(self, sort_by: str = "uses", order: str = "desc") -> list[Invite]:
        """Get all invites sorted by specified field."""
        try:
            from sqlalchemy import asc, desc

            query = select(Invite)
            if sort_by == "uses":
                query = query.order_by(desc(Invite.uses) if order == "desc" else asc(Invite.uses))
            elif sort_by == "created_at":
                query = query.order_by(desc(Invite.created_at) if order == "desc" else asc(Invite.created_at))

            result = await self.session.execute(query)
            invites = list(result.scalars().all())

            self._log_operation("get_sorted_invites", sort_by=sort_by, order=order, count=len(invites))

            return invites

        except Exception as e:
            self._log_error("get_sorted_invites", e)
            return []

    async def get_all_invites(self) -> list[Invite]:
        """Get all invites."""
        try:
            result = await self.session.execute(select(Invite))
            invites = list(result.scalars().all())

            self._log_operation("get_all_invites", count=len(invites))
            return invites

        except Exception as e:
            self._log_error("get_all_invites", e)
            return []

    async def get_invites_for_cleanup(
        self,
        limit: int = 100,
        inactive_threshold_days: int = 1,
    ) -> list[Invite]:
        """Get invites that should be cleaned up."""
        try:
            from datetime import timedelta

            from sqlalchemy import and_, case, or_

            now = datetime.now(timezone.utc)
            threshold_date = now - timedelta(days=inactive_threshold_days)

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

            result = await self.session.execute(query)
            invites = list(result.scalars().all())

            self._log_operation(
                "get_invites_for_cleanup", limit=limit, threshold_days=inactive_threshold_days, count=len(invites)
            )

            return invites

        except Exception as e:
            self._log_error("get_invites_for_cleanup", e)
            return []

    async def get_member_invite_count(self, member_id: int) -> int:
        """Get total count of invites (uses) for a specific member."""
        try:
            query = select(func.sum(Invite.uses)).where(Invite.creator_id == member_id)
            result = await self.session.execute(query)
            count = result.scalar()

            final_count = count if count is not None else 0

            self._log_operation("get_member_invite_count", member_id=member_id, count=final_count)

            return final_count

        except Exception as e:
            self._log_error("get_member_invite_count", e, member_id=member_id)
            return 0

    async def get_member_valid_invite_count(self, member_id: int, guild, min_days: int = 7) -> int:
        """
        Get count of valid invites for a specific member.
        Only counts users who:
        - Are still on the server
        - Have an avatar
        - Have joined_at timestamp
        - Account age difference (joined_at - created_at) > min_days
        """
        try:
            from datetime import timedelta

            # Get all members invited by this user from database
            query = select(Member).where(Member.current_inviter_id == member_id)
            result = await self.session.execute(query)
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

            self._log_operation(
                "get_member_valid_invite_count",
                member_id=member_id,
                total_invited=len(invited_members),
                valid_count=valid_count,
            )

            return valid_count

        except Exception as e:
            self._log_error("get_member_valid_invite_count", e, member_id=member_id)
            return 0
