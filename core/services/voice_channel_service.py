"""Voice channel management service."""

import logging
from typing import List, Optional

import discord

from core.interfaces.voice_interfaces import IVoiceChannelService
from core.repositories.channel_repository import ChannelRepository
from core.services.base_service import BaseService


class VoiceChannelService(BaseService, IVoiceChannelService):
    """Service for managing voice channels."""

    def __init__(self, channel_repository: ChannelRepository, bot, **kwargs):
        """Initialize voice channel service."""
        super().__init__(**kwargs)
        self.channel_repository = channel_repository
        self.bot = bot
        self.config = bot.config
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate voice channel operation."""
        return True

    async def create_voice_channel(
        self,
        member: discord.Member,
        category: discord.CategoryChannel,
        name: Optional[str] = None,
    ) -> discord.VoiceChannel:
        """Create a new voice channel for a member."""
        try:
            # Get channel name format from config
            channel_name = name or f"{member.display_name}'s Channel"
            
            # Check for emojis in config
            emojis = self.config.get("channel_emojis", [])
            if emojis and category.id in self.config.get("channel_name_formats", {}):
                import random
                emoji = random.choice(emojis)
                format_str = self.config["channel_name_formats"][category.id]
                channel_name = format_str.format(emoji=emoji)

            # Create channel with proper permissions
            overwrites = {
                member.guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True
                ),
                member: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    manage_channels=True,
                    manage_permissions=True,
                    move_members=True,
                    mute_members=True,
                    deafen_members=True
                ),
            }

            # Create the channel
            channel = await category.create_voice_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Created by {member}"
            )

            # Save to database
            await self.channel_repository.add_voice_channel(
                channel_id=channel.id,
                guild_id=member.guild.id,
                owner_id=member.id,
                category_id=category.id
            )
            await self.channel_repository.session.commit()

            self._log_operation(
                "create_voice_channel",
                {"member_id": member.id, "channel_id": channel.id}
            )

            return channel

        except Exception as e:
            self.logger.error(f"Error creating voice channel: {e}")
            raise

    async def delete_voice_channel(
        self, channel: discord.VoiceChannel, reason: str = "Channel cleanup"
    ) -> bool:
        """Delete a voice channel."""
        try:
            # Remove from database first
            await self.channel_repository.remove_voice_channel(channel.id)
            await self.channel_repository.session.commit()

            # Delete the channel
            await channel.delete(reason=reason)

            self._log_operation(
                "delete_voice_channel",
                {"channel_id": channel.id, "reason": reason}
            )

            return True

        except Exception as e:
            self.logger.error(f"Error deleting voice channel: {e}")
            return False

    async def modify_channel_permissions(
        self,
        channel: discord.VoiceChannel,
        target: discord.Member,
        permission_type: str,
        action: str,
    ) -> bool:
        """Modify channel permissions for a user."""
        try:
            # Get current overwrites
            overwrites = channel.overwrites_for(target)

            # Map permission types to Discord permissions
            permission_map = {
                "view": "view_channel",
                "connect": "connect",
                "speak": "speak",
                "text": "send_messages",
                "live": "stream",
            }

            if permission_type not in permission_map:
                return False

            perm_name = permission_map[permission_type]

            # Set permission based on action
            if action == "allow":
                setattr(overwrites, perm_name, True)
            elif action == "deny":
                setattr(overwrites, perm_name, False)
            elif action == "neutral":
                setattr(overwrites, perm_name, None)
            else:
                return False

            # Apply the permissions
            await channel.set_permissions(
                target,
                overwrite=overwrites,
                reason=f"Permission {permission_type} {action} by command"
            )

            # Save to database
            await self.channel_repository.set_channel_permission(
                channel_id=channel.id,
                member_id=target.id,
                permission_type=permission_type,
                value=action
            )
            await self.channel_repository.session.commit()

            self._log_operation(
                "modify_channel_permissions",
                {
                    "channel_id": channel.id,
                    "target_id": target.id,
                    "permission": permission_type,
                    "action": action
                }
            )

            return True

        except Exception as e:
            self.logger.error(f"Error modifying channel permissions: {e}")
            return False

    async def get_member_channels(
        self, member_id: int
    ) -> List[discord.VoiceChannel]:
        """Get all voice channels owned by a member."""
        try:
            # Get channel IDs from database
            db_channels = await self.channel_repository.get_member_channels(member_id)
            
            # Convert to Discord channel objects
            channels = []
            for db_channel in db_channels:
                channel = self.bot.get_channel(db_channel.channel_id)
                if channel and isinstance(channel, discord.VoiceChannel):
                    channels.append(channel)

            return channels

        except Exception as e:
            self.logger.error(f"Error getting member channels: {e}")
            return []