"""Utility module for managing channel permissions."""

import logging

import discord
from discord import Member, PermissionOverwrite

from core.repositories.channel_repository import ChannelRepository

logger = logging.getLogger(__name__)


class ChannelPermissionManager:
    """Manages channel permissions and their synchronization with the database."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    def get_default_permission_overwrites(self, guild: discord.Guild, owner: Member) -> dict:
        """
        Get the default permission overwrites for a voice channel.

        Args:
            guild: The guild to get roles from
            owner: The channel owner to set permissions for

        Returns:
            dict: A dictionary of permission overwrites
        """
        # Initialize mute roles dictionary - filter out None values
        mute_roles = {}
        for role_config in self.bot.config["mute_roles"]:
            role = guild.get_role(role_config["id"])
            if role:  # Only add if role exists
                mute_roles[role_config["description"]] = role
            else:
                logger.warning(f"Mute role {role_config['description']} (ID: {role_config['id']}) not found in guild")

        # Set up permission overwrites - only add if roles exist
        overwrites = {
            owner: PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                priority_speaker=True,
                manage_messages=True,
            ),
        }

        # Add mute role overwrites if they exist
        if mute_roles.get("stream_off"):
            overwrites[mute_roles["stream_off"]] = PermissionOverwrite(stream=False)
        if mute_roles.get("send_messages_off"):
            overwrites[mute_roles["send_messages_off"]] = PermissionOverwrite(send_messages=False)
        if mute_roles.get("attach_files_off"):
            overwrites[mute_roles["attach_files_off"]] = PermissionOverwrite(
                attach_files=False, embed_links=False, external_emojis=False
            )

        return overwrites

    async def reset_user_permissions(self, channel: discord.VoiceChannel, owner: Member, target: Member):
        """
        Reset permissions for a specific user.

        Args:
            channel: The voice channel to reset permissions in
            owner: The channel owner
            target: The user to reset permissions for
        """
        # Remove permissions from channel
        await channel.set_permissions(target, overwrite=None)

        # Remove permissions from database
        async with self.bot.get_db() as session:
            channel_repo = ChannelRepository(session)
            await channel_repo.remove_permission(owner.id, target.id)

    async def reset_channel_permissions(self, channel: discord.VoiceChannel, owner: Member):
        """
        Reset all channel permissions to default.

        Args:
            channel: The voice channel to reset permissions in
            owner: The channel owner
        """
        # Get default permission overwrites
        permission_overwrites = self.get_default_permission_overwrites(channel.guild, owner)

        # Reset channel permissions
        await channel.edit(overwrites=permission_overwrites)

        # Clear database permissions for this channel owner
        async with self.bot.get_db() as session:
            channel_repo = ChannelRepository(session)
            await channel_repo.remove_all_permissions(owner.id)

    async def add_db_overwrites_to_permissions(
        self, guild: discord.Guild, member_id: int, permission_overwrites: dict
    ) -> dict:
        """
        Fetch permissions from the database and add them to the provided permission_overwrites dict.

        Args:
            guild: The guild to get members/roles from
            member_id: The ID of the member whose permissions to fetch
            permission_overwrites: The existing permission overwrites to add to

        Returns:
            dict: Additional overwrites that couldn't be added to the main dict
        """
        remaining_overwrites = {}
        async with self.bot.get_db() as session:
            channel_repo = ChannelRepository(session)
            member_permissions = await channel_repo.get_permissions_for_member(member_id, limit=95)
            self.logger.info(f"Found {len(member_permissions)} permissions in database for member {member_id}")

        for permission in member_permissions:
            allow_permissions = discord.Permissions(permission.allow_permissions_value)
            deny_permissions = discord.Permissions(permission.deny_permissions_value)
            overwrite = PermissionOverwrite.from_pair(allow_permissions, deny_permissions)
            self.logger.info(
                f"Processing permission for target {permission.target_id}: "
                f"allow={permission.allow_permissions_value}, deny={permission.deny_permissions_value}"
            )

            # Convert target_id to appropriate Discord object
            target = guild.get_member(permission.target_id) or guild.get_role(permission.target_id)
            if target:
                if target in permission_overwrites:
                    # If target already exists in main permissions, add new permissions to it
                    for key, value in overwrite._values.items():
                        if value is not None:
                            setattr(permission_overwrites[target], key, value)
                            self.logger.info(f"Updated existing permission {key}={value} for {target}")
                else:
                    # If target doesn't exist in main permissions, add to remaining
                    remaining_overwrites[target] = overwrite
                    self.logger.info(f"Added to remaining overwrites for {target}")

        return remaining_overwrites

    async def add_remaining_overwrites(self, channel: discord.VoiceChannel, remaining_overwrites: dict):
        """
        Add remaining overwrites to the channel.

        Args:
            channel: The voice channel to add overwrites to
            remaining_overwrites: The overwrites to add
        """
        for target, overwrite in remaining_overwrites.items():
            try:
                await channel.set_permissions(target, overwrite=overwrite)
            except discord.errors.NotFound:
                self.logger.warning(f"Target {target.id} not found while adding remaining overwrites")
            except Exception as e:
                self.logger.error(f"Error adding overwrite for {target.id}: {str(e)}")
