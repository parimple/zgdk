"""Event handler for voice state updates."""

import asyncio
import logging
import random

import discord
from discord.ext import commands

from utils.channel_permissions import ChannelPermissionManager
from utils.message_sender import MessageSender
from utils.voice.autokick import AutoKickManager

logger = logging.getLogger(__name__)


class OnVoiceStateUpdateEvent(commands.Cog):
    """Class for handling the event when a member's voice state is updated."""

    def __init__(self, bot):
        self.bot = bot
        self.guild = bot.get_guild(self.bot.config["guild_id"])
        self.logger = logging.getLogger(__name__)
        self.message_sender = MessageSender(bot)
        self.channel_permission_manager = ChannelPermissionManager(bot)
        self.autokick_manager = AutoKickManager(bot)

        self.channels_create = self.bot.config["channels_create"]
        self.vc_categories = self.bot.config["vc_categories"]

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle the event when a member joins or leaves a voice channel."""
        # Check for autokicks when a member joins a voice channel
        if after.channel and before.channel != after.channel:
            if member.id != self.bot.config["owner_id"]:
                await self.handle_autokicks(member, after.channel)

            if after.channel and after.channel.id in self.channels_create:
                await self.handle_create_channel(member, after)
            elif after.channel and after.channel.id == self.bot.config["channels_voice"]["afk"]:
                return

        if (
            before.channel
            and before.channel != after.channel
            and before.channel.type == discord.ChannelType.voice
            and len(before.channel.members) == 0
        ):
            await self.handle_channel_leave(before)

    async def handle_autokicks(self, member, channel):
        """Handle autokicks for a member joining a voice channel"""
        if channel.id == self.bot.config["channels_voice"]["afk"]:
            return

        # Check if member should be autokicked using AutoKickManager
        if await self.autokick_manager.check_autokick(member, channel):
            try:
                # Find the owner who has autokick on this member
                owner = None
                for owner_id in self.autokick_manager._autokick_cache[member.id]:
                    potential_owner = channel.guild.get_member(owner_id)
                    if potential_owner and potential_owner in channel.members:
                        owner = potential_owner
                        break

                if not owner:
                    return

                # Move member to AFK channel
                afk_channel = self.guild.get_channel(self.bot.config["channels_voice"]["afk"])
                if afk_channel:
                    await member.move_to(afk_channel)
                else:
                    await member.move_to(None)

                # Set connect permission to False
                current_perms = channel.overwrites_for(member) or discord.PermissionOverwrite()
                current_perms.connect = False
                await channel.set_permissions(member, overwrite=current_perms)

                # Send notification
                await self.message_sender.send_autokick_notification(channel, member, owner)
            except discord.Forbidden:
                self.logger.warning(f"Failed to autokick {member.id} (no permission)")
            except Exception as e:
                self.logger.error(f"Failed to autokick {member.id}: {str(e)}")

    async def handle_create_channel(self, member, after):
        """
        Handle the creation of a new voice channel when a member joins a creation channel.

        :param member: Member object representing the joining member
        :param after: VoiceState object representing the state after the update
        """
        # Determine channel name based on category
        channel_name = member.display_name
        category_id = after.channel.category.id if after.channel.category else None

        logger.info(f"Creating channel in category: {category_id}")
        logger.info(f"Available formats: {self.bot.config.get('channel_name_formats', {}).keys()}")

        # Check if category has a custom format
        formats = self.bot.config.get("channel_name_formats", {})
        format_key = category_id  # próbuj najpierw jako int
        if format_key not in formats:
            format_key = str(category_id)  # spróbuj jako string

        if format_key in formats:
            # Get random emoji
            emoji = random.choice(self.bot.config.get("channel_emojis", ["🎮"]))
            # Apply the format
            channel_name = formats[format_key].format(emoji=emoji)
            logger.info(f"Using format for category {category_id}: {channel_name}")
        else:
            logger.info(
                f"No format found for category {category_id}, using default name: {channel_name}"
            )

        # Get default permission overwrites
        permission_overwrites = self.channel_permission_manager.get_default_permission_overwrites(
            self.guild, member
        )

        # Add permissions from database and combine them with default overwrites
        db_overwrites = await self.channel_permission_manager.add_db_overwrites_to_permissions(
            self.guild, member.id, permission_overwrites
        )

        # Combine all overwrites before channel creation
        if db_overwrites:
            for target, overwrite in db_overwrites.items():
                if target in permission_overwrites:
                    # Update existing overwrite
                    current = permission_overwrites[target]
                    for perm, value in overwrite._values.items():
                        if value is not None:
                            setattr(current, perm, value)
                else:
                    # Add new overwrite
                    permission_overwrites[target] = overwrite

        # Create the new channel with all permissions
        new_channel = await self.guild.create_voice_channel(
            channel_name,
            category=after.channel.category,
            bitrate=self.guild.bitrate_limit,
            user_limit=after.channel.user_limit,
            overwrites=permission_overwrites,
        )

        await member.move_to(new_channel)

        # Send channel creation info
        await self.message_sender.send_channel_creation_info(new_channel, member)

    async def handle_channel_leave(self, before):
        """
        Handle the deletion of a voice channel when all members leave.

        :param before: VoiceState object representing the state before the update
        """
        # Nie usuwamy kanałów create ani AFK
        if (
            before.channel.id in self.channels_create
            or before.channel.id == self.bot.config["channels_voice"]["afk"]
        ):
            return

        # Usuwamy tylko kanały w kategoriach głosowych
        if before.channel.category and before.channel.category.id in self.vc_categories:
            await before.channel.delete()


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnVoiceStateUpdateEvent(bot))
