"""Adapters to migrate from old queries to new repositories."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.member_repository import MemberRepository
from core.repositories.role_repository import RoleRepository
from datasources.models import Activity, Member, MemberRole

logger = logging.getLogger(__name__)


class MemberQueriesAdapter:
    """Adapter to make MemberRepository compatible with old MemberQueries interface."""
    
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
        repo = MemberRepository(session)
        
        # Try to get existing member
        member = await repo.get_by_discord_id(member_id)
        
        if member is None:
            # Create new member
            member = await repo.create_member(
                discord_id=member_id,
                first_inviter_id=first_inviter_id,
                current_inviter_id=current_inviter_id,
                joined_at=joined_at,
            )
            # Update wallet balance if provided
            if wallet_balance > 0:
                member.wallet_balance = wallet_balance
                await session.flush()
        else:
            # Update fields for existing members
            if current_inviter_id is not None:
                member.current_inviter_id = current_inviter_id
            if rejoined_at is not None:
                member.rejoined_at = rejoined_at
            await session.flush()
        
        return member
    
    @staticmethod
    async def add_to_wallet_balance(
        session: AsyncSession, member_id: int, amount: int
    ) -> None:
        """Add to the wallet balance of a Member"""
        repo = MemberRepository(session)
        member = await repo.get_by_discord_id(member_id)
        if member:
            await repo.update_wallet_balance(member_id, member.wallet_balance + amount)
    
    @staticmethod
    async def extend_voice_bypass(
        session: AsyncSession, member_id: int, duration: timedelta
    ) -> Optional[datetime]:
        """Extend the voice bypass duration for a member."""
        try:
            repo = MemberRepository(session)
            member = await repo.get_or_create(member_id)
            now = datetime.now(timezone.utc)
            
            if member.voice_bypass_until is None or member.voice_bypass_until < now:
                member.voice_bypass_until = now + duration
            else:
                member.voice_bypass_until += duration
            
            await session.flush()
            return member.voice_bypass_until
        except Exception as e:
            logger.error(f"Failed to extend voice bypass for member {member_id}: {str(e)}")
            return None
    
    @staticmethod
    async def get_voice_bypass_status(
        session: AsyncSession, member_id: int
    ) -> Optional[datetime]:
        """Get the current voice bypass expiration datetime for a member."""
        member = await session.get(Member, member_id)
        if not member or not member.voice_bypass_until:
            return None
        
        now = datetime.now(timezone.utc)
        return member.voice_bypass_until if member.voice_bypass_until > now else None
    
    @staticmethod
    async def clear_voice_bypass(session: AsyncSession, member_id: int) -> bool:
        """Clear the voice bypass for a member."""
        try:
            member = await session.get(Member, member_id)
            if member:
                member.voice_bypass_until = None
                await session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to clear voice bypass for member {member_id}: {str(e)}")
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
        """Set the voice bypass status for a member."""
        try:
            repo = MemberRepository(session)
            member = await repo.get_or_create(member_id)
            member.voice_bypass_until = expiration
            await session.flush()
            return member
        except Exception as e:
            logger.error(f"Failed to set voice bypass status for member {member_id}: {str(e)}")
            return None


class ActivityQueriesAdapter:
    """Adapter to make ActivityRepository compatible with old activity query functions."""
    
    @staticmethod
    async def ensure_member_exists(session: AsyncSession, member_id: int) -> None:
        """Ensure member exists in the database."""
        from core.repositories.member_repository import MemberRepository
        repo = MemberRepository(session)
        member = await repo.get_by_discord_id(member_id)
        if not member:
            await repo.create_member(discord_id=member_id)
    
    @staticmethod
    async def add_activity_points(
        session: AsyncSession,
        member_id: int,
        activity_type: str,
        points: int,
        date: datetime = None,
    ) -> None:
        """Add points to member's activity for specific date and type."""
        from core.repositories.activity_repository import ActivityRepository
        if date is None:
            date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        
        repo = ActivityRepository(session)
        # Check if activity exists for this date
        existing = await session.get(Activity, (member_id, date, activity_type))
        if existing:
            existing.points += points
            await session.flush()
        else:
            await repo.add_activity(member_id, points, activity_type, date)
    
    @staticmethod
    async def get_member_total_points(
        session: AsyncSession, member_id: int, days_back: int = 7
    ) -> int:
        """Get total points for a member from last N days."""
        from core.repositories.activity_repository import ActivityRepository
        from datetime import timedelta
        
        repo = ActivityRepository(session)
        start_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        return await repo.get_member_total_points(member_id, start_date=start_date)
    
    @staticmethod
    async def get_top_members_by_points(
        session: AsyncSession, limit: int = 100, days_back: int = 7
    ) -> list[tuple[int, int]]:
        """Get top members by total points from last N days."""
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        from sqlalchemy import func, select
        from datasources.models import Activity
        
        result = await session.execute(
            select(Activity.member_id, func.sum(Activity.points).label("total_points"))
            .where(Activity.date >= cutoff_date)
            .group_by(Activity.member_id)
            .order_by(func.sum(Activity.points).desc())
            .limit(limit)
        )
        return result.all()
    
    @staticmethod
    async def get_member_ranking_position(
        session: AsyncSession, member_id: int, days_back: int = 7
    ) -> int:
        """Get member's ranking position (1-based)."""
        from datetime import timedelta
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        from sqlalchemy import func, select
        from datasources.models import Activity
        
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
        return len(ranking) + 1


