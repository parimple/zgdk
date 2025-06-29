"""Moderation service for managing server moderation actions."""

import logging
from datetime import datetime, timezone
from typing import Optional

import discord

from core.interfaces.member_interfaces import (
    IMemberRepository,
    IModerationRepository,
    IModerationService,
)
from core.services.base_service import BaseService
from datasources.models import ModerationLog

logger = logging.getLogger(__name__)


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
