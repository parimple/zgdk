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
                func.max(Invite.last_used_at).label("last_used")
            ).where(Invite.creator_id == creator_id)

            result = await self.session.execute(query)
            row = result.first()

            stats = {
                "total_invites": row.total_invites or 0,
                "total_uses": row.total_uses or 0,
                "first_invite": row.first_invite,
                "last_used": row.last_used
            }

            self._log_operation(
                "get_invite_stats",
                creator_id=creator_id,
                **stats
            )

            return stats

        except Exception as e:
            self._log_error("get_invite_stats", e, creator_id=creator_id)
            return {
                "total_invites": 0,
                "total_uses": 0,
                "first_invite": None,
                "last_used": None
            }

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

            invite = Invite(
                id=invite_code,
                creator_id=creator_id,
                uses=uses,
                created_at=created_at
            )

            self.session.add(invite)
            await self.session.flush()

            self._log_operation(
                "create_invite",
                invite_code=invite_code,
                creator_id=creator_id,
                uses=uses
            )

            return invite

        except Exception as e:
            self._log_error("create_invite", e, invite_code=invite_code)
            raise

    async def update_invite_usage(
        self,
        invite_code: str,
        new_uses: int,
        last_used_at: Optional[datetime] = None
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

            self._log_operation(
                "update_invite_usage",
                invite_code=invite_code,
                new_uses=new_uses
            )

            return True

        except Exception as e:
            self._log_error("update_invite_usage", e, invite_code=invite_code)
            return False

    async def get_invites_by_creator(self, creator_id: int) -> list[Invite]:
        """Get all invites created by a specific member."""
        try:
            query = select(Invite).where(
                Invite.creator_id == creator_id
            ).order_by(Invite.created_at.desc())

            result = await self.session.execute(query)
            invites = list(result.scalars().all())

            self._log_operation(
                "get_invites_by_creator",
                creator_id=creator_id,
                count=len(invites)
            )

            return invites

        except Exception as e:
            self._log_error("get_invites_by_creator", e, creator_id=creator_id)
            return []

    async def get_most_used_invites(self, limit: int = 10) -> list[Invite]:
        """Get invites with highest usage."""
        try:
            query = select(Invite).where(
                Invite.uses > 0
            ).order_by(
                Invite.uses.desc()
            ).limit(limit)

            result = await self.session.execute(query)
            invites = list(result.scalars().all())

            self._log_operation(
                "get_most_used_invites",
                limit=limit,
                count=len(invites)
            )

            return invites

        except Exception as e:
            self._log_error("get_most_used_invites", e)
            return []

    async def get_invite_leaderboard(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get invite leaderboard (optimized single query)."""
        try:
            # Single aggregated query
            query = select(
                Invite.creator_id,
                func.count(Invite.id).label("total_invites"),
                func.sum(Invite.uses).label("total_uses")
            ).group_by(
                Invite.creator_id
            ).order_by(
                func.sum(Invite.uses).desc()
            ).limit(limit)

            result = await self.session.execute(query)
            
            leaderboard = []
            for row in result:
                leaderboard.append({
                    "creator_id": row.creator_id,
                    "total_invites": row.total_invites or 0,
                    "total_uses": row.total_uses or 0
                })

            self._log_operation(
                "get_invite_leaderboard",
                limit=limit,
                count=len(leaderboard)
            )

            return leaderboard

        except Exception as e:
            self._log_error("get_invite_leaderboard", e)
            return []

    async def cleanup_unused_invites(self, days_old: int = 30) -> int:
        """Remove invites that haven't been used in specified days."""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(
                day=datetime.now(timezone.utc).day - days_old
            )

            # Find unused invites older than cutoff
            query = select(Invite).where(
                Invite.uses == 0,
                Invite.created_at < cutoff_date
            )

            result = await self.session.execute(query)
            old_invites = list(result.scalars().all())

            count = len(old_invites)

            # Delete them
            for invite in old_invites:
                await self.session.delete(invite)

            await self.session.flush()

            self._log_operation(
                "cleanup_unused_invites",
                days_old=days_old,
                cleaned=count
            )

            return count

        except Exception as e:
            self._log_error("cleanup_unused_invites", e)
            return 0

    async def get_by_code(self, invite_code: str) -> Optional[Invite]:
        """Get invite by code."""
        return await self.get_by_id(invite_code)