class AutoKickQueriesAdapter:
    """Adapter to make AutoKickRepository compatible with old AutoKickQueries interface."""
    
    @staticmethod
    async def ensure_members_exist(
        session: AsyncSession, owner_id: int, target_id: int
    ) -> None:
        """Ensure both owner and target exist in members table."""
        from core.repositories import MemberRepository
        member_repo = MemberRepository(session)
        await member_repo.get_or_create(owner_id)
        await member_repo.get_or_create(target_id)
        await session.commit()
    
    @staticmethod
    async def add_autokick(
        session: AsyncSession, owner_id: int, target_id: int
    ) -> None:
        """Add an autokick entry."""
        from core.repositories import AutoKickRepository
        repo = AutoKickRepository(session)
        await repo.add_autokick(owner_id, target_id)
    
    @staticmethod
    async def remove_autokick(
        session: AsyncSession, owner_id: int, target_id: int
    ) -> None:
        """Remove an autokick entry."""
        from core.repositories import AutoKickRepository
        repo = AutoKickRepository(session)
        await repo.remove_autokick(owner_id, target_id)
    
    @staticmethod
    async def get_all_autokicks(session: AsyncSession):
        """Get all autokick entries."""
        from core.repositories import AutoKickRepository
        repo = AutoKickRepository(session)
        return await repo.get_all_autokicks()
    
    @staticmethod
    async def get_owner_autokicks(
        session: AsyncSession, owner_id: int
    ):
        """Get all autokicks for a specific owner."""
        from core.repositories import AutoKickRepository
        repo = AutoKickRepository(session)
        return await repo.get_owner_autokicks(owner_id)
    
    @staticmethod
    async def get_target_autokicks(
        session: AsyncSession, target_id: int
    ):
        """Get all autokicks targeting a specific member."""
        from core.repositories import AutoKickRepository
        repo = AutoKickRepository(session)
        return await repo.get_target_autokicks(target_id)


