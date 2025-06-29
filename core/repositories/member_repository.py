"""Member repository implementations for database operations."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Interfaces are now Protocols - no need to import for inheritance
from core.repositories.base_repository import BaseRepository
from datasources.models import Activity, AutoKick, Invite, Member, ModerationLog


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

            old_balance = member.wallet_balance
            member.wallet_balance = new_balance
            await self.session.flush()

            self._log_operation(
                "update_wallet_balance",
                member_id=member_id,
                old_balance=old_balance,
                new_balance=new_balance,
            )

            return True

        except Exception as e:
            self._log_error("update_wallet_balance", e, member_id=member_id)
            return False

    async def update_voice_bypass(self, member_id: int, bypass_until: Optional[datetime]) -> bool:
        """Update member's voice bypass expiration."""
        try:
            member = await self.get_by_id(member_id)
            if not member:
                return False

            member.voice_bypass_until = bypass_until
            await self.session.flush()

            self._log_operation(
                "update_voice_bypass",
                member_id=member_id,
                bypass_until=bypass_until,
            )

            return True

        except Exception as e:
            self._log_error("update_voice_bypass", e, member_id=member_id)
            return False

    async def update_inviter(self, member_id: int, new_inviter_id: Optional[int], update_current: bool = True) -> bool:
        """Update member's inviter (current or first)."""
        try:
            member = await self.get_by_id(member_id)
            if not member:
                return False

            if update_current:
                member.current_inviter_id = new_inviter_id
            else:
                # Only set first inviter if it's not already set
                if member.first_inviter_id is None:
                    member.first_inviter_id = new_inviter_id

            await self.session.flush()

            self._log_operation(
                "update_inviter",
                member_id=member_id,
                new_inviter_id=new_inviter_id,
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
        """Get total member count."""
        try:
            result = await self.session.execute(select(func.count(Member.id)))
            return result.scalar() or 0

        except Exception as e:
            self._log_error("get_member_count", e)
            return 0

    async def get_or_add_member(
        self,
        member_id: int,
        wallet_balance: int = 0,
        first_inviter_id: Optional[int] = None,
        current_inviter_id: Optional[int] = None,
        joined_at: Optional[datetime] = None,
        rejoined_at: Optional[datetime] = None,
    ) -> Member:
        """Legacy compatibility method for MemberQueries.get_or_add_member."""
        try:
            member = await self.get_by_discord_id(member_id)
            if member is None:
                member = await self.create_member(
                    discord_id=member_id,
                    wallet_balance=wallet_balance,
                    first_inviter_id=first_inviter_id,
                    current_inviter_id=current_inviter_id,
                    joined_at=joined_at,
                    rejoined_at=rejoined_at,
                )
            else:
                # Update fields for existing members
                if current_inviter_id is not None:
                    member.current_inviter_id = current_inviter_id
                if rejoined_at is not None:
                    member.rejoined_at = rejoined_at
                await self.session.flush()

            return member

        except Exception as e:
            self._log_error("get_or_add_member", e, member_id=member_id)
            raise

    async def add_to_wallet_balance(self, member_id: int, amount: int) -> None:
        """Legacy compatibility method for MemberQueries.add_to_wallet_balance."""
        try:
            from sqlalchemy import update

            await self.session.execute(
                update(Member).where(Member.id == member_id).values(wallet_balance=Member.wallet_balance + amount)
            )
            await self.session.flush()

            self._log_operation("add_to_wallet_balance", member_id=member_id, amount=amount)

        except Exception as e:
            self._log_error("add_to_wallet_balance", e, member_id=member_id)
            raise

    async def get_voice_bypass_status(self, member_id: int) -> Optional[datetime]:
        """Get the current voice bypass expiration datetime for a member."""
        try:
            member = await self.get_by_discord_id(member_id)
            if not member or not member.voice_bypass_until:
                return None

            now = datetime.now(timezone.utc)
            return member.voice_bypass_until if member.voice_bypass_until > now else None

        except Exception as e:
            self._log_error("get_voice_bypass_status", e, member_id=member_id)
            return None

    async def add_bypass_time(self, member_id: int, hours: int) -> Optional[Member]:
        """Add bypass time to a member."""
        try:
            member = await self.get_by_discord_id(member_id)
            if not member:
                return None

            now = datetime.now(timezone.utc)
            if not member.voice_bypass_until or member.voice_bypass_until < now:
                member.voice_bypass_until = now + timedelta(hours=hours)
            else:
                member.voice_bypass_until += timedelta(hours=hours)

            await self.session.flush()

            self._log_operation(
                "add_bypass_time", member_id=member_id, hours=hours, new_expiry=member.voice_bypass_until
            )

            return member

        except Exception as e:
            self._log_error("add_bypass_time", e, member_id=member_id)
            return None

    async def extend_voice_bypass(self, member_id: int, duration: timedelta) -> Optional[datetime]:
        """Extend the voice bypass duration for a member."""
        try:
            member = await self.get_or_add_member(member_id)
            now = datetime.now(timezone.utc)

            if member.voice_bypass_until is None or member.voice_bypass_until < now:
                member.voice_bypass_until = now + duration
            else:
                member.voice_bypass_until += duration

            await self.session.flush()

            self._log_operation(
                "extend_voice_bypass", member_id=member_id, duration=str(duration), new_expiry=member.voice_bypass_until
            )

            return member.voice_bypass_until

        except Exception as e:
            self._log_error("extend_voice_bypass", e, member_id=member_id)
            return None

    async def clear_voice_bypass(self, member_id: int) -> bool:
        """Clear the voice bypass for a member."""
        try:
            member = await self.get_by_discord_id(member_id)
            if member:
                member.voice_bypass_until = None
                await self.session.flush()

                self._log_operation("clear_voice_bypass", member_id=member_id)
                return True
            return False

        except Exception as e:
            self._log_error("clear_voice_bypass", e, member_id=member_id)
            return False

    async def get_member(self, member_id: int) -> Optional[Member]:
        """Legacy compatibility method for MemberQueries.get_member."""
        return await self.get_by_discord_id(member_id)

    async def get_all_members(self) -> list[Member]:
        """Get all members from database."""
        return await self.get_all()


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
            return list(result.scalars().all())

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

            activity = Activity(
                member_id=member_id,
                points=points,
                activity_type=activity_type,
                date=date,
            )

            self.session.add(activity)
            await self.session.flush()
            await self.session.refresh(activity)

            # Reduced logging for frequent activity operations
            # self._log_operation(
            #     "add_activity",
            #     member_id=member_id,
            #     points=points,
            #     activity_type=activity_type,
            # )

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
            return result.scalar() or 0

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
        """Get activity leaderboard."""
        try:
            query = select(Member, func.sum(Activity.points).label("total_points")).join(Activity).group_by(Member.id)

            if activity_type:
                query = query.where(Activity.activity_type == activity_type)

            if start_date:
                query = query.where(Activity.date >= start_date)

            if end_date:
                query = query.where(Activity.date <= end_date)

            query = query.order_by(func.sum(Activity.points).desc()).limit(limit)

            result = await self.session.execute(query)
            return [(row.Member, row.total_points) for row in result.all()]

        except Exception as e:
            self._log_error("get_leaderboard", e)
            return []

    async def get_total_points(
        self,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Get total points across all members."""
        try:
            query = select(func.sum(Activity.points))

            if activity_type:
                query = query.where(Activity.activity_type == activity_type)

            if start_date:
                query = query.where(Activity.date >= start_date)

            if end_date:
                query = query.where(Activity.date <= end_date)

            result = await self.session.execute(query)
            return result.scalar() or 0

        except Exception as e:
            self._log_error("get_total_points", e)
            return 0

    async def get_active_members_count(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Get count of members who had activity in the period."""
        try:
            query = select(func.count(func.distinct(Activity.member_id)))

            if start_date:
                query = query.where(Activity.date >= start_date)

            if end_date:
                query = query.where(Activity.date <= end_date)

            result = await self.session.execute(query)
            return result.scalar() or 0

        except Exception as e:
            self._log_error("get_active_members_count", e)
            return 0


class InviteRepository(BaseRepository):
    """Repository for invite tracking operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Invite, session)

    async def get_by_code(self, invite_code: str) -> Optional[Invite]:
        """Get invite by code."""
        try:
            result = await self.session.execute(
                select(Invite).options(selectinload(Invite.creator)).where(Invite.id == invite_code)
            )
            return result.scalar_one_or_none()

        except Exception as e:
            self._log_error("get_by_code", e, invite_code=invite_code)
            return None

    async def create_invite(
        self,
        invite_code: str,
        creator_id: int,
        uses: int = 0,
        created_at: Optional[datetime] = None,
    ) -> Optional[Invite]:
        """Create new invite record."""
        try:
            # Check if creator exists in members table
            member_repo = MemberRepository(self.session)
            creator = await member_repo.get_by_discord_id(creator_id)

            if not creator:
                # Create the member first if they don't exist
                self._log_operation("create_invite_with_member", invite_code=invite_code, creator_id=creator_id)
                creator = await member_repo.get_or_create(creator_id)

            if created_at is None:
                created_at = datetime.now(timezone.utc)

            invite = Invite(
                id=invite_code,
                creator_id=creator_id,
                uses=uses,
                created_at=created_at,
            )

            self.session.add(invite)
            await self.session.flush()
            await self.session.refresh(invite)

            self._log_operation(
                "create_invite",
                invite_code=invite_code,
                creator_id=creator_id,
                uses=uses,
            )

            return invite

        except Exception as e:
            self._log_error("create_invite", e, invite_code=invite_code)
            raise

    async def update_invite_usage(
        self, invite_code: str, new_uses: int, last_used_at: Optional[datetime] = None
    ) -> bool:
        """Update invite usage statistics."""
        try:
            invite = await self.get_by_code(invite_code)
            if not invite:
                return False

            invite.uses = new_uses
            if last_used_at:
                invite.last_used_at = last_used_at

            await self.session.flush()

            self._log_operation(
                "update_invite_usage",
                invite_code=invite_code,
                new_uses=new_uses,
            )

            return True

        except Exception as e:
            self._log_error("update_invite_usage", e, invite_code=invite_code)
            return False

    async def get_member_invites(self, creator_id: int) -> list[Invite]:
        """Get all invites created by member."""
        try:
            result = await self.session.execute(
                select(Invite).where(Invite.creator_id == creator_id).order_by(Invite.created_at.desc())
            )
            return list(result.scalars().all())

        except Exception as e:
            self._log_error("get_member_invites", e, creator_id=creator_id)
            return []

    async def get_invite_stats(self, creator_id: int) -> dict[str, int]:
        """Get invite statistics for member."""
        try:
            # Get total invites created
            total_invites_result = await self.session.execute(
                select(func.count(Invite.id)).where(Invite.creator_id == creator_id)
            )
            total_invites = total_invites_result.scalar() or 0

            # Get total uses
            total_uses_result = await self.session.execute(
                select(func.sum(Invite.uses)).where(Invite.creator_id == creator_id)
            )
            total_uses = total_uses_result.scalar() or 0

            return {
                "total_invites": total_invites,
                "total_uses": total_uses,
            }

        except Exception as e:
            self._log_error("get_invite_stats", e, creator_id=creator_id)
            return {"total_invites": 0, "total_uses": 0}


class ModerationRepository(BaseRepository):
    """Repository for moderation log operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(ModerationLog, session)

    async def log_action(
        self,
        target_user_id: int,
        moderator_id: int,
        action_type: str,
        channel_id: int,
        mute_type: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        reason: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> ModerationLog:
        """Log moderation action."""
        try:
            log_entry = ModerationLog(
                target_user_id=target_user_id,
                moderator_id=moderator_id,
                action_type=action_type,
                channel_id=channel_id,
                mute_type=mute_type,
                duration_seconds=duration_seconds,
                reason=reason,
                expires_at=expires_at,
            )

            self.session.add(log_entry)
            await self.session.flush()
            await self.session.refresh(log_entry)

            self._log_operation(
                "log_action",
                target_user_id=target_user_id,
                moderator_id=moderator_id,
                action_type=action_type,
            )

            return log_entry

        except Exception as e:
            self._log_error("log_action", e, target_user_id=target_user_id)
            raise

    async def get_member_history(self, member_id: int, action_type: Optional[str] = None) -> list[ModerationLog]:
        """Get moderation history for member."""
        try:
            query = select(ModerationLog).where(ModerationLog.target_user_id == member_id)

            if action_type:
                query = query.where(ModerationLog.action_type == action_type)

            query = query.order_by(ModerationLog.created_at.desc())

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            self._log_error("get_member_history", e, member_id=member_id)
            return []

    async def get_active_mutes(
        self, member_id: Optional[int] = None, mute_type: Optional[str] = None
    ) -> list[ModerationLog]:
        """Get active mute records."""
        try:
            current_time = datetime.now(timezone.utc)
            query = select(ModerationLog).where(
                ModerationLog.action_type == "mute",
                ModerationLog.expires_at > current_time,
            )

            if member_id:
                query = query.where(ModerationLog.target_user_id == member_id)

            if mute_type:
                query = query.where(ModerationLog.mute_type == mute_type)

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            self._log_error("get_active_mutes", e)
            return []

    async def get_moderator_stats(self, moderator_id: int) -> dict[str, int]:
        """Get moderation statistics for moderator."""
        try:
            # Get counts by action type
            result = await self.session.execute(
                select(ModerationLog.action_type, func.count(ModerationLog.id).label("count"))
                .where(ModerationLog.moderator_id == moderator_id)
                .group_by(ModerationLog.action_type)
            )

            stats = {row.action_type: row.count for row in result.all()}

            # Ensure all action types are present
            for action in ["mute", "unmute", "kick", "ban"]:
                if action not in stats:
                    stats[action] = 0

            return stats

        except Exception as e:
            self._log_error("get_moderator_stats", e, moderator_id=moderator_id)
            return {"mute": 0, "unmute": 0, "kick": 0, "ban": 0}


class AutoKickRepository(BaseRepository):
    """Repository for auto-kick management."""

    def __init__(self, session: AsyncSession):
        super().__init__(AutoKick, session)

    async def get_autokick(self, owner_id: int, target_id: int) -> Optional[AutoKick]:
        """Get specific autokick setting."""
        try:
            result = await self.session.execute(
                select(AutoKick).where(
                    AutoKick.owner_id == owner_id,
                    AutoKick.target_id == target_id,
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            self._log_error("get_autokick", e, owner_id=owner_id, target_id=target_id)
            return None

    async def create_autokick(self, owner_id: int, target_id: int) -> AutoKick:
        """Create autokick setting."""
        try:
            autokick = AutoKick(owner_id=owner_id, target_id=target_id)

            self.session.add(autokick)
            await self.session.flush()
            await self.session.refresh(autokick)

            self._log_operation(
                "create_autokick",
                owner_id=owner_id,
                target_id=target_id,
            )

            return autokick

        except Exception as e:
            self._log_error("create_autokick", e, owner_id=owner_id)
            raise

    async def remove_autokick(self, owner_id: int, target_id: int) -> bool:
        """Remove autokick setting."""
        try:
            autokick = await self.get_autokick(owner_id, target_id)
            if not autokick:
                return False

            await self.session.delete(autokick)
            await self.session.flush()

            self._log_operation(
                "remove_autokick",
                owner_id=owner_id,
                target_id=target_id,
            )

            return True

        except Exception as e:
            self._log_error("remove_autokick", e, owner_id=owner_id)
            return False

    async def get_member_autokicks(self, owner_id: int) -> list[AutoKick]:
        """Get all autokick settings for member."""
        try:
            result = await self.session.execute(
                select(AutoKick).options(selectinload(AutoKick.target)).where(AutoKick.owner_id == owner_id)
            )
            return list(result.scalars().all())

        except Exception as e:
            self._log_error("get_member_autokicks", e, owner_id=owner_id)
            return []

    async def get_targets_for_autokick(self, target_id: int) -> list[AutoKick]:
        """Get all autokick settings targeting specific member."""
        try:
            result = await self.session.execute(
                select(AutoKick).options(selectinload(AutoKick.owner)).where(AutoKick.target_id == target_id)
            )
            return list(result.scalars().all())

        except Exception as e:
            self._log_error("get_targets_for_autokick", e, target_id=target_id)
            return []

    async def get_invite_leaderboard_optimized(self, limit: int = 10) -> list[dict]:
        """Get invite leaderboard with optimized single query (eliminates N+1 problem)."""
        try:
            # Single aggregated query that replaces N+1 pattern
            query = (
                select(
                    Member.id.label("member_id"),
                    Member.joined_at,
                    func.count(Invite.id).label("total_invites"),
                    func.sum(Invite.uses).label("total_uses"),
                    func.count(Member.current_inviter_id).label("members_invited"),
                )
                .select_from(Member)
                .outerjoin(
                    # Join with invites created by this member
                    Invite,
                    Member.id == Invite.creator_id,
                )
                .group_by(Member.id, Member.joined_at)
                .order_by(func.sum(Invite.uses).desc().nulls_last())
                .limit(limit)
            )

            result = await self.session.execute(query)

            leaderboard_data = []
            for row in result:
                leaderboard_data.append(
                    {
                        "member_id": row.member_id,
                        "total_invites": row.total_invites or 0,
                        "total_uses": row.total_uses or 0,
                        "members_invited": row.members_invited or 0,
                        "joined_at": row.joined_at,
                    }
                )

            self._log_operation("get_invite_leaderboard_optimized", limit=limit, count=len(leaderboard_data))
            return leaderboard_data

        except Exception as e:
            self._log_error("get_invite_leaderboard_optimized", e, limit=limit)
            return []

    async def get_activity_leaderboard_optimized(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Get activity leaderboard with optimized aggregated query."""
        try:
            cutoff_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)

            # Single aggregated query for activity leaderboard
            query = (
                select(
                    Activity.member_id,
                    func.sum(Activity.points).label("total_points"),
                    func.sum(func.case((Activity.activity_type == "voice", Activity.points), else_=0)).label(
                        "voice_points"
                    ),
                    func.sum(func.case((Activity.activity_type == "text", Activity.points), else_=0)).label(
                        "text_points"
                    ),
                    func.sum(func.case((Activity.activity_type == "bonus", Activity.points), else_=0)).label(
                        "bonus_points"
                    ),
                )
                .where(Activity.date >= cutoff_date)
                .group_by(Activity.member_id)
                .order_by(func.sum(Activity.points).desc())
                .limit(limit)
            )

            result = await self.session.execute(query)

            leaderboard_data = []
            for row in result:
                leaderboard_data.append(
                    {
                        "member_id": row.member_id,
                        "total_points": row.total_points or 0,
                        "voice_points": row.voice_points or 0,
                        "text_points": row.text_points or 0,
                        "bonus_points": row.bonus_points or 0,
                    }
                )

            self._log_operation(
                "get_activity_leaderboard_optimized", days=days, limit=limit, count=len(leaderboard_data)
            )
            return leaderboard_data

        except Exception as e:
            self._log_error("get_activity_leaderboard_optimized", e, days=days, limit=limit)
            return []
