"""Member management service implementations."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import discord

from core.interfaces.member_interfaces import (
    IActivityRepository,
    IActivityService,
    IInviteRepository,
    IInviteService,
    IMemberRepository,
    IMemberService,
    IModerationRepository,
    IModerationService,
)
from core.services.base_service import BaseService
from datasources.models import Activity, Invite, Member, ModerationLog

logger = logging.getLogger(__name__)


class MemberService(BaseService, IMemberService):
    """Service for comprehensive member management."""

    def __init__(
        self, member_repository: IMemberRepository, invite_repository: IInviteRepository, unit_of_work, **kwargs
    ):
        super().__init__(unit_of_work=unit_of_work)
        self.member_repository = member_repository
        self.invite_repository = invite_repository

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate member operation."""
        return True

    async def get_or_create_member(self, discord_user: discord.Member | discord.User) -> Member:
        """Get existing member or create new one."""
        try:
            member = await self.member_repository.get_by_discord_id(discord_user.id)
            if member:
                return member

            # Create new member
            joined_at = None
            if isinstance(discord_user, discord.Member) and discord_user.joined_at:
                joined_at = discord_user.joined_at

            member = await self.member_repository.create_member(
                discord_id=discord_user.id,
                joined_at=joined_at,
            )

            self._log_operation(
                "get_or_create_member",
                discord_id=discord_user.id,
                created=True,
            )

            return member

        except Exception as e:
            self._log_error("get_or_create_member", e, discord_id=discord_user.id)
            raise

    async def update_member_info(
        self,
        member: Member,
        wallet_balance: Optional[int] = None,
        voice_bypass_until: Optional[datetime] = None,
        current_inviter_id: Optional[int] = None,
    ) -> Member:
        """Update member information."""
        try:
            updated = False

            if wallet_balance is not None:
                await self.member_repository.update_wallet_balance(member.id, wallet_balance)
                updated = True

            if voice_bypass_until is not None:
                await self.member_repository.update_voice_bypass(member.id, voice_bypass_until)
                updated = True

            if current_inviter_id is not None:
                await self.member_repository.update_inviter(member.id, current_inviter_id, update_current=True)
                updated = True

            if updated:
                # Refresh member object
                member = await self.member_repository.get_by_id(member.id)

                self._log_operation(
                    "update_member_info",
                    member_id=member.id,
                    wallet_balance=wallet_balance,
                    voice_bypass_until=voice_bypass_until,
                    current_inviter_id=current_inviter_id,
                )

            return member

        except Exception as e:
            self._log_error("update_member_info", e, member_id=member.id)
            raise

    async def process_member_join(
        self,
        discord_user: discord.Member,
        invite_code: Optional[str] = None,
        inviter: Optional[discord.Member] = None,
    ) -> Member:
        """Process new member joining server."""
        try:
            # Get or create member
            member = await self.get_or_create_member(discord_user)

            # Update join information
            if discord_user.joined_at:
                member.joined_at = discord_user.joined_at
                member.rejoined_at = discord_user.joined_at

            # Set inviter information
            if inviter:
                inviter_member = await self.get_or_create_member(inviter)

                # Set first inviter if not set
                if member.first_inviter_id is None:
                    await self.member_repository.update_inviter(member.id, inviter_member.id, update_current=False)

                # Always update current inviter
                await self.member_repository.update_inviter(member.id, inviter_member.id, update_current=True)

            # Update invite usage if invite code provided
            if invite_code:
                invite = await self.invite_repository.get_by_code(invite_code)
                if invite:
                    await self.invite_repository.update_invite_usage(
                        invite_code,
                        invite.uses + 1,
                        last_used_at=datetime.now(timezone.utc),
                    )

            # Refresh member object
            member = await self.member_repository.get_by_id(member.id)

            self._log_operation(
                "process_member_join",
                member_id=member.id,
                invite_code=invite_code,
                inviter_id=inviter.id if inviter else None,
            )

            return member

        except Exception as e:
            self._log_error("process_member_join", e, discord_id=discord_user.id)
            raise

    async def process_member_leave(self, discord_user: discord.Member) -> bool:
        """Process member leaving server."""
        try:
            member = await self.member_repository.get_by_discord_id(discord_user.id)
            if not member:
                return False

            # Could add additional leave processing logic here
            # For now, just log the event

            self._log_operation(
                "process_member_leave",
                member_id=member.id,
                left_at=datetime.now(timezone.utc),
            )

            return True

        except Exception as e:
            self._log_error("process_member_leave", e, discord_id=discord_user.id)
            return False

    async def get_member_profile(self, member_id: int) -> dict[str, Any]:
        """Get comprehensive member profile data."""
        try:
            member = await self.member_repository.get_by_id(member_id)
            if not member:
                return {}

            # Get activity stats (last 30 days)
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            total_activity_points = await self.activity_repository.get_member_total_points(
                member_id, start_date=thirty_days_ago
            )

            # Get voice activity points specifically
            voice_points = await self.activity_repository.get_member_total_points(
                member_id, activity_type="voice", start_date=thirty_days_ago
            )

            # Get text activity points specifically
            text_points = await self.activity_repository.get_member_total_points(
                member_id, activity_type="text", start_date=thirty_days_ago
            )

            # Get invite stats
            invite_stats = await self.invite_repository.get_invite_stats(member_id)

            # Get invited members count
            invited_members = await self.member_repository.get_members_by_inviter(member_id)

            profile = {
                "member_id": member.id,
                "joined_at": member.joined_at,
                "rejoined_at": member.rejoined_at,
                "wallet_balance": member.wallet_balance,
                "voice_bypass_until": member.voice_bypass_until,
                "first_inviter_id": member.first_inviter_id,
                "current_inviter_id": member.current_inviter_id,
                "activity": {
                    "total_points_30d": total_activity_points,
                    "voice_points_30d": voice_points,
                    "text_points_30d": text_points,
                },
                "invites": {
                    "total_invites_created": invite_stats["total_invites"],
                    "total_invite_uses": invite_stats["total_uses"],
                    "members_invited": len(invited_members),
                },
            }

            self._log_operation("get_member_profile", member_id=member_id)
            return profile

        except Exception as e:
            self._log_error("get_member_profile", e, member_id=member_id)
            return {}

    async def get_invite_leaderboard(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get invite leaderboard with optimized single query (eliminates N+1 problem)."""
        try:
            # Use optimized repository method that eliminates N+1 queries
            leaderboard = await self.member_repository.get_invite_leaderboard_optimized(limit)

            self._log_operation("get_invite_leaderboard", limit=limit, count=len(leaderboard))
            return leaderboard

        except Exception as e:
            self._log_error("get_invite_leaderboard", e)
            return []

    async def get_voice_bypass_status(self, member_id: int) -> Optional[datetime]:
        """Get voice bypass expiration for member."""
        try:
            member = await self.member_repository.get_by_discord_id(member_id)
            if not member:
                return None

            self._log_operation("get_voice_bypass_status", member_id=member_id)
            return member.voice_bypass_until

        except Exception as e:
            self._log_error("get_voice_bypass_status", e, member_id=member_id)
            return None

    async def set_voice_bypass_status(self, member_id: int, expiration: Optional[datetime]) -> bool:
        """Set voice bypass expiration for member."""
        try:
            success = await self.member_repository.update_voice_bypass(member_id, expiration)

            self._log_operation("set_voice_bypass_status", member_id=member_id, expiration=expiration)
            return success

        except Exception as e:
            self._log_error("set_voice_bypass_status", e, member_id=member_id)
            return False


class ActivityService(BaseService, IActivityService):
    """Service for activity tracking and management."""

    def __init__(self, activity_repository: IActivityRepository, member_repository: IMemberRepository, **kwargs):
        super().__init__(**kwargs)
        self.activity_repository = activity_repository
        self.member_repository = member_repository

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate activity operation."""
        return True

    async def track_activity(self, member: Member, activity_type: str, points: int) -> Activity:
        """Track member activity and award points."""
        try:
            activity = await self.activity_repository.add_activity(
                member_id=member.id,
                points=points,
                activity_type=activity_type,
            )

            self._log_operation(
                "track_activity",
                member_id=member.id,
                activity_type=activity_type,
                points=points,
            )

            return activity

        except Exception as e:
            self._log_error("track_activity", e, member_id=member.id)
            raise

    async def get_member_activity_summary(self, member_id: int, days: int = 30) -> dict[str, Any]:
        """Get member activity summary for specified period."""
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Get total points
            total_points = await self.activity_repository.get_member_total_points(member_id, start_date=start_date)

            # Get points by activity type
            voice_points = await self.activity_repository.get_member_total_points(
                member_id, activity_type="voice", start_date=start_date
            )

            text_points = await self.activity_repository.get_member_total_points(
                member_id, activity_type="text", start_date=start_date
            )

            bonus_points = await self.activity_repository.get_member_total_points(
                member_id, activity_type="bonus", start_date=start_date
            )

            # Get recent activity
            recent_activities = await self.activity_repository.get_member_activity(member_id, start_date=start_date)

            summary = {
                "member_id": member_id,
                "period_days": days,
                "total_points": total_points,
                "breakdown": {
                    "voice": voice_points,
                    "text": text_points,
                    "bonus": bonus_points,
                },
                "recent_activities_count": len(recent_activities),
            }

            self._log_operation(
                "get_member_activity_summary",
                member_id=member_id,
                days=days,
            )

            return summary

        except Exception as e:
            self._log_error("get_member_activity_summary", e, member_id=member_id)
            return {}

    async def get_activity_leaderboard(
        self, activity_type: Optional[str] = None, limit: int = 10, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get activity leaderboard."""
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            leaderboard_raw = await self.activity_repository.get_leaderboard(
                activity_type=activity_type,
                limit=limit,
                start_date=start_date,
            )

            leaderboard = []
            for rank, (member, points) in enumerate(leaderboard_raw, 1):
                leaderboard.append(
                    {
                        "rank": rank,
                        "member_id": member.id,
                        "points": points,
                        "activity_type": activity_type or "all",
                        "period_days": days,
                    }
                )

            self._log_operation(
                "get_activity_leaderboard",
                activity_type=activity_type,
                limit=limit,
                days=days,
            )

            return leaderboard

        except Exception as e:
            self._log_error("get_activity_leaderboard", e)
            return []

    async def track_message_activity(self, member_id: int, message_content: str, channel_id: int) -> Activity:
        """Track text message activity."""
        try:
            # Ensure member exists
            member = await self.member_repository.get_or_create(member_id)

            # Calculate points based on message length (1-3 points)
            message_length = len(message_content.strip())
            if message_length < 10:
                points = 1
            elif message_length < 50:
                points = 2
            else:
                points = 3

            activity = await self.activity_repository.add_activity(
                member_id=member_id,
                points=points,
                activity_type="text",
            )

            # Reduced logging for frequent activity operations
            # self._log_operation(
            #     "track_message_activity",
            #     member_id=member_id,
            #     points=points,
            #     channel_id=channel_id,
            # )

            return activity

        except Exception as e:
            self._log_error("track_message_activity", e, member_id=member_id)
            raise

    async def track_voice_activity(self, member_id: int, channel_id: int, is_with_others: bool) -> Activity:
        """Track voice channel activity."""
        try:
            # Ensure member exists
            member = await self.member_repository.get_or_create(member_id)

            # Award more points when with others (social bonus)
            points = 2 if is_with_others else 1

            activity = await self.activity_repository.add_activity(
                member_id=member_id,
                points=points,
                activity_type="voice",
            )

            # Reduced logging for frequent activity operations
            # self._log_operation(
            #     "track_voice_activity",
            #     member_id=member_id,
            #     points=points,
            #     channel_id=channel_id,
            #     is_with_others=is_with_others,
            # )

            return activity

        except Exception as e:
            self._log_error("track_voice_activity", e, member_id=member_id)
            raise

    async def track_promotion_activity(self, member_id: int) -> Activity:
        """Track server promotion activity."""
        try:
            # Ensure member exists
            member = await self.member_repository.get_or_create(member_id)

            # Award bonus points for promoting the server
            points = 5

            activity = await self.activity_repository.add_activity(
                member_id=member_id,
                points=points,
                activity_type="promotion",
            )

            self._log_operation(
                "track_promotion_activity",
                member_id=member_id,
                points=points,
            )

            return activity

        except Exception as e:
            self._log_error("track_promotion_activity", e, member_id=member_id)
            raise

    async def award_bonus_points(self, member: Member, points: int, reason: str = "bonus") -> Activity:
        """Award bonus points to member."""
        try:
            activity = await self.activity_repository.add_activity(
                member_id=member.id,
                points=points,
                activity_type="bonus",
            )

            self._log_operation(
                "award_bonus_points",
                member_id=member.id,
                points=points,
                reason=reason,
            )

            return activity

        except Exception as e:
            self._log_error("award_bonus_points", e, member_id=member.id)
            raise

    async def get_server_activity_stats(self, days: int = 30) -> dict[str, Any]:
        """Get overall server activity statistics."""
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Get total points across all activity types
            total_points = await self.activity_repository.get_total_points(start_date=start_date)

            # Get activity breakdown
            voice_activity = await self.activity_repository.get_total_points(
                activity_type="voice", start_date=start_date
            )

            text_activity = await self.activity_repository.get_total_points(activity_type="text", start_date=start_date)

            promotion_activity = await self.activity_repository.get_total_points(
                activity_type="promotion", start_date=start_date
            )

            bonus_activity = await self.activity_repository.get_total_points(
                activity_type="bonus", start_date=start_date
            )

            # Get active members count
            active_members = await self.activity_repository.get_active_members_count(start_date=start_date)

            stats = {
                "period_days": days,
                "total_points": total_points or 0,
                "active_members": active_members or 0,
                "breakdown": {
                    "voice_activity": voice_activity or 0,
                    "text_activity": text_activity or 0,
                    "promotion_activity": promotion_activity or 0,
                    "bonus_activity": bonus_activity or 0,
                },
                # Legacy format for backwards compatibility
                "voice_activity": voice_activity or 0,
                "text_activity": text_activity or 0,
            }

            self._log_operation("get_server_activity_stats", days=days)
            return stats

        except Exception as e:
            self._log_error("get_server_activity_stats", e)
            return {}

    async def award_bonus_points(self, member: Member, points: int, reason: str = "bonus") -> Activity:
        """Award bonus points to member."""
        try:
            activity = await self.activity_repository.add_activity(
                member_id=member.id,
                points=points,
                activity_type="bonus",
            )

            self._log_operation(
                "award_bonus_points",
                member_id=member.id,
                points=points,
                reason=reason,
            )

            return activity

        except Exception as e:
            self._log_error("award_bonus_points", e, member_id=member.id)
            raise

    async def get_server_activity_stats(self, days: int = 30) -> dict[str, Any]:
        """Get overall server activity statistics."""
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Get leaderboards for different activity types
            overall_leaderboard = await self.activity_repository.get_leaderboard(limit=5, start_date=start_date)

            voice_leaderboard = await self.activity_repository.get_leaderboard(
                activity_type="voice", limit=5, start_date=start_date
            )

            text_leaderboard = await self.activity_repository.get_leaderboard(
                activity_type="text", limit=5, start_date=start_date
            )

            # Get total member count
            total_members = await self.member_repository.get_member_count()

            stats = {
                "period_days": days,
                "total_members": total_members,
                "top_overall": [{"member_id": member.id, "points": points} for member, points in overall_leaderboard],
                "top_voice": [{"member_id": member.id, "points": points} for member, points in voice_leaderboard],
                "top_text": [{"member_id": member.id, "points": points} for member, points in text_leaderboard],
            }

            self._log_operation("get_server_activity_stats", days=days)
            return stats

        except Exception as e:
            self._log_error("get_server_activity_stats", e)
            return {}


class ModerationService(BaseService, IModerationService):
    """Service for moderation operations."""

    def __init__(self, moderation_repository: IModerationRepository, member_repository: IMemberRepository, **kwargs):
        super().__init__(**kwargs)
        self.moderation_repository = moderation_repository
        self.member_repository = member_repository

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate moderation operation."""
        return True

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
        try:
            # Ensure target member exists in database
            await self.member_repository.get_or_create(target.id)
            # Ensure moderator exists in database
            await self.member_repository.get_or_create(moderator.id)

            expires_at = None
            if duration_seconds:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

            if channel_id is None:
                channel_id = 0  # Default fallback

            log_entry = await self.moderation_repository.log_action(
                target_user_id=target.id,
                moderator_id=moderator.id,
                action_type="mute",
                channel_id=channel_id,
                mute_type=mute_type,
                duration_seconds=duration_seconds,
                reason=reason,
            )

            self._log_operation(
                "mute_member",
                target_id=target.id,
                moderator_id=moderator.id,
                mute_type=mute_type,
                duration_seconds=duration_seconds,
            )

            return log_entry

        except Exception as e:
            self._log_error("mute_member", e, target_id=target.id)
            raise

    async def unmute_member(
        self,
        target: discord.Member,
        moderator: discord.Member,
        mute_type: str,
        reason: Optional[str] = None,
        channel_id: Optional[int] = None,
    ) -> ModerationLog:
        """Unmute member for specific mute type."""
        try:
            # Ensure target member exists in database
            await self.member_repository.get_or_create(target.id)
            # Ensure moderator exists in database
            await self.member_repository.get_or_create(moderator.id)

            if channel_id is None:
                channel_id = 0  # Default fallback

            log_entry = await self.moderation_repository.log_action(
                target_user_id=target.id,
                moderator_id=moderator.id,
                action_type="unmute",
                channel_id=channel_id,
                mute_type=mute_type,
                reason=reason,
            )

            self._log_operation(
                "unmute_member",
                target_id=target.id,
                moderator_id=moderator.id,
                mute_type=mute_type,
            )

            return log_entry

        except Exception as e:
            self._log_error("unmute_member", e, target_id=target.id)
            raise

    async def kick_member(
        self,
        target: discord.Member,
        moderator: discord.Member,
        reason: Optional[str] = None,
        channel_id: Optional[int] = None,
    ) -> ModerationLog:
        """Kick member from server."""
        try:
            if channel_id is None:
                channel_id = 0  # Default fallback

            log_entry = await self.moderation_repository.log_action(
                target_user_id=target.id,
                moderator_id=moderator.id,
                action_type="kick",
                channel_id=channel_id,
                reason=reason,
            )

            self._log_operation(
                "kick_member",
                target_id=target.id,
                moderator_id=moderator.id,
                reason=reason,
            )

            return log_entry

        except Exception as e:
            self._log_error("kick_member", e, target_id=target.id)
            raise

    async def ban_member(
        self,
        target: discord.Member,
        moderator: discord.Member,
        reason: Optional[str] = None,
        channel_id: Optional[int] = None,
    ) -> ModerationLog:
        """Ban member from server."""
        try:
            if channel_id is None:
                channel_id = 0  # Default fallback

            log_entry = await self.moderation_repository.log_action(
                target_user_id=target.id,
                moderator_id=moderator.id,
                action_type="ban",
                channel_id=channel_id,
                reason=reason,
            )

            self._log_operation(
                "ban_member",
                target_id=target.id,
                moderator_id=moderator.id,
                reason=reason,
            )

            return log_entry

        except Exception as e:
            self._log_error("ban_member", e, target_id=target.id)
            raise

    async def get_member_warnings(self, member_id: int) -> list[ModerationLog]:
        """Get all warnings for member."""
        try:
            warnings = await self.moderation_repository.get_member_history(member_id, action_type="mute")

            self._log_operation("get_member_warnings", member_id=member_id)
            return warnings

        except Exception as e:
            self._log_error("get_member_warnings", e, member_id=member_id)
            return []

    async def check_active_mutes(self, member_id: int) -> list[str]:
        """Check what mute types are active for member."""
        try:
            active_mutes = await self.moderation_repository.get_active_mutes(member_id)
            mute_types = [mute.mute_type for mute in active_mutes if mute.mute_type]

            self._log_operation("check_active_mutes", member_id=member_id)
            return mute_types

        except Exception as e:
            self._log_error("check_active_mutes", e, member_id=member_id)
            return []

    async def process_expired_mutes(self) -> list[ModerationLog]:
        """Process and clean up expired mutes."""
        try:
            # Get all active mutes
            active_mutes = await self.moderation_repository.get_active_mutes()

            current_time = datetime.now(timezone.utc)
            expired_mutes = []

            for mute in active_mutes:
                if mute.expires_at and mute.expires_at <= current_time:
                    expired_mutes.append(mute)

            self._log_operation("process_expired_mutes", expired_count=len(expired_mutes))
            return expired_mutes

        except Exception as e:
            self._log_error("process_expired_mutes", e)
            return []


class InviteService(BaseService, IInviteService):
    """Service for invite tracking and management."""

    def __init__(self, invite_repository: IInviteRepository, member_repository: IMemberRepository, **kwargs):
        super().__init__(**kwargs)
        self.invite_repository = invite_repository
        self.member_repository = member_repository

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate invite operation."""
        return True

    async def sync_server_invites(self, guild: discord.Guild) -> dict[str, Invite]:
        """Synchronize server invites with database."""
        try:
            logger.info(f"NEW InviteService.sync_server_invites called for guild {guild.id}")
            discord_invites = await guild.invites()
            synced_invites = {}

            for discord_invite in discord_invites:
                # Get or create invite in database
                db_invite = await self.invite_repository.get_by_code(discord_invite.code)

                if not db_invite:
                    # Ensure creator exists in members table before creating invite
                    creator_id = 0  # Default fallback
                    if discord_invite.inviter:
                        try:
                            # Get or create the creator member first
                            creator_member = await self.member_repository.get_by_discord_id(discord_invite.inviter.id)
                            if not creator_member:
                                # Create member if doesn't exist (might be a user who left the server)
                                creator_member = await self.member_repository.create_member(
                                    discord_id=discord_invite.inviter.id,
                                    joined_at=None,  # We don't have join date for invite creators
                                )
                            creator_id = creator_member.id
                        except Exception as e:
                            # If we can't create the member for any reason, use fallback
                            self._log_error("sync_server_invites_creator", e, discord_id=discord_invite.inviter.id)
                            creator_id = 0

                    # Create new invite with proper creator_id
                    db_invite = await self.invite_repository.create_invite(
                        invite_code=discord_invite.code,
                        creator_id=creator_id,
                        uses=discord_invite.uses or 0,  # Handle None values
                        created_at=discord_invite.created_at,
                    )
                else:
                    # Update usage if changed
                    current_uses = discord_invite.uses or 0
                    if db_invite.uses != current_uses:
                        await self.invite_repository.update_invite_usage(
                            discord_invite.code,
                            current_uses,
                        )

                synced_invites[discord_invite.code] = db_invite

            self._log_operation("sync_server_invites", synced_count=len(synced_invites))
            return synced_invites

        except Exception as e:
            self._log_error("sync_server_invites", e)
            return {}

    async def process_invite_usage(
        self, before_invites: dict[str, discord.Invite], after_invites: dict[str, discord.Invite]
    ) -> Optional[Invite]:
        """Process invite usage change and return used invite."""
        try:
            for code, after_invite in after_invites.items():
                before_invite = before_invites.get(code)

                if before_invite and after_invite.uses > before_invite.uses:
                    # This invite was used
                    await self.invite_repository.update_invite_usage(
                        code,
                        after_invite.uses,
                        last_used_at=datetime.now(timezone.utc),
                    )

                    db_invite = await self.invite_repository.get_by_code(code)

                    self._log_operation(
                        "process_invite_usage",
                        invite_code=code,
                        new_uses=after_invite.uses,
                    )

                    return db_invite

            return None

        except Exception as e:
            self._log_error("process_invite_usage", e)
            return None

    async def get_member_invite_stats(self, member_id: int) -> dict[str, Any]:
        """Get comprehensive invite statistics for member."""
        try:
            # Get basic invite stats
            basic_stats = await self.invite_repository.get_invite_stats(member_id)

            # Get invited members
            invited_members = await self.member_repository.get_members_by_inviter(member_id)

            # Get member's invites
            member_invites = await self.invite_repository.get_member_invites(member_id)

            stats = {
                "member_id": member_id,
                "total_invites_created": basic_stats["total_invites"],
                "total_invite_uses": basic_stats["total_uses"],
                "members_currently_invited": len(invited_members),
                "active_invites": len([inv for inv in member_invites]),
                "invite_details": [
                    {
                        "code": invite.id,
                        "uses": invite.uses,
                        "created_at": invite.created_at,
                        "last_used_at": invite.last_used_at,
                    }
                    for invite in member_invites
                ],
            }

            self._log_operation("get_member_invite_stats", member_id=member_id)
            return stats

        except Exception as e:
            self._log_error("get_member_invite_stats", e, member_id=member_id)
            return {}

    async def create_tracked_invite(self, invite: discord.Invite, creator: discord.Member) -> Optional[Invite]:
        """Create tracked invite in database."""
        try:
            # Import InviteQueries to avoid circular imports
            from datasources.queries import InviteQueries

            # Need to get session from somewhere - use member repository's session
            session = self.member_repository.session

            db_invite = await InviteQueries.add_or_update_invite(
                session=session,
                invite_id=invite.code,
                creator_id=creator.id,
                uses=invite.uses,
                created_at=invite.created_at,
            )

            self._log_operation(
                "create_tracked_invite",
                invite_code=invite.code,
                creator_id=creator.id,
            )

            return db_invite

        except Exception as e:
            self._log_error("create_tracked_invite", e, invite_code=invite.code)
            return None

    async def cleanup_expired_invites(self, guild: discord.Guild) -> int:
        """Remove expired/invalid invites from database."""
        try:
            # Get current Discord invites (for future implementation)
            # current_invites = await guild.invites()
            # current_codes = {invite.code for invite in current_invites}

            # Get all database invites (this would need a method to get all)
            # For now, we'll just log this operation

            self._log_operation("cleanup_expired_invites", guild_id=guild.id)
            return 0  # Placeholder

        except Exception as e:
            self._log_error("cleanup_expired_invites", e, guild_id=guild.id)
            return 0