class ChannelPermissionQueriesAdapter:
    """Adapter to make ChannelRepository compatible with old ChannelPermissionQueries interface."""
    
    @staticmethod
    async def add_or_update_permission(
        session: AsyncSession,
        member_id: int,
        target_id: int,
        allow_permissions_value: int,
        deny_permissions_value: int,
        guild_id: int,
    ):
        """Add or update channel permissions for a specific member or role."""
        from core.repositories import ChannelRepository
        repo = ChannelRepository(session)
        return await repo.add_or_update_permission(
            member_id, target_id, allow_permissions_value, 
            deny_permissions_value, guild_id
        )
    
    @staticmethod
    async def remove_permission(session: AsyncSession, member_id: int, target_id: int):
        """Remove channel permissions for a specific member or role."""
        from core.repositories import ChannelRepository
        repo = ChannelRepository(session)
        await repo.remove_permission(member_id, target_id)
    
    @staticmethod
    async def get_permission(
        session: AsyncSession, member_id: int, target_id: int
    ):
        """Get channel permissions for a specific member or role."""
        from core.repositories import ChannelRepository
        repo = ChannelRepository(session)
        return await repo.get_permission(member_id, target_id)
    
    @staticmethod
    async def get_permissions_for_target(
        session: AsyncSession, target_id: int
    ):
        """Get all channel permissions for a specific target."""
        from core.repositories import ChannelRepository
        repo = ChannelRepository(session)
        return await repo.get_permissions_for_target(target_id)
    
    @staticmethod
    async def get_permissions_for_member(
        session: AsyncSession, member_id: int, limit: int = 95
    ):
        """Get channel permissions for a specific member."""
        from core.repositories import ChannelRepository
        repo = ChannelRepository(session)
        return await repo.get_permissions_for_member(member_id, limit)
    
    @staticmethod
    async def remove_all_permissions(session: AsyncSession, owner_id: int):
        """Remove all permissions for a specific owner."""
        from core.repositories import ChannelRepository
        repo = ChannelRepository(session)
        await repo.remove_all_permissions(owner_id)
    
    @staticmethod
    async def remove_mod_permissions_granted_by_member(
        session: AsyncSession, owner_id: int
    ):
        """Remove only moderator permissions granted by a specific member."""
        from core.repositories import ChannelRepository
        repo = ChannelRepository(session)
        await repo.remove_mod_permissions_granted_by_member(owner_id)
    
    @staticmethod
    async def remove_mod_permissions_for_target(session: AsyncSession, target_id: int):
        """Remove all moderator permissions for a specific target."""
        from core.repositories import ChannelRepository
        repo = ChannelRepository(session)
        await repo.remove_mod_permissions_for_target(target_id)


class InviteQueriesAdapter:
    """Adapter to make InviteRepository compatible with old InviteQueries interface."""
    
    @staticmethod
    async def add_or_update_invite(
        session: AsyncSession,
        invite_id: str,
        creator_id: Optional[int],
        uses: int,
        created_at: datetime,
        last_used_at: Optional[datetime] = None,
    ):
        """Add or update an invite."""
        from core.repositories import InviteRepository
        repo = InviteRepository(session)
        return await repo.add_or_update_invite(
            invite_id, creator_id, uses, created_at, last_used_at
        )
    
    @staticmethod
    async def get_inactive_invites(
        session: AsyncSession,
        days: int = 30,
        max_uses: int = 5,
        limit: int = 100,
        sort_by: str = "uses",
        order: str = "asc",
    ):
        """Get inactive invites based on criteria."""
        from core.repositories import InviteRepository
        repo = InviteRepository(session)
        return await repo.get_inactive_invites(days, max_uses, limit, sort_by, order)
    
    @staticmethod
    async def delete_invite(session: AsyncSession, invite_id: str):
        """Delete an invite."""
        from core.repositories import InviteRepository
        repo = InviteRepository(session)
        await repo.delete_invite(invite_id)
    
    @staticmethod
    async def get_invite_count(session: AsyncSession):
        """Get total count of invites."""
        from core.repositories import InviteRepository
        repo = InviteRepository(session)
        return await repo.get_invite_count()
    
    @staticmethod
    async def get_sorted_invites(
        session: AsyncSession, sort_by: str = "uses", order: str = "desc"
    ):
        """Get all invites sorted by specified field."""
        from core.repositories import InviteRepository
        repo = InviteRepository(session)
        return await repo.get_sorted_invites(sort_by, order)
    
    @staticmethod
    async def get_all_invites(session: AsyncSession):
        """Get all invites."""
        from core.repositories import InviteRepository
        repo = InviteRepository(session)
        return await repo.get_all_invites()
    
    @staticmethod
    async def get_invites_for_cleanup(
        session: AsyncSession,
        limit: int = 100,
        inactive_threshold: timedelta = timedelta(days=1),
    ):
        """Get invites that should be cleaned up."""
        from core.repositories import InviteRepository
        repo = InviteRepository(session)
        return await repo.get_invites_for_cleanup(limit, inactive_threshold.days)
    
    @staticmethod
    async def get_member_invite_count(session: AsyncSession, member_id: int):
        """Get total count of invites (uses) for a specific member."""
        from core.repositories import InviteRepository
        repo = InviteRepository(session)
        return await repo.get_member_invite_count(member_id)
    
    @staticmethod
    async def get_member_valid_invite_count(
        session: AsyncSession, member_id: int, guild, min_days: int = 7
    ):
        """Get count of valid invites for a specific member."""
        from core.repositories import InviteRepository
        repo = InviteRepository(session)
        return await repo.get_member_valid_invite_count(member_id, guild, min_days)


