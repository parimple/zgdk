"""Autokick functionality for voice channels."""

import logging

import discord
from sqlalchemy import select

from datasources.models import AutoKick
from datasources.queries import AutoKickQueries
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class AutoKickManager:
    """Manages autokick functionality for voice channels."""

    def __init__(self, bot):
        self.bot = bot
        self.message_sender = MessageSender()
        # Cache structure: {target_id: set(owner_ids)}
        self._autokick_cache = {}
        self._cache_initialized = False
        self.logger = logging.getLogger(__name__)

    async def _initialize_cache(self):
        """Initialize the cache with data from database"""
        if self._cache_initialized:
            return

        try:
            async with self.bot.get_db() as session:
                # Get all autokicks using SQLAlchemy ORM
                result = await session.execute(select(AutoKick.target_id, AutoKick.owner_id))
                rows = result.all()

                # Clear existing cache
                self._autokick_cache.clear()

                # Build the cache
                for target_id, owner_id in rows:
                    if target_id not in self._autokick_cache:
                        self._autokick_cache[target_id] = set()
                    self._autokick_cache[target_id].add(owner_id)
                    self.logger.info(f"Added autokick: target={target_id}, owner={owner_id}")

                self.logger.info(f"Cache initialized with {len(rows)} entries")
                self._cache_initialized = True
        except Exception as e:
            self.logger.error(f"Failed to initialize cache: {str(e)}")
            self._cache_initialized = False
            raise

    async def _reset_cache(self):
        """Force reset the cache"""
        self._cache_initialized = False
        self._autokick_cache.clear()
        await self._initialize_cache()

    async def get_autokick_limit(self, member: discord.Member) -> int:
        """Get the autokick limit for a member based on their premium roles."""
        max_autokicks = 0
        for role_config in self.bot.config["premium_roles"]:
            if "auto_kick" in role_config:
                role = discord.utils.get(member.roles, name=role_config["name"])
                if role:
                    max_autokicks = max(max_autokicks, role_config["auto_kick"])
        return max_autokicks

    async def add_autokick(self, ctx, target: discord.Member):
        """Add a member to autokick list."""
        try:
            await self._initialize_cache()
            max_autokicks = await self.get_autokick_limit(ctx.author)

            if max_autokicks == 0:
                await self.message_sender.send_no_autokick_permission(
                    ctx, self.bot.config["channels"]["premium_info"]
                )
                return

            # Check cache for existing autokicks count
            owner_autokicks_count = sum(
                1 for owners in self._autokick_cache.values() if ctx.author.id in owners
            )

            if owner_autokicks_count >= max_autokicks:
                await self.message_sender.send_autokick_limit_reached(
                    ctx, max_autokicks, self.bot.config["channels"]["premium_info"]
                )
                return

            # Check if autokick already exists
            if (
                target.id in self._autokick_cache
                and ctx.author.id in self._autokick_cache[target.id]
            ):
                await self.message_sender.send_autokick_already_exists(ctx, target)
                return

            # Update cache
            if target.id not in self._autokick_cache:
                self._autokick_cache[target.id] = set()
            self._autokick_cache[target.id].add(ctx.author.id)

            # Update database
            async with self.bot.get_db() as session:
                await AutoKickQueries.add_autokick(session, ctx.author.id, target.id)
                self.logger.info(f"Added autokick: owner={ctx.author.id}, target={target.id}")
                await self.message_sender.send_autokick_added(ctx, target)
        except Exception as e:
            self.logger.error(f"Error in add_autokick: {str(e)}")
            await self._reset_cache()
            raise

    async def remove_autokick(self, ctx, target: discord.Member):
        """Remove a member from autokick list."""
        try:
            await self._initialize_cache()

            # Check cache first
            if (
                target.id not in self._autokick_cache
                or ctx.author.id not in self._autokick_cache[target.id]
            ):
                await self.message_sender.send_autokick_not_found(ctx, target)
                return

            # Update cache
            self._autokick_cache[target.id].remove(ctx.author.id)
            if not self._autokick_cache[target.id]:
                del self._autokick_cache[target.id]

            # Update database
            async with self.bot.get_db() as session:
                await AutoKickQueries.remove_autokick(session, ctx.author.id, target.id)
                self.logger.info(f"Removed autokick: owner={ctx.author.id}, target={target.id}")
                await self.message_sender.send_autokick_removed(ctx, target)
        except Exception as e:
            self.logger.error(f"Error in remove_autokick: {str(e)}")
            await self._reset_cache()
            raise

    async def list_autokicks(self, ctx):
        """Show autokick list."""
        await self._initialize_cache()

        # Get all targets that this user has autokick on
        user_autokicks = [
            target_id
            for target_id, owners in self._autokick_cache.items()
            if ctx.author.id in owners
        ]

        if not user_autokicks:
            await self.message_sender.send_autokick_list_empty(ctx)
            return

        max_autokicks = await self.get_autokick_limit(ctx.author)
        await self.message_sender.send_autokick_list(ctx, user_autokicks, max_autokicks)

    async def check_autokick(
        self, member: discord.Member, channel: discord.VoiceChannel
    ) -> tuple[bool, set[int]]:
        """
        Check if a member should be autokicked from a channel.
        Returns a tuple of (should_kick: bool, matching_owners: set[int])
        """
        try:
            await self._initialize_cache()

            # self.logger.info(f"Checking autokick for member {member.id} in channel {channel.id}")
            # self.logger.info(
            #     f"Current cache state for member {member.id}: {self._autokick_cache.get(member.id, set())}"
            # )

            if member.id not in self._autokick_cache:
                # self.logger.info(f"Member {member.id} not in autokick cache")
                return False, set()

            # Check if any channel members have autokick on this member
            channel_member_ids = {m.id for m in channel.members}
            # self.logger.info(f"Channel {channel.id} members: {channel_member_ids}")

            owner_ids = self._autokick_cache[member.id]
            # self.logger.info(f"Owners who have autokick on member {member.id}: {owner_ids}")

            # Check intersection between channel members and owners who have autokick
            matching_owners = owner_ids.intersection(channel_member_ids)
            if matching_owners:
                # self.logger.info(f"Found matching owners in channel: {matching_owners}")
                return True, matching_owners

            # self.logger.info(f"No matching owners found for member {member.id}")
            return False, set()
        except Exception as e:
            self.logger.error(f"Error in check_autokick: {str(e)}")
            # Try to recover by resetting cache
            await self._reset_cache()
            return False, set()
