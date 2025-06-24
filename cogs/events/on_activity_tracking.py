"""Activity tracking event handlers for the ranking system."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Set

import discord
from discord.ext import commands, tasks

from utils.managers import ActivityManager
from utils.permissions import is_zagadka_owner

logger = logging.getLogger(__name__)


class OnActivityTracking(commands.Cog):
    """Cog for tracking user activity and managing ranking system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.activity_manager = ActivityManager()

        # Track voice members for point calculation
        self.voice_members: Dict[int, Set[int]] = {}  # channel_id -> set of member_ids
        self.promotion_members: Set[int] = set()  # members with promotion in status

        # Start background tasks (use same pattern as other cogs)
        self.voice_point_tracker.start()
        self.promotion_checker.start()

    def _has_points_off_role(self, member: discord.Member) -> bool:
        """Check if member has the 'points_off' role based on config."""
        mute_roles = self.bot.config.get("mute_roles", [])
        points_off_role = None

        # Find the points_off role from config
        for role_config in mute_roles:
            if role_config.get("description") == "points_off":
                points_off_role = role_config.get("name")
                break

        if not points_off_role:
            # Fallback to hardcoded if not found in config
            points_off_role = "♺"

        return any(role.name == points_off_role for role in member.roles)

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.voice_point_tracker.cancel()
        self.promotion_checker.cancel()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """Track voice channel activity."""
        if member.bot:
            return

        # Handle member leaving voice
        if before.channel and before.channel.id in self.voice_members:
            self.voice_members[before.channel.id].discard(member.id)
            if not self.voice_members[before.channel.id]:
                del self.voice_members[before.channel.id]

        # Handle member joining voice
        if after.channel:
            if after.channel.id not in self.voice_members:
                self.voice_members[after.channel.id] = set()
            self.voice_members[after.channel.id].add(member.id)

        logger.debug(
            f"Voice update: {member.display_name} - {len(self.voice_members)} channels active"
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track text message activity."""
        if message.author.bot or not message.guild or message.guild != self.bot.guild:
            return

        # Skip if member has "points_off" role
        if self._has_points_off_role(message.author):
            return

        try:
            async with self.bot.get_db() as session:
                await self.activity_manager.add_text_activity(
                    session, message.author.id, message.content
                )
        except Exception as e:
            logger.error(f"Failed to track text activity for {message.author.id}: {e}")

    @tasks.loop(minutes=1)
    async def voice_point_tracker(self):
        """Award points every minute for voice activity."""
        if not self.voice_members or not self.bot.guild:
            return

        try:
            async with self.bot.get_db() as session:
                # Create a copy of the dictionary to avoid "dictionary changed size during iteration"
                voice_members_copy = dict(self.voice_members)

                for channel_id, member_ids in voice_members_copy.items():
                    channel = self.bot.guild.get_channel(channel_id)
                    if not channel:
                        continue

                    # Create a copy of member_ids set to avoid modification during iteration
                    member_ids_copy = set(member_ids)

                    # Filter out muted/deafened members
                    active_members = []
                    members_to_remove = set()

                    for member_id in member_ids_copy:
                        member = self.bot.guild.get_member(member_id)
                        if not member:
                            members_to_remove.add(member_id)
                            continue

                        # Skip if member has "points_off" role
                        if self._has_points_off_role(member):
                            continue

                        # Skip if muted or deafened
                        if member.voice and (member.voice.self_mute or member.voice.self_deaf):
                            continue

                        active_members.append(member_id)

                    # Remove non-existent members from the original set after iteration
                    if members_to_remove:
                        self.voice_members[channel_id].difference_update(members_to_remove)
                        # Remove empty channel entries
                        if not self.voice_members[channel_id]:
                            del self.voice_members[channel_id]

                    # Award points based on whether they're alone or with others
                    is_with_others = len(active_members) > 1

                    for member_id in active_members:
                        await self.activity_manager.add_voice_activity(
                            session, member_id, is_with_others
                        )

                    if active_members:
                        points_type = "with others" if is_with_others else "alone"
                        logger.debug(
                            f"Awarded voice points to {len(active_members)} members in {channel.name} ({points_type})"
                        )

        except Exception as e:
            logger.error(f"Error in voice point tracker: {e}")

    @tasks.loop(minutes=1)
    async def promotion_checker(self):
        """Check for members promoting the server and award points."""
        if not self.bot.guild:
            return

        # Only award promotion points every 5 minutes (optimal balance)
        current_time = datetime.now(timezone.utc)
        should_award_points = current_time.minute % 5 == 0

        try:
            async with self.bot.get_db() as session:
                current_promoters = set()

                for member in self.bot.guild.members:
                    if member.bot:
                        continue

                    # Skip if member has "points_off" role
                    if self._has_points_off_role(member):
                        continue

                    # Check for promotion
                    if await self.activity_manager.check_member_promotion_status(member):
                        current_promoters.add(member.id)
                        # Only award points every 3 minutes
                        if should_award_points:
                            await self.activity_manager.add_promotion_activity(session, member.id)

                    # Check for anti-promotion (promoting other servers)
                    if await self.activity_manager.check_member_antipromo_status(member):
                        # Log but don't reset points automatically (as per user request)
                        logger.debug(
                            f"Member {member.display_name} ({member.id}) is promoting other servers"
                        )

                # Log promotion activity
                new_promoters = current_promoters - self.promotion_members
                stopped_promoters = self.promotion_members - current_promoters

                if new_promoters:
                    logger.info(f"New promoters: {len(new_promoters)} members")
                if stopped_promoters:
                    logger.info(f"Stopped promoting: {len(stopped_promoters)} members")

                self.promotion_members = current_promoters

        except Exception as e:
            logger.error(f"Error in promotion checker: {e}")

    @voice_point_tracker.before_loop
    async def before_voice_tracker(self):
        """Wait for bot to be ready before starting voice tracker."""
        await self.bot.wait_until_ready()
        if self.bot.guild:
            self.activity_manager.set_guild(self.bot.guild)
            logger.info("Activity Manager: Guild set for voice tracker")
        else:
            logger.warning("Activity Manager: No guild set for voice tracker")

    @promotion_checker.before_loop
    async def before_promotion_checker(self):
        """Wait for bot to be ready before starting promotion checker."""
        await self.bot.wait_until_ready()
        if self.bot.guild:
            self.activity_manager.set_guild(self.bot.guild)
            logger.info("Activity Manager: Guild set for promotion checker")
        else:
            logger.warning("Activity Manager: No guild set for promotion checker")

    # Admin commands for testing/management
    @commands.hybrid_command(name="activity_debug")
    @is_zagadka_owner()
    async def activity_debug(self, ctx: commands.Context):
        """Debug command to show current activity tracking status."""
        voice_info = []
        for channel_id, member_ids in self.voice_members.items():
            channel = self.bot.guild.get_channel(channel_id)
            voice_info.append(
                f"{channel.name if channel else channel_id}: {len(member_ids)} members"
            )

        embed = discord.Embed(title="🔧 Activity Tracking Debug", color=discord.Color.orange())

        embed.add_field(
            name="🎤 Voice Channels",
            value="\n".join(voice_info) if voice_info else "No active voice channels",
            inline=False,
        )

        embed.add_field(
            name="📢 Promoters",
            value=f"{len(self.promotion_members)} members promoting",
            inline=True,
        )

        embed.add_field(
            name="🔄 Tasks Status",
            value=f"Voice: {'Running' if self.voice_point_tracker.is_running() else 'Stopped'}\n"
            f"Promotion: {'Running' if self.promotion_checker.is_running() else 'Stopped'}",
            inline=True,
        )

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="add_bonus_points")
    @is_zagadka_owner()
    async def add_bonus_points(self, ctx: commands.Context, member: discord.Member, points: int):
        """Add bonus points to a member."""
        try:
            async with self.bot.get_db() as session:
                await self.activity_manager.add_bonus_activity(session, member.id, points)

            embed = discord.Embed(
                title="✅ Bonus Points Added",
                description=f"Added **{points}** bonus points to {member.mention}",
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Failed to add bonus points: {e}")
            await ctx.send(f"❌ Failed to add bonus points: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    """Set up the cog."""
    await bot.add_cog(OnActivityTracking(bot))