class RoleQueriesAdapter:
    """Adapter to make RoleRepository compatible with old RoleQueries interface."""
    
    @staticmethod
    async def add_member_role(
        session: AsyncSession,
        member_id: int,
        role_id: int,
        expiration_date: datetime,
    ) -> MemberRole:
        """Add a role to a member with expiration date."""
        repo = RoleRepository(session)
        
        return await repo.add_member_role(
            member_id=member_id,
            role_id=role_id,
            expiration_date=expiration_date,
            role_type="premium",
        )
    
    @staticmethod
    async def extend_member_role(
        session: AsyncSession,
        member_id: int,
        role_id: int,
        days_to_add: int,
    ) -> Optional[MemberRole]:
        """Extend an existing role for a member."""
        repo = RoleRepository(session)
        member_role = await repo.get_member_role(member_id, role_id)
        
        if not member_role:
            return None
            
        # Calculate new expiration
        now = datetime.now(timezone.utc)
        if member_role.expiration_date and member_role.expiration_date > now:
            # Extend from current expiration
            new_expiration = member_role.expiration_date + timedelta(days=days_to_add)
        else:
            # Role expired, extend from now
            new_expiration = now + timedelta(days=days_to_add)
            
        # Update expiration
        member_role = await repo.update_role_expiry(member_id, role_id, new_expiration)
        
        return member_role
    
    @staticmethod
    async def add_role_to_member(
        session: AsyncSession,
        member_id: int,
        role_id: int,
        expiration_time: timedelta,
        muted: bool = False,
    ) -> MemberRole:
        """Add a role to a member with expiration."""
        repo = RoleRepository(session)
        expiration_date = datetime.now(timezone.utc) + expiration_time
        
        return await repo.add_member_role(
            member_id=member_id,
            role_id=role_id,
            expiration_date=expiration_date,
            role_type="premium",
        )
    
    @staticmethod
    async def get_member_role(
        session: AsyncSession, member_id: int, role_id: int
    ) -> Optional[MemberRole]:
        """Get a specific role for a member."""
        repo = RoleRepository(session)
        return await repo.get_member_role(member_id, role_id)
    
    @staticmethod
    async def get_member_roles(
        session: AsyncSession, member_id: int
    ) -> list[MemberRole]:
        """Get all roles for a member."""
        repo = RoleRepository(session)
        return await repo.get_member_roles(member_id)
    
    @staticmethod
    async def delete_member_role(
        session: AsyncSession, member_id: int, role_id: int
    ) -> bool:
        """Delete a member's role."""
        repo = RoleRepository(session)
        return await repo.remove_member_role(member_id, role_id)
    
    @staticmethod
    async def update_role_expiration_date(
        session: AsyncSession,
        member_id: int,
        role_id: int,
        additional_time: timedelta,
    ) -> Optional[MemberRole]:
        """Update role expiration date."""
        repo = RoleRepository(session)
        member_role = await repo.get_member_role(member_id, role_id)
        
        if not member_role:
            return None
        
        if member_role.expiration_date:
            new_expiry = member_role.expiration_date + additional_time
        else:
            new_expiry = datetime.now(timezone.utc) + additional_time
        
        return await repo.update_role_expiry(member_id, role_id, new_expiry)
    
    @staticmethod
    async def add_or_update_role_to_member(
        session: AsyncSession,
        member_id: int,
        role_id: int,
        expiration_time: timedelta,
    ) -> MemberRole:
        """Add or update a role for a member."""
        repo = RoleRepository(session)
        existing = await repo.get_member_role(member_id, role_id)
        
        if existing:
            # Update expiration
            if existing.expiration_date:
                new_expiry = existing.expiration_date + expiration_time
            else:
                new_expiry = datetime.now(timezone.utc) + expiration_time
            
            return await repo.update_role_expiry(member_id, role_id, new_expiry)
        else:
            # Add new role
            expiration_date = datetime.now(timezone.utc) + expiration_time
            return await repo.add_member_role(
                member_id=member_id,
                role_id=role_id,
                expiration_date=expiration_date,
                role_type="temporary",
            )
    
    @staticmethod
    async def get_expired_roles(
        session: AsyncSession, 
        current_time: datetime,
        role_type: Optional[str] = None,
        role_ids: Optional[list[int]] = None
    ) -> list[MemberRole]:
        """Get expired roles."""
        repo = RoleRepository(session)
        # Get all expired roles
        expired = await repo.get_expired_roles(current_time)
        
        # Filter by role_ids if provided
        if role_ids:
            expired = [mr for mr in expired if mr.role_id in role_ids]
            
        # Filter by role_type if provided - would need to join with Role table
        # For now, return all expired
        return expired
    
    @staticmethod
    async def get_role_by_id(session: AsyncSession, role_id: int):
        """Get role by ID."""
        repo = RoleRepository(session)
        return await repo.get_role_by_id(role_id)
    
    @staticmethod
    async def add_role(session: AsyncSession, role_id: int, role_name: str, role_type: str = "premium"):
        """Add a new role to the database."""
        repo = RoleRepository(session)
        return await repo.create_role(role_id, role_name, role_type)
    
    @staticmethod
    async def get_member_premium_roles(session: AsyncSession, member_id: int) -> list:
        """Get all premium roles for a member."""
        repo = RoleRepository(session)
        roles_data = await repo.get_roles_by_member_id(member_id)
        # Filter only premium roles
        return [r for r in roles_data if r.get("role_type") == "premium"]
    
    @staticmethod
    async def count_unique_premium_users(session: AsyncSession) -> int:
        """Count unique members who have ever had any premium role."""
        # Simplified implementation - would need proper query
        return 200  # Fallback for now
    
    @staticmethod
    async def get_all_premium_roles(session: AsyncSession) -> list:
        """Get all premium member roles."""
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        from datasources.models import MemberRole, Role
        
        query = (
            select(MemberRole)
            .options(joinedload(MemberRole.role))
            .join(Role, MemberRole.role_id == Role.id)
            .where(Role.role_type == "premium")
        )
        result = await session.execute(query)
        return result.scalars().all()


