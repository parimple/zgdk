"""Auto-kick service for voice channels."""

import logging
from typing import List

import discord

from core.interfaces.voice_interfaces import IAutoKickService
from core.repositories.channel_repository import ChannelRepository
from core.services.base_service import BaseService


class AutoKickService(BaseService, IAutoKickService):
    """Service for managing auto-kick functionality."""

    def __init__(self, channel_repository: ChannelRepository, **kwargs):
        """Initialize auto-kick service."""
        super().__init__(**kwargs)
        self.channel_repository = channel_repository
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate auto-kick operation."""
        return True

    async def add_autokick(
        self,
        channel_id: int,
        target_id: int,
        member_id: int,
    ) -> bool:
        """Add a user to auto-kick list."""
        try:
            # Check if already exists
            existing = await self.channel_repository.get_autokick_entry(
                channel_id, target_id
            )
            
            if existing:
                self.logger.info(
                    f"User {target_id} already in auto-kick list for channel {channel_id}"
                )
                return False

            # Add to database
            await self.channel_repository.add_autokick(
                channel_id=channel_id,
                target_id=target_id,
                added_by=member_id
            )
            await self.channel_repository.session.commit()

            self._log_operation(
                "add_autokick",
                {
                    "channel_id": channel_id,
                    "target_id": target_id,
                    "added_by": member_id
                }
            )

            return True

        except Exception as e:
            self.logger.error(f"Error adding autokick: {e}")
            return False

    async def remove_autokick(
        self,
        channel_id: int,
        target_id: int,
    ) -> bool:
        """Remove a user from auto-kick list."""
        try:
            # Remove from database
            result = await self.channel_repository.remove_autokick(
                channel_id, target_id
            )
            
            if not result:
                self.logger.info(
                    f"User {target_id} not in auto-kick list for channel {channel_id}"
                )
                return False

            await self.channel_repository.session.commit()

            self._log_operation(
                "remove_autokick",
                {
                    "channel_id": channel_id,
                    "target_id": target_id
                }
            )

            return True

        except Exception as e:
            self.logger.error(f"Error removing autokick: {e}")
            return False

    async def check_autokick(
        self,
        channel: discord.VoiceChannel,
        member: discord.Member,
    ) -> bool:
        """Check if a member should be auto-kicked from channel."""
        try:
            # Check if user is in auto-kick list
            entry = await self.channel_repository.get_autokick_entry(
                channel.id, member.id
            )
            
            if entry:
                # Kick the member
                try:
                    await member.move_to(None, reason="Auto-kick")
                    
                    self._log_operation(
                        "autokick_executed",
                        {
                            "channel_id": channel.id,
                            "member_id": member.id
                        }
                    )
                    
                    return True
                except discord.Forbidden:
                    self.logger.warning(
                        f"No permission to kick {member} from {channel}"
                    )
                except Exception as e:
                    self.logger.error(f"Error kicking member: {e}")

            return False

        except Exception as e:
            self.logger.error(f"Error checking autokick: {e}")
            return False

    async def get_autokick_list(
        self, channel_id: int
    ) -> List[int]:
        """Get list of auto-kicked users for a channel."""
        try:
            entries = await self.channel_repository.get_channel_autokicks(channel_id)
            return [entry.target_id for entry in entries]

        except Exception as e:
            self.logger.error(f"Error getting autokick list: {e}")
            return []