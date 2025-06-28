"""Member repository for core member operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.base_repository import BaseRepository
from datasources.models import Member


class MemberRepository(BaseRepository):
    """Repository for member data operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Member, session)

    async def get_by_discord_id(self, discord_id: int) -> Optional[Member]:
        """Get member by Discord ID."""
        try:
            result = await self.session.execute(select(Member).where(Member.id == discord_id))
            return result.scalar_one_or_none()
        except Exception as e:
            self._log_error("get_by_discord_id", e, discord_id=discord_id)
            return None

    async def get_or_create(self, discord_id: int, **kwargs) -> Member:
        """Get existing member or create new one."""
        try:
            # Try to get existing member
            member = await self.get_by_discord_id(discord_id)
            if member:
                return member

            # Create new member if not found
            return await self.create_member(
                discord_id=discord_id,
                first_inviter_id=kwargs.get("first_inviter_id"),
                current_inviter_id=kwargs.get("current_inviter_id"),
                joined_at=kwargs.get("joined_at"),
            )

        except Exception as e:
            self._log_error("get_or_create", e, discord_id=discord_id)
            raise

    async def get_all(self) -> list[Member]:
        """Get all members."""
        try:
            result = await self.session.execute(select(Member))
            return list(result.scalars().all())
        except Exception as e:
            self._log_error("get_all", e)
            return []

    async def create_member(
        self,
        discord_id: int,
        first_inviter_id: Optional[int] = None,
        current_inviter_id: Optional[int] = None,
        joined_at: Optional[datetime] = None,
    ) -> Member:
        """Create a new member."""
        try:
            if joined_at is None:
                joined_at = datetime.now(timezone.utc)

            member = Member(
                id=discord_id,
                first_inviter_id=first_inviter_id,
                current_inviter_id=current_inviter_id,
                joined_at=joined_at,
                wallet_balance=0,
            )

            self.session.add(member)
            await self.session.flush()
            await self.session.refresh(member)

            self._log_operation(
                "create_member",
                discord_id=discord_id,
                first_inviter_id=first_inviter_id,
                current_inviter_id=current_inviter_id,
            )

            return member

        except Exception as e:
            self._log_error("create_member", e, discord_id=discord_id)
            raise

    async def update_wallet_balance(self, member_id: int, new_balance: int) -> bool:
        """Update member's wallet balance."""
        try:
            member = await self.get_by_id(member_id)
            if not member:
                return False

            member.wallet_balance = new_balance
            await self.session.flush()

            self._log_operation(
                "update_wallet_balance",
                member_id=member_id,
                new_balance=new_balance,
            )

            return True

        except Exception as e:
            self._log_error("update_wallet_balance", e, member_id=member_id)
            return False

    async def update_voice_bypass(self, member_id: int, voice_bypass_until: Optional[datetime]) -> bool:
        """Update member's voice bypass expiration."""
        try:
            member = await self.get_by_id(member_id)
            if not member:
                return False

            member.voice_bypass_until = voice_bypass_until
            await self.session.flush()

            self._log_operation(
                "update_voice_bypass",
                member_id=member_id,
                voice_bypass_until=voice_bypass_until,
            )

            return True

        except Exception as e:
            self._log_error("update_voice_bypass", e, member_id=member_id)
            return False

    async def update_inviter(self, member_id: int, inviter_id: Optional[int], update_current: bool = True) -> bool:
        """Update member's inviter information."""
        try:
            member = await self.get_by_id(member_id)
            if not member:
                return False

            if update_current:
                member.current_inviter_id = inviter_id

            # Set first inviter if not already set
            if member.first_inviter_id is None and inviter_id is not None:
                member.first_inviter_id = inviter_id

            await self.session.flush()

            self._log_operation(
                "update_inviter",
                member_id=member_id,
                inviter_id=inviter_id,
                update_current=update_current,
            )

            return True

        except Exception as e:
            self._log_error("update_inviter", e, member_id=member_id)
            return False

    async def get_members_by_inviter(self, inviter_id: int) -> list[Member]:
        """Get all members invited by a specific inviter."""
        try:
            result = await self.session.execute(select(Member).where(Member.current_inviter_id == inviter_id))
            return list(result.scalars().all())
        except Exception as e:
            self._log_error("get_members_by_inviter", e, inviter_id=inviter_id)
            return []

    async def get_member_count(self) -> int:
        """Get total number of members."""
        try:
            result = await self.session.execute(select(func.count(Member.id)))
            return result.scalar() or 0
        except Exception as e:
            self._log_error("get_member_count", e)
            return 0

    async def get_invite_leaderboard_optimized(self, limit: int = 10) -> list[dict]:
        """Get invite leaderboard with single optimized query."""
        try:
            # Use aliased table to avoid confusion
            from sqlalchemy.orm import aliased

            inviter = aliased(Member)
            invited = aliased(Member)

            # Count how many members each inviter has invited
            result = await self.session.execute(
                select(inviter.id.label("inviter_id"), func.count(invited.id).label("invite_count"))
                .select_from(inviter)
                .join(
                    invited,
                    invited.current_inviter_id == inviter.id,
                    isouter=True,  # Left join to include inviters with 0 invites
                )
                .group_by(inviter.id)
                .having(func.count(invited.id) > 0)  # Only include those who have invited someone
                .order_by(func.count(invited.id).desc())
                .limit(limit)
            )

            # Convert to list of dicts
            leaderboard = []
            for row in result:
                leaderboard.append({"member_id": row.inviter_id, "invite_count": row.invite_count})

            return leaderboard

        except Exception as e:
            self._log_error("get_invite_leaderboard_optimized", e)
            return []