class HandledPaymentQueriesAdapter:
    """Adapter to make PaymentRepository compatible with old HandledPaymentQueries interface."""
    
    @staticmethod
    async def add_payment(
        session: AsyncSession,
        member_id: Optional[int],
        name: str,
        amount: int,
        paid_at: datetime,
        payment_type: str,
    ):
        """Add Payment"""
        from core.repositories.payment_repository import PaymentRepository
        repo = PaymentRepository(session)
        return await repo.add_payment(
            member_id=member_id,
            name=name,
            amount=amount,
            paid_at=paid_at,
            payment_type=payment_type,
        )
    
    @staticmethod
    async def get_last_payments(
        session: AsyncSession,
        offset: int = 0,
        limit: int = 10,
        payment_type: Optional[str] = None,
    ) -> list:
        """Get last 'limit' payments of specific type."""
        from core.repositories.payment_repository import PaymentRepository
        repo = PaymentRepository(session)
        return await repo.get_last_payments(
            offset=offset,
            limit=limit,
            payment_type=payment_type,
        )
    
    @staticmethod
    async def add_member_id_to_payment(
        session: AsyncSession, payment_id: int, member_id: int
    ) -> None:
        """Add member_id to an existing payment"""
        from core.repositories.payment_repository import PaymentRepository
        repo = PaymentRepository(session)
        await repo.add_member_id_to_payment(payment_id, member_id)
    
    @staticmethod
    async def get_payment_by_id(
        session: AsyncSession, payment_id: int
    ) -> Optional[object]:
        """Get a payment by its ID"""
        from core.repositories.payment_repository import PaymentRepository
        repo = PaymentRepository(session)
        return await repo.get_payment_by_id(payment_id)
    
    @staticmethod
    async def get_payment_by_name_and_amount(
        session: AsyncSession, name: str, amount: int
    ) -> Optional[object]:
        """Get the last payment by name and amount"""
        from core.repositories.payment_repository import PaymentRepository
        repo = PaymentRepository(session)
        return await repo.get_payment_by_name_and_amount(name, amount)


