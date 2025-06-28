"""Member management interfaces for member operations, activity tracking, and invites."""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import Any, Optional

import discord

from core.interfaces.base import IRepository, IService
from datasources.models import Activity, AutoKick, Invite, Member, ModerationLog


class IMemberRepository(IRepository):
    """Repository interface for member data operations."""

    @abstractmethod
    async def get_by_discord_id(self, discord_id: int) -> Optional[Member]:
        """Get member by Discord ID."""
        pass

    @abstractmethod
    async def create_member(
        self,
        discord_id: int,
        first_inviter_id: Optional[int] = None,
        current_inviter_id: Optional[int] = None,
        joined_at: Optional[datetime] = None,
    ) -> Member:
        """Create a new member."""
        pass

    @abstractmethod
    async def update_wallet_balance(self, member_id: int, new_balance: int) -> bool:
        """Update member's wallet balance."""
        pass

    @abstractmethod
    async def update_voice_bypass(self, member_id: int, bypass_until: Optional[datetime]) -> bool:
        """Update member's voice bypass expiration."""
        pass

    @abstractmethod
    async def update_inviter(self, member_id: int, new_inviter_id: Optional[int], update_current: bool = True) -> bool:
        """Update member's inviter (current or first)."""
        pass

    @abstractmethod
    async def get_members_by_inviter(self, inviter_id: int) -> list[Member]:
        """Get all members invited by a specific inviter."""
        pass

    @abstractmethod
    async def get_member_count(self) -> int:
        """Get total member count."""
        pass


