"""Voice service providing an interface to voice channel functionality."""

from typing import List, Literal, Optional, Tuple, Union

import discord
from discord import Member, VoiceChannel

from utils.errors import PermissionError
from utils.managers.voice_manager import VoiceManager
from utils.message_sender import MessageSender
from utils.services import BaseService


class VoiceService(BaseService):
    """Service for handling voice channel operations."""

    def __init__(self, bot):
        """Initialize the voice service with a bot instance."""
        super().__init__(bot)
        self.voice_manager = VoiceManager(bot)
        self.message_sender = MessageSender()

    async def get_permission_level(
        self, ctx, channel: Optional[VoiceChannel] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """Get the permission level of a member in a voice channel.

        Args:
            ctx: The command context
            channel: The voice channel to check (defaults to member's current voice channel)

        Returns:
            Tuple of (success, message, permission_level)
        """
        try:
            # Check if member is in a voice channel
            if not channel and not ctx.author.voice:
                return False, "You are not in a voice channel", None

            # Use the current voice channel if none is specified
            voice_channel = channel or ctx.author.voice.channel

            # Get the permission level
            permission_level = await self.voice_manager.get_permission_level(
                voice_channel, ctx.author
            )

            return True, "Permission level retrieved", permission_level

        except Exception as e:
            return False, f"Error getting permission level: {str(e)}", None

    async def modify_permission(
        self,
        ctx,
        target: Union[Member, discord.Role],
        permission_name: str,
        value: Optional[Literal["+", "-"]] = None,
        toggle: bool = False,
        default_to_true: bool = False,
    ) -> Tuple[bool, str]:
        """Modify a permission for a target in the current voice channel.

        Args:
            ctx: The command context
            target: The target member or role to modify
            permission_name: The permission name to modify
            value: The value to set the permission to ("+" for True, "-" for False, None for toggle)
            toggle: Whether to toggle the permission
            default_to_true: Whether to default to True if the permission is None

        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if member is in a voice channel
            if not ctx.author.voice:
                return False, "You are not in a voice channel"

            voice_channel = ctx.author.voice.channel

            # Check if member can modify permissions
            can_modify = await self.voice_manager.can_modify_permissions(
                voice_channel, ctx.author, target
            )
            if not can_modify:
                return (
                    False,
                    "You don't have permission to modify this target's permissions",
                )

            # Block priority_speaker modification
            if permission_name == "priority_speaker":
                return False, "You cannot modify the priority_speaker permission"

            # Block setting manage_messages for @everyone
            if (
                permission_name == "manage_messages"
                and target == ctx.guild.default_role
            ):
                return False, "You cannot set moderator permissions for @everyone"

            # Modify the permission
            success = await self.voice_manager.modify_channel_permission(
                voice_channel,
                target,
                permission_name,
                value,
                "+",  # Always update database
                default_to_true,
                toggle,
                ctx.guild.id,
            )

            if success:
                # Build a user-friendly message
                value_desc = (
                    "enabled"
                    if value == "+"
                    else "disabled" if value == "-" else "toggled"
                )
                target_desc = (
                    target.name
                    if isinstance(target, discord.Role)
                    else f"{target.display_name}"
                )

                return (
                    True,
                    f"{permission_name.replace('_', ' ').title()} {value_desc} for {target_desc}",
                )
            else:
                return False, "Failed to modify permission"

        except PermissionError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error modifying permission: {str(e)}"

    async def set_channel_limit(self, ctx, max_members: int) -> Tuple[bool, str]:
        """Set the member limit for the current voice channel.

        Args:
            ctx: The command context
            max_members: The maximum number of members allowed in the channel

        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if member is in a voice channel
            if not ctx.author.voice:
                return False, "You are not in a voice channel"

            voice_channel = ctx.author.voice.channel

            # Check if member is the owner or a mod
            permission_level = await self.voice_manager.get_permission_level(
                voice_channel, ctx.author
            )
            if permission_level not in ["owner", "mod"]:
                return False, "You don't have permission to set the channel limit"

            # Format the limit
            if max_members > 99:
                max_members = 0  # Set to 0 for unlimited
            elif max_members < 0:
                max_members = 0

            # Set the limit
            success = await self.voice_manager.set_channel_limit(
                voice_channel, max_members
            )

            if success:
                limit_text = "unlimited" if max_members == 0 else str(max_members)
                return True, f"Channel limit set to {limit_text}"
            else:
                return False, "Failed to set channel limit"

        except Exception as e:
            return False, f"Error setting channel limit: {str(e)}"

    async def reset_channel_permissions(self, ctx) -> Tuple[bool, str]:
        """Reset all permissions for the current voice channel.

        Args:
            ctx: The command context

        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if member is in a voice channel
            if not ctx.author.voice:
                return False, "You are not in a voice channel"

            voice_channel = ctx.author.voice.channel

            # Reset the permissions
            success = await self.voice_manager.reset_channel_permissions(
                voice_channel, ctx.author
            )

            if success:
                return True, "Channel permissions reset successfully"
            else:
                return False, "Failed to reset channel permissions"

        except PermissionError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error resetting channel permissions: {str(e)}"

    async def reset_user_permissions(self, ctx, target: Member) -> Tuple[bool, str]:
        """Reset permissions for a specific user in the current voice channel.

        Args:
            ctx: The command context
            target: The target member to reset permissions for

        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if member is in a voice channel
            if not ctx.author.voice:
                return False, "You are not in a voice channel"

            voice_channel = ctx.author.voice.channel

            # Reset the user's permissions
            success = await self.voice_manager.reset_user_permissions(
                voice_channel, ctx.author, target
            )

            if success:
                return True, f"Permissions reset for {target.display_name}"
            else:
                return False, f"Failed to reset permissions for {target.display_name}"

        except PermissionError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Error resetting user permissions: {str(e)}"

    # AutoKick functionality

    async def add_autokick(self, ctx, target: Member) -> Tuple[bool, str]:
        """Add a user to the autokick list.

        Args:
            ctx: The command context
            target: The target member to autokick

        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if member is in a voice channel
            if not ctx.author.voice:
                return False, "You are not in a voice channel"

            voice_channel = ctx.author.voice.channel

            # Check if member is the owner or a mod
            permission_level = await self.voice_manager.get_permission_level(
                voice_channel, ctx.author
            )
            if permission_level not in ["owner", "mod"]:
                return (
                    False,
                    "You don't have permission to add users to the autokick list",
                )

            # Add to autokick list
            success = await self.voice_manager.add_autokick(ctx.author, target)

            if success:
                return True, f"Added {target.display_name} to your autokick list"
            else:
                return (
                    False,
                    f"Failed to add {target.display_name} to your autokick list",
                )

        except Exception as e:
            return False, f"Error adding autokick: {str(e)}"

    async def remove_autokick(self, ctx, target: Member) -> Tuple[bool, str]:
        """Remove a user from the autokick list.

        Args:
            ctx: The command context
            target: The target member to remove from the autokick list

        Returns:
            Tuple of (success, message)
        """
        try:
            # Remove from autokick list
            success = await self.voice_manager.remove_autokick(ctx.author, target)

            if success:
                return True, f"Removed {target.display_name} from your autokick list"
            else:
                return (
                    False,
                    f"Failed to remove {target.display_name} from your autokick list",
                )

        except Exception as e:
            return False, f"Error removing autokick: {str(e)}"

    async def get_autokicks(self, ctx) -> Tuple[bool, str, Optional[List[int]]]:
        """Get the list of users in the autokick list for a member.

        Args:
            ctx: The command context

        Returns:
            Tuple of (success, message, list of user IDs)
        """
        try:
            # Get autokicks
            target_ids = await self.voice_manager.get_autokicks(ctx.author)

            if target_ids:
                return (
                    True,
                    f"Found {len(target_ids)} users in your autokick list",
                    target_ids,
                )
            else:
                return True, "Your autokick list is empty", []

        except Exception as e:
            return False, f"Error getting autokicks: {str(e)}", None

    async def should_autokick(self, member: Member, channel: VoiceChannel) -> bool:
        """Check if a member should be autokicked from a voice channel.

        Args:
            member: The member to check
            channel: The voice channel to check

        Returns:
            True if the member should be autokicked, False otherwise
        """
        return await self.voice_manager.should_autokick(member, channel)