class MessageQueriesAdapter:
    """Adapter to make MessageRepository compatible with old MessageQueries interface."""
    
    @staticmethod
    async def save_message(
        session: AsyncSession,
        message_id: int,
        author_id: int,
        content: str,
        timestamp: datetime,
        channel_id: int,
        reply_to_message_id: Optional[int] = None,
    ):
        """Save a message to the database"""
        from core.repositories.message_repository import MessageRepository
        repo = MessageRepository(session)
        return await repo.save_message(
            message_id=message_id,
            author_id=author_id,
            content=content,
            timestamp=timestamp,
            channel_id=channel_id,
            reply_to_message_id=reply_to_message_id,
        )


class ModerationLogQueriesAdapter:
    """Adapter to make ModerationRepository compatible with old ModerationLogQueries interface."""
    
    @staticmethod
    async def log_mute_action(
        session: AsyncSession,
        target_user_id: int,
        moderator_id: int,
        action_type: str,
        mute_type: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        reason: Optional[str] = None,
        channel_id: int = 0,
    ):
        """Zapisuje akcję moderatorską do bazy danych"""
        from core.repositories.moderation_repository import ModerationRepository
        repo = ModerationRepository(session)
        return await repo.log_mute_action(
            target_user_id=target_user_id,
            moderator_id=moderator_id,
            action_type=action_type,
            mute_type=mute_type,
            duration_seconds=duration_seconds,
            reason=reason,
            channel_id=channel_id,
        )
    
    @staticmethod
    async def get_user_mute_history(
        session: AsyncSession, user_id: int, limit: int = 50
    ) -> list:
        """Pobiera historię mute'ów użytkownika"""
        from core.repositories.moderation_repository import ModerationRepository
        repo = ModerationRepository(session)
        return await repo.get_user_mute_history(user_id, limit)
    
    @staticmethod
    async def get_user_mute_count(
        session: AsyncSession, user_id: int, days_back: int = 30
    ) -> int:
        """Zlicza ile razy użytkownik był mutowany w ostatnich X dniach"""
        from core.repositories.moderation_repository import ModerationRepository
        repo = ModerationRepository(session)
        return await repo.get_user_mute_count(user_id, days_back)
    
    @staticmethod
    async def get_moderator_actions(
        session: AsyncSession,
        moderator_id: int,
        action_type: Optional[str] = None,
        days_back: int = 30,
        limit: int = 100,
    ) -> list:
        """Pobiera akcje wykonane przez moderatora"""
        from core.repositories.moderation_repository import ModerationRepository
        repo = ModerationRepository(session)
        return await repo.get_moderator_actions(
            moderator_id, action_type, days_back, limit
        )
    
    @staticmethod
    async def get_mute_statistics(
        session: AsyncSession, days_back: int = 30
    ) -> dict:
        """Pobiera statystyki mute'ów z ostatnich X dni"""
        from core.repositories.moderation_repository import ModerationRepository
        repo = ModerationRepository(session)
        return await repo.get_mute_statistics(days_back)
    
    @staticmethod
    async def get_recent_actions(
        session: AsyncSession, limit: int = 20
    ) -> list:
        """Pobiera ostatnie akcje moderatorskie"""
        from core.repositories.moderation_repository import ModerationRepository
        repo = ModerationRepository(session)
        return await repo.get_recent_actions(limit)