class IActivityRepository(IRepository):
    """Repository interface for activity tracking operations."""

    @abstractmethod
    async def get_member_activity(
        self,
        member_id: int,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Activity]:
        """Get member activity records with optional filtering."""
        pass

    @abstractmethod
    async def add_activity(
        self,
        member_id: int,
        points: int,
        activity_type: str,
        date: Optional[datetime] = None,
    ) -> Activity:
        """Add activity record for member."""
        pass

    @abstractmethod
    async def get_member_total_points(
        self,
        member_id: int,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Get total points for member with optional filtering."""
        pass

    @abstractmethod
    async def get_leaderboard(
        self,
        activity_type: Optional[str] = None,
        limit: int = 10,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[tuple[Member, int]]:
        """Get activity leaderboard."""
        pass


class IInviteRepository(IRepository):
    """Repository interface for invite tracking operations."""

    @abstractmethod
    async def get_by_code(self, invite_code: str) -> Optional[Invite]:
        """Get invite by code."""
        pass

    @abstractmethod
    async def create_invite(
        self,
        invite_code: str,
        creator_id: int,
        uses: int = 0,
        created_at: Optional[datetime] = None,
    ) -> Optional[Invite]:
        """Create new invite record."""
        pass

    @abstractmethod
    async def update_invite_usage(
        self, invite_code: str, new_uses: int, last_used_at: Optional[datetime] = None
    ) -> bool:
        """Update invite usage statistics."""
        pass

    @abstractmethod
    async def get_member_invites(self, creator_id: int) -> list[Invite]:
        """Get all invites created by member."""
        pass

    @abstractmethod
    async def get_invite_stats(self, creator_id: int) -> dict[str, int]:
        """Get invite statistics for member."""
        pass


class IModerationRepository(IRepository):
    """Repository interface for moderation log operations."""

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_member_history(self, member_id: int, action_type: Optional[str] = None) -> list[ModerationLog]:
        """Get moderation history for member."""
        pass

    @abstractmethod
    async def get_active_mutes(
        self, member_id: Optional[int] = None, mute_type: Optional[str] = None
    ) -> list[ModerationLog]:
        """Get active mute records."""
        pass

    @abstractmethod
    async def get_moderator_stats(self, moderator_id: int) -> dict[str, int]:
        """Get moderation statistics for moderator."""
        pass


class IAutoKickRepository(IRepository):
    """Repository interface for auto-kick management."""

    @abstractmethod
    async def get_autokick(self, owner_id: int, target_id: int) -> Optional[AutoKick]:
        """Get specific autokick setting."""
        pass

    @abstractmethod
    async def create_autokick(self, owner_id: int, target_id: int) -> AutoKick:
        """Create autokick setting."""
        pass

    @abstractmethod
    async def remove_autokick(self, owner_id: int, target_id: int) -> bool:
        """Remove autokick setting."""
        pass

    @abstractmethod
    async def get_member_autokicks(self, owner_id: int) -> list[AutoKick]:
        """Get all autokick settings for member."""
        pass

    @abstractmethod
    async def get_targets_for_autokick(self, target_id: int) -> list[AutoKick]:
        """Get all autokick settings targeting specific member."""
        pass


class IMemberService(IService):
    """Service interface for comprehensive member management."""

    @abstractmethod
    async def get_or_create_member(self, discord_user: discord.Member | discord.User) -> Member:
        """Get existing member or create new one."""
        pass

    @abstractmethod
    async def update_member_info(
        self,
        member: Member,
        wallet_balance: Optional[int] = None,
        voice_bypass_until: Optional[datetime] = None,
        current_inviter_id: Optional[int] = None,
    ) -> Member:
        """Update member information."""
        pass

    @abstractmethod
    async def process_member_join(
        self,
        discord_user: discord.Member,
        invite_code: Optional[str] = None,
        inviter: Optional[discord.Member] = None,
    ) -> Member:
        """Process new member joining server."""
        pass

    @abstractmethod
    async def process_member_leave(self, discord_user: discord.Member) -> bool:
        """Process member leaving server."""
        pass

    @abstractmethod
    async def get_member_profile(self, member_id: int) -> dict[str, Any]:
        """Get comprehensive member profile data."""
        pass

    @abstractmethod
    async def get_invite_leaderboard(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get invite leaderboard."""
        pass


class IActivityService(IService):
    """Service interface for activity tracking and management."""

    @abstractmethod
    async def track_activity(self, member: Member, activity_type: str, points: int) -> Activity:
        """Track member activity and award points."""
        pass

    @abstractmethod
    async def get_member_activity_summary(self, member_id: int, days: int = 30) -> dict[str, Any]:
        """Get member activity summary for specified period."""
        pass

    @abstractmethod
    async def get_activity_leaderboard(
        self, activity_type: Optional[str] = None, limit: int = 10, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get activity leaderboard."""
        pass

    @abstractmethod
    async def award_bonus_points(self, member: Member, points: int, reason: str = "bonus") -> Activity:
        """Award bonus points to member."""
        pass

    @abstractmethod
    async def get_server_activity_stats(self, days: int = 30) -> dict[str, Any]:
        """Get overall server activity statistics."""
        pass

    @abstractmethod
    async def track_message_activity(self, member_id: int, message_content: str, channel_id: int) -> Activity:
        """Track text message activity."""
        pass

    @abstractmethod
    async def track_voice_activity(self, member_id: int, channel_id: int, is_with_others: bool) -> Activity:
        """Track voice channel activity."""
        pass

    @abstractmethod
    async def track_promotion_activity(self, member_id: int) -> Activity:
        """Track server promotion activity."""
        pass


class IModerationService(IService):
    """Service interface for moderation operations."""

    @abstractmethod
    async def mute_member(
        self,
        target: discord.Member,
        moderator: discord.Member,
        mute_type: str,
        duration_seconds: Optional[int] = None,
        reason: Optional[str] = None,
        channel_id: Optional[int] = None,
    ) -> ModerationLog:
        """Mute member with specified type and duration."""
        pass

    @abstractmethod
    async def unmute_member(
        self,
        target: discord.Member,
        moderator: discord.Member,
        mute_type: str,
        reason: Optional[str] = None,
        channel_id: Optional[int] = None,
    ) -> ModerationLog:
        """Unmute member for specific mute type."""
        pass

    @abstractmethod
    async def kick_member(
        self,
        target: discord.Member,
        moderator: discord.Member,
        reason: Optional[str] = None,
        channel_id: Optional[int] = None,
    ) -> ModerationLog:
        """Kick member from server."""
        pass

    @abstractmethod
    async def ban_member(
        self,
        target: discord.Member,
        moderator: discord.Member,
        reason: Optional[str] = None,
        channel_id: Optional[int] = None,
    ) -> ModerationLog:
        """Ban member from server."""
        pass

    @abstractmethod
    async def get_member_warnings(self, member_id: int) -> list[ModerationLog]:
        """Get all warnings for member."""
        pass

    @abstractmethod
    async def check_active_mutes(self, member_id: int) -> list[str]:
        """Check what mute types are active for member."""
        pass

    @abstractmethod
    async def process_expired_mutes(self) -> list[ModerationLog]:
        """Process and clean up expired mutes."""
        pass


class IInviteService(IService):
    """Service interface for invite tracking and management."""

    @abstractmethod
    async def sync_server_invites(self, guild: discord.Guild) -> dict[str, Invite]:
        """Synchronize server invites with database."""
        pass

    @abstractmethod
    async def process_invite_usage(
        self, before_invites: dict[str, discord.Invite], after_invites: dict[str, discord.Invite]
    ) -> Optional[Invite]:
        """Process invite usage change and return used invite."""
        pass

    @abstractmethod
    async def get_member_invite_stats(self, member_id: int) -> dict[str, Any]:
        """Get comprehensive invite statistics for member."""
        pass

    @abstractmethod
    async def create_tracked_invite(self, invite: discord.Invite, creator: discord.Member) -> Optional[Invite]:
        """Create tracked invite in database."""
        pass

    @abstractmethod
    async def cleanup_expired_invites(self, guild: discord.Guild) -> int:
        """Remove expired/invalid invites from database."""
        pass
