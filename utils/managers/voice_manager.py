"""Voice system manager for handling voice channel operations."""

import asyncio
import logging
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import discord
from discord import (
    CategoryChannel,
    Member,
    PermissionOverwrite,
    Permissions,
    TextChannel,
    VoiceChannel,
)

from datasources.queries import AutoKickQueries, ChannelPermissionQueries
from utils.errors import PermissionError, ResourceNotFoundError
from utils.managers import BaseManager
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class VoiceManager(BaseManager):
    """Manager for voice channel operations."""

    # Permission value mapping tables
    TOGGLE_MAP = {
        True: lambda pf: None if pf == "manage_messages" else False,
        False: lambda _: True,
        None: lambda _: True,
    }

    DIRECT_MAP = {
        "+": lambda _: True,
        "-": lambda pf: None if pf == "manage_messages" else False,
        None: None,  # Special case - handled separately
    }

    def __init__(self, bot):
        """Initialize the voice manager with a bot instance."""
        super().__init__(bot)
        self.message_sender = MessageSender()
        # Cache for autokick functionality
        self._autokick_cache = {}
        self._cache_initialized = False

    async def is_channel_owner(self, channel: VoiceChannel, member: Member) -> bool:
        """Check if member is the owner of the voice channel.

        Args:
            channel: The voice channel to check
            member: The member to check

        Returns:
            True if the member is the owner, False otherwise
        """
        perms = channel.overwrites_for(member)
        return perms and perms.priority_speaker is True

    async def is_channel_mod(self, channel: VoiceChannel, member: Member) -> bool:
        """Check if member is a moderator of the voice channel.

        Args:
            channel: The voice channel to check
            member: The member to check

        Returns:
            True if the member is a moderator, False otherwise
        """
        perms = channel.overwrites_for(member)
        return perms and perms.manage_messages is True and not perms.priority_speaker

    async def get_permission_level(
        self, channel: VoiceChannel, member: Member
    ) -> Literal["owner", "mod", "none"]:
        """Get the permission level of a member in a voice channel.

        Args:
            channel: The voice channel to check
            member: The member to check

        Returns:
            "owner" if member is the owner, "mod" if member is a moderator, "none" otherwise
        """
        if not channel:
            return "none"

        perms = channel.overwrites_for(member)
        if not perms:
            return "none"

        if perms.priority_speaker:
            return "owner"
        elif perms.manage_messages:
            return "mod"

        return "none"

    async def can_modify_permissions(
        self, channel: VoiceChannel, member: Member, target=None
    ) -> bool:
        """Check if member can modify permissions in a voice channel.

        Args:
            channel: The voice channel to check
            member: The member who wants to modify permissions
            target: The target member or role to modify

        Returns:
            True if the member can modify permissions, False otherwise
        """
        if not channel:
            return False

        permission_level = await self.get_permission_level(channel, member)

        if permission_level == "owner":
            return True
        elif permission_level == "mod" and target:
            target_perms = channel.overwrites_for(target)
            # Mods cannot modify owner or other mod permissions
            if target_perms and (
                target_perms.priority_speaker or target_perms.manage_messages
            ):
                return False
            return True

        return False

    def _determine_new_permission_value(
        self,
        current_perms: PermissionOverwrite,
        permission_flag: str,
        value: Optional[Literal["+", "-"]],
        default_to_true: bool = False,
        toggle: bool = False,
        **kwargs,
    ) -> Optional[bool]:
        """Determine the new permission value based on the current permissions.

        Args:
            current_perms: Current permission overwrites
            permission_flag: The permission flag to check
            value: The value to set the permission to ("+" for True, "-" for False, None for toggle)
            default_to_true: Whether to default to True if the permission is None
            toggle: Whether to toggle the permission

        Returns:
            The new permission value
        """
        # Get current permission value
        current_value = getattr(current_perms, permission_flag)

        # Handle toggle mode
        if toggle:
            if value is not None:
                # If value is explicitly specified, use that instead of toggling
                return True if value == "+" else False
            else:
                # Otherwise toggle based on current value
                return self.TOGGLE_MAP.get(current_value, lambda _: True)(
                    permission_flag
                )

        # Handle direct mode
        if value is None:
            # If no explicit value is provided, use the default
            value = "+" if default_to_true else "-"

        # Map the value using the direct map
        return self.DIRECT_MAP.get(value, lambda _: None)(permission_flag)

    async def modify_channel_permission(
        self,
        channel: VoiceChannel,
        target: Union[Member, discord.Role],
        permission_flag: str,
        value: Optional[Literal["+", "-"]],
        update_db: Optional[Literal["+", "-"]],
        default_to_true: bool = False,
        toggle: bool = False,
        guild_id: Optional[int] = None,
    ) -> bool:
        """Modify a permission for a target in a voice channel.

        Args:
            channel: The voice channel to modify
            target: The target member or role to modify
            permission_flag: The permission flag to modify
            value: The value to set the permission to ("+" for True, "-" for False, None for toggle)
            update_db: Whether to update the database ("+" to add/update, "-" to remove)
            default_to_true: Whether to default to True if the permission is None
            toggle: Whether to toggle the permission
            guild_id: The guild ID for database operations

        Returns:
            True if the permission was modified, False otherwise
        """
        # Get current permission overwrites
        current_perms = channel.overwrites_for(target)

        # Determine the new permission value
        new_value = self._determine_new_permission_value(
            current_perms, permission_flag, value, default_to_true, toggle
        )

        # Update the permission overwrites
        new_perms = current_perms
        setattr(new_perms, permission_flag, new_value)

        try:
            # Apply the new permission overwrites
            await channel.set_permissions(
                target, overwrite=new_perms, reason="Modified voice channel permissions"
            )

            # Update the database if requested
            if update_db and guild_id:
                allow_value = 0
                deny_value = 0

                # Convert the permission overwrites to bitfield values
                for perm_name, perm_value in new_perms._values.items():
                    if perm_value is True:
                        allow_value |= getattr(Permissions, perm_name).flag
                    elif perm_value is False:
                        deny_value |= getattr(Permissions, perm_name).flag

                # Update the database
                async with self.bot.get_db() as session:
                    if update_db == "+":
                        await ChannelPermissionQueries.add_or_update_permission(
                            session,
                            guild_id,
                            target.id,
                            allow_value,
                            deny_value,
                            self.bot.guild.id,
                        )
                    elif update_db == "-":
                        await ChannelPermissionQueries.remove_permission(
                            session, guild_id, target.id
                        )

                    await session.commit()

            return True

        except Exception as e:
            logger.error(f"Error modifying channel permission: {e}", exc_info=True)
            return False

    async def get_default_permission_overwrites(
        self, guild: discord.Guild, owner: Member
    ) -> Dict[Union[Member, discord.Role], PermissionOverwrite]:
        """Get the default permission overwrites for a new voice channel.

        Args:
            guild: The guild to get roles from
            owner: The owner of the channel

        Returns:
            A dictionary of permission overwrites
        """
        # Initialize mute roles dictionary
        mute_roles = {
            role["description"]: guild.get_role(role["id"])
            for role in self.bot.config["mute_roles"]
        }

        # Set up permission overwrites
        return {
            mute_roles["stream_off"]: PermissionOverwrite(stream=False),
            mute_roles["send_messages_off"]: PermissionOverwrite(send_messages=False),
            mute_roles["attach_files_off"]: PermissionOverwrite(
                attach_files=False, embed_links=False, external_emojis=False
            ),
            owner: PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                priority_speaker=True,
                manage_messages=True,
            ),
        }

    def get_clean_everyone_permissions(self) -> PermissionOverwrite:
        """Get clean/default permissions for @everyone role in max/public channels."""
        return PermissionOverwrite(
            view_channel=None,
            connect=None,
            speak=None,
            stream=None,
            use_voice_activation=None,
            priority_speaker=None,
            mute_members=None,
            deafen_members=None,
            move_members=None,
            manage_messages=None,
            send_messages=None,
            embed_links=None,
            attach_files=None,
            add_reactions=None,
            external_emojis=None,
            manage_channels=None,
            create_instant_invite=None,
        )

    def get_default_user_limit(self, category_id: int) -> int:
        """Get the default user limit for a channel based on its category.

        Args:
            category_id: The category ID to check

        Returns:
            The default user limit
        """
        config = self.bot.config.get("default_user_limits", {})

        # Check git and public categories
        for cat_type in ["git_categories", "public_categories"]:
            cat_config = config.get(cat_type, {})
            if category_id in cat_config.get("categories", []):
                return cat_config.get("limit", 0)

        # Check max categories
        max_categories = config.get("max_categories", {})
        for max_type, max_config in max_categories.items():
            if category_id == max_config.get("id"):
                return max_config.get("limit", 0)

        return 0  # Default: no limit

    async def set_channel_limit(self, channel: VoiceChannel, max_members: int) -> bool:
        """Set the member limit for a voice channel.

        Args:
            channel: The voice channel to modify
            max_members: The maximum number of members allowed in the channel

        Returns:
            True if the limit was set, False otherwise
        """
        try:
            if max_members > 99:
                max_members = 0  # Set to 0 for unlimited
            elif max_members < 0:
                max_members = 0

            await channel.edit(user_limit=max_members)
            return True

        except Exception as e:
            logger.error(f"Error setting channel limit: {e}", exc_info=True)
            return False

    async def reset_channel_permissions(
        self, channel: VoiceChannel, member: Member
    ) -> bool:
        """Reset all permissions for a channel.

        Args:
            channel: The voice channel to reset
            member: The member requesting the reset

        Returns:
            True if permissions were reset, False otherwise
        """
        try:
            # Check if member is the owner
            if not await self.is_channel_owner(channel, member):
                raise PermissionError("Only the channel owner can reset permissions")

            # Get all overwrites except for the owner
            overwrites_to_remove = []
            for target, _ in channel.overwrites.items():
                if isinstance(target, Member) and await self.is_channel_owner(
                    channel, target
                ):
                    continue  # Skip owner
                overwrites_to_remove.append(target)

            # Remove all overwrites
            for target in overwrites_to_remove:
                await channel.set_permissions(target, overwrite=None)

            # Update database - remove all permissions for this channel except owner
            async with self.bot.get_db() as session:
                for target in overwrites_to_remove:
                    await ChannelPermissionQueries.remove_permission(
                        session, member.guild.id, target.id
                    )

                await session.commit()

            return True

        except Exception as e:
            logger.error(f"Error resetting channel permissions: {e}", exc_info=True)
            return False

    async def reset_user_permissions(
        self, channel: VoiceChannel, member: Member, target: Member
    ) -> bool:
        """Reset permissions for a specific user in a channel.

        Args:
            channel: The voice channel to modify
            member: The member requesting the reset
            target: The target member to reset permissions for

        Returns:
            True if permissions were reset, False otherwise
        """
        try:
            # Check if member can modify target's permissions
            if not await self.can_modify_permissions(channel, member, target):
                raise PermissionError(
                    "You don't have permission to reset this user's permissions"
                )

            # Remove the target's overwrites
            await channel.set_permissions(target, overwrite=None)

            # Update database
            async with self.bot.get_db() as session:
                await ChannelPermissionQueries.remove_permission(
                    session, member.guild.id, target.id
                )

                await session.commit()

            return True

        except Exception as e:
            logger.error(f"Error resetting user permissions: {e}", exc_info=True)
            return False

    # AutoKick functionality

    async def _initialize_autokick_cache(self):
        """Initialize the autokick cache with data from database."""
        if self._cache_initialized:
            return

        try:
            async with self.bot.get_db() as session:
                autokicks = await AutoKickQueries.get_all_autokicks(session)

                # Clear existing cache
                self._autokick_cache.clear()

                # Build the cache
                for autokick in autokicks:
                    if autokick.target_id not in self._autokick_cache:
                        self._autokick_cache[autokick.target_id] = set()

                    self._autokick_cache[autokick.target_id].add(autokick.owner_id)

                self._cache_initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize autokick cache: {e}", exc_info=True)

    async def add_autokick(self, member: Member, target: Member) -> bool:
        """Add a user to the autokick list.

        Args:
            member: The member adding the autokick
            target: The target member to autokick

        Returns:
            True if the autokick was added, False otherwise
        """
        try:
            # Initialize cache if needed
            await self._initialize_autokick_cache()

            # Add to database
            async with self.bot.get_db() as session:
                await AutoKickQueries.add_autokick(session, member.id, target.id)
                await session.commit()

            # Update cache
            if target.id not in self._autokick_cache:
                self._autokick_cache[target.id] = set()

            self._autokick_cache[target.id].add(member.id)

            return True

        except Exception as e:
            logger.error(f"Error adding autokick: {e}", exc_info=True)
            return False

    async def remove_autokick(self, member: Member, target: Member) -> bool:
        """Remove a user from the autokick list.

        Args:
            member: The member removing the autokick
            target: The target member to remove from autokick list

        Returns:
            True if the autokick was removed, False otherwise
        """
        try:
            # Initialize cache if needed
            await self._initialize_autokick_cache()

            # Remove from database
            async with self.bot.get_db() as session:
                await AutoKickQueries.remove_autokick(session, member.id, target.id)
                await session.commit()

            # Update cache
            if (
                target.id in self._autokick_cache
                and member.id in self._autokick_cache[target.id]
            ):
                self._autokick_cache[target.id].remove(member.id)

                # Clean up empty sets
                if not self._autokick_cache[target.id]:
                    del self._autokick_cache[target.id]

            return True

        except Exception as e:
            logger.error(f"Error removing autokick: {e}", exc_info=True)
            return False

    async def get_autokicks(self, member: Member) -> List[int]:
        """Get the list of users in the autokick list for a member.

        Args:
            member: The member to get autokicks for

        Returns:
            List of user IDs in the autokick list
        """
        try:
            # Initialize cache if needed
            await self._initialize_autokick_cache()

            # Get all targets that have this member as an owner
            targets = []
            for target_id, owner_ids in self._autokick_cache.items():
                if member.id in owner_ids:
                    targets.append(target_id)

            return targets

        except Exception as e:
            logger.error(f"Error getting autokicks: {e}", exc_info=True)
            return []

    async def should_autokick(self, member: Member, channel: VoiceChannel) -> bool:
        """Check if a member should be autokicked from a voice channel.

        Args:
            member: The member to check
            channel: The voice channel to check

        Returns:
            True if the member should be autokicked, False otherwise
        """
        try:
            # Initialize cache if needed
            await self._initialize_autokick_cache()

            # Skip if member not in autokick cache
            if member.id not in self._autokick_cache:
                return False

            # Check all channel members
            for channel_member in channel.members:
                # If any channel member has this person in their autokick list
                if channel_member.id in self._autokick_cache.get(member.id, set()):
                    # Get permission level
                    perm_level = await self.get_permission_level(
                        channel, channel_member
                    )

                    # Owner/Mod can autokick
                    if perm_level in ["owner", "mod"]:
                        return True

            return False

        except Exception as e:
            logger.error(f"Error checking autokick: {e}", exc_info=True)
            return False
