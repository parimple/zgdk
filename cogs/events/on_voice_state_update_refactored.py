"""Event handler for voice state updates."""

import asyncio
import logging
import random
from collections import deque
from datetime import datetime

import discord
from discord.ext import commands

from utils.message_sender import MessageSender
from utils.services.voice_service import VoiceService

logger = logging.getLogger(__name__)


class FakeContext:
    """A fake context class to provide bot and guild attributes."""

    def __init__(self, bot, guild):
        self.bot = bot
        self.guild = guild


class OnVoiceStateUpdateEventRefactored(commands.Cog):
    """Class for handling the event when a member's voice state is updated."""

    def __init__(self, bot):
        """Initialize the event handler."""
        self.bot = bot
        self.guild = None
        self.logger = logging.getLogger(__name__)
        self.message_sender = MessageSender(bot)
        self.voice_service = VoiceService(bot)

        self.channels_create = self.bot.config["channels_create"]
        self.vc_categories = self.bot.config["vc_categories"]

        # Queue for autokick operations
        self.autokick_queue = asyncio.Queue()
        self.autokick_worker_task = None

        # Cache for categories and their configuration
        self._category_config_cache = {}
        self._empty_channels_cache = {}
        self._cache_refresh_time = 0

        # Performance metrics
        self.metrics = {
            "voice_joins": 0,
            "voice_leaves": 0,
            "autokicks": 0,
            "channels_created": 0,
            "channels_deleted": 0,
            "permissions_restored": 0,
        }

    @commands.Cog.listener()
    async def on_ready(self):
        """Start the autokick worker when the bot is ready."""
        self.guild = self.bot.guild
        self.autokick_worker_task = asyncio.create_task(self.autokick_worker())
        self.logger.info("Started autokick worker task")

    async def cog_unload(self):
        """Clean up tasks when the cog is unloaded."""
        if self.autokick_worker_task:
            self.autokick_worker_task.cancel()
            try:
                await self.autokick_worker_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Stopped autokick worker task")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates."""
        if member.bot:
            return  # Ignore bots

        # Get the channels
        before_channel = before.channel
        after_channel = after.channel

        # Check for joins and leaves
        is_join = before_channel is None and after_channel is not None
        is_leave = before_channel is not None and after_channel is None
        is_move = (
            before_channel is not None
            and after_channel is not None
            and before_channel != after_channel
        )

        # Update metrics
        if is_join:
            self.metrics["voice_joins"] += 1
        if is_leave:
            self.metrics["voice_leaves"] += 1

        # Handle autokick
        if after_channel:
            await self.handle_potential_autokick(member, after_channel)

        # Handle channel creation
        if is_join or is_move:
            await self.handle_channel_creation(member, after_channel)

        # Handle channel deletion
        if is_leave or is_move:
            await self.handle_empty_channel(before_channel)

    async def autokick_worker(self):
        """Worker that processes autokick operations from the queue."""
        while True:
            try:
                # Get the next autokick operation from the queue
                member, channel = await self.autokick_queue.get()

                # Check if the member is still in the channel
                if channel in member.guild.voice_channels and member in channel.members:
                    # Check if the member should be autokicked
                    should_kick = await self.voice_service.should_autokick(member, channel)

                    if should_kick:
                        try:
                            await member.move_to(None)
                            self.metrics["autokicks"] += 1
                            self.logger.info(
                                f"Autokicked {member.display_name} from {channel.name}"
                            )
                        except discord.Forbidden:
                            self.logger.warning(
                                f"Failed to autokick {member.display_name} - missing permissions"
                            )
                        except discord.HTTPException as e:
                            self.logger.error(f"HTTP error autokicking {member.display_name}: {e}")
                        except Exception as e:
                            self.logger.error(f"Error autokicking {member.display_name}: {e}")

                # Mark the task as done
                self.autokick_queue.task_done()

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                # Task was cancelled, exit the loop
                break
            except Exception as e:
                self.logger.error(f"Error in autokick worker: {e}")
                await asyncio.sleep(1)  # Delay before retrying

    async def handle_potential_autokick(self, member, channel):
        """Handle potential autokick by adding to the queue."""
        # Add to the autokick queue
        await self.autokick_queue.put((member, channel))

    async def handle_channel_creation(self, member, channel):
        """Handle channel creation for join channels."""
        # Skip if channel is not in a VC category
        if not channel.category or channel.category.id not in self.vc_categories:
            return

        # Skip if channel is not a join channel
        if channel.id not in self.channels_create:
            return

        # Get the category for the new channel
        target_category = channel.category

        # Generate a random name if needed
        channel_name = f"{member.display_name}'s channel"

        try:
            # Create the new channel
            new_channel = await target_category.create_voice_channel(
                name=channel_name,
                bitrate=channel.bitrate,
                user_limit=0,  # No limit by default
                reason=f"Created by {member.display_name}",
            )

            # Get default permission overwrites
            overwrites = await self.voice_service.voice_manager.get_default_permission_overwrites(
                self.guild, member
            )

            # Apply the overwrites
            for target, overwrite in overwrites.items():
                await new_channel.set_permissions(target, overwrite=overwrite)

            # Move the member to the new channel
            await member.move_to(new_channel)

            # Update metrics
            self.metrics["channels_created"] += 1
            self.logger.info(f"Created new channel {new_channel.name} for {member.display_name}")

        except discord.Forbidden:
            self.logger.warning(
                f"Failed to create channel for {member.display_name} - missing permissions"
            )
        except discord.HTTPException as e:
            self.logger.error(f"HTTP error creating channel for {member.display_name}: {e}")
        except Exception as e:
            self.logger.error(f"Error creating channel for {member.display_name}: {e}")

    async def handle_empty_channel(self, channel):
        """Handle empty channel deletion."""
        if not channel:
            return

        # Skip if channel is not in a VC category
        if not channel.category or channel.category.id not in self.vc_categories:
            return

        # Skip if channel is a join channel
        if channel.id in self.channels_create:
            return

        # Check if the channel is empty
        if len(channel.members) == 0:
            try:
                # Delay the deletion to avoid deleting channels that are being joined
                await asyncio.sleep(5)

                # Check again if the channel is still empty
                fetched_channel = self.guild.get_channel(channel.id)
                if not fetched_channel or len(fetched_channel.members) > 0:
                    return

                # Delete the channel
                await fetched_channel.delete(reason="Empty voice channel")

                # Update metrics
                self.metrics["channels_deleted"] += 1
                self.logger.info(f"Deleted empty channel {channel.name}")

            except discord.Forbidden:
                self.logger.warning(
                    f"Failed to delete channel {channel.name} - missing permissions"
                )
            except discord.HTTPException as e:
                self.logger.error(f"HTTP error deleting channel {channel.name}: {e}")
            except Exception as e:
                self.logger.error(f"Error deleting channel {channel.name}: {e}")


async def setup(bot: commands.Bot):
    """Setup function for OnVoiceStateUpdateEventRefactored."""
    await bot.add_cog(OnVoiceStateUpdateEventRefactored(bot))
