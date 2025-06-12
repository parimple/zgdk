"""
Premium role and bypass checking functionality.
"""

import logging
from datetime import datetime, timezone
from enum import IntEnum
from functools import wraps
from typing import List, Optional, Tuple

import discord
from discord.ext import commands

from datasources.models import Member
from datasources.queries import InviteQueries, MemberQueries
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class CommandTier(IntEnum):
    """Enum representing command access tiers."""

    TIER_0 = 0  # Available to everyone without any requirements
    TIER_T = 1  # Requires only T>0
    TIER_1 = 2  # Requires (booster/invite role + T>0) or any premium
    TIER_2 = 3  # Requires any premium role (zG50+)
    TIER_3 = 4  # Requires high premium role (zG500+)


class PremiumChecker:
    """Class for checking premium role requirements and bypass status."""

    # Command tiers
    COMMAND_TIERS = {
        # TIER_0 - Available to everyone without any requirements
        CommandTier.TIER_0: ["voicechat"],
        # TIER_T - Requires only T>0
        CommandTier.TIER_T: ["limit"],
        # TIER_1 - Requires (booster/invite role + T>0) or any premium
        CommandTier.TIER_1: ["speak", "connect", "text", "reset"],
        # TIER_2 - Requires any premium role (zG50+)
        CommandTier.TIER_2: ["view", "mod", "live", "color"],
        # TIER_3 - Requires high premium role (zG500+)
        CommandTier.TIER_3: ["autokick"],
    }

    # Role IDs
    BOOSTER_ROLE_ID = 1052692705718829117  # ♼
    INVITE_ROLE_ID = 960665311760248879  # ♵

    # Premium role levels
    PREMIUM_ROLE_LEVELS = {"zG50": 1, "zG100": 2, "zG500": 3, "zG1000": 4}

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config.get("voice_permission_levels", {})
        self.message_sender = MessageSender()

    def get_command_tier(self, command_name: str) -> Optional[CommandTier]:
        """Get the tier level for a given command."""
        for tier, commands in self.COMMAND_TIERS.items():
            if command_name in commands:
                return tier
        return None

    async def has_active_bypass(self, ctx: commands.Context) -> bool:
        """Check if user has active T (bypass)."""
        try:
            async with self.bot.get_db() as session:
                bypass_until = await MemberQueries.get_voice_bypass_status(session, ctx.author.id)
                return bypass_until is not None and bypass_until > datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Error in has_active_bypass for user {ctx.author.id}: {e}")
            return False

    def has_booster_roles(self, ctx: commands.Context) -> bool:
        """Check if user has booster or invite role."""
        return any(
            role.id in [self.BOOSTER_ROLE_ID, self.INVITE_ROLE_ID] for role in ctx.author.roles
        )

    def has_discord_invite_in_status(self, ctx: commands.Context) -> bool:
        """Check if user has 'discord.gg/zagadka' in their status."""
        target_text = "discord.gg/zagadka"

        # Check activities (games, spotify, etc.)
        if ctx.author.activities:
            for activity in ctx.author.activities:
                # Check activity name
                if (
                    hasattr(activity, "name")
                    and activity.name
                    and target_text in activity.name.lower()
                ):
                    return True
                # Check activity details
                if (
                    hasattr(activity, "details")
                    and activity.details
                    and target_text in activity.details.lower()
                ):
                    return True
                # Check activity state
                if (
                    hasattr(activity, "state")
                    and activity.state
                    and target_text in activity.state.lower()
                ):
                    return True
                # Check custom status (discord.CustomActivity)
                if isinstance(activity, discord.CustomActivity):
                    if activity.name and target_text in activity.name.lower():
                        return True

        # Try through guild member as well
        try:
            guild_member = ctx.guild.get_member(ctx.author.id)
            if guild_member and guild_member.activities:
                for activity in guild_member.activities:
                    if (
                        hasattr(activity, "name")
                        and activity.name
                        and target_text in activity.name.lower()
                    ):
                        return True
                    if (
                        hasattr(activity, "details")
                        and activity.details
                        and target_text in activity.details.lower()
                    ):
                        return True
                    if (
                        hasattr(activity, "state")
                        and activity.state
                        and target_text in activity.state.lower()
                    ):
                        return True
                    if isinstance(activity, discord.CustomActivity):
                        if activity.name and target_text in activity.name.lower():
                            return True
        except Exception:
            pass

        return False

    async def has_alternative_bypass_access(self, ctx: commands.Context) -> bool:
        """
        Check if user qualifies for alternative bypass access.
        Requirements: booster role + 4+ invites + discord.gg/zagadka in status
        """
        try:
            logger.debug(f"Checking alternative bypass access for user {ctx.author.id}")

            if not self.has_booster_roles(ctx):
                logger.debug(f"User {ctx.author.id} does not have booster roles")
                return False

            if not self.has_discord_invite_in_status(ctx):
                logger.debug(f"User {ctx.author.id} does not have discord invite in status")
                return False

            # Check invite count (with validation like legacy system)
            async with self.bot.get_db() as session:
                invite_count = await InviteQueries.get_member_valid_invite_count(
                    session, ctx.author.id, ctx.guild, min_days=7
                )
                logger.debug(f"User {ctx.author.id} has {invite_count} valid invites")
                return invite_count >= 4
        except Exception as e:
            logger.error(f"Error in has_alternative_bypass_access for user {ctx.author.id}: {e}")
            return False

    async def debug_alternative_access(self, ctx: commands.Context) -> str:
        """Debug function to check alternative access requirements."""
        has_booster = self.has_booster_roles(ctx)
        has_status = self.has_discord_invite_in_status(ctx)

        async with self.bot.get_db() as session:
            invite_count = await InviteQueries.get_member_valid_invite_count(
                session, ctx.author.id, ctx.guild, min_days=7
            )

        # Debug activities
        activities_debug = []
        if ctx.author.activities:
            for i, activity in enumerate(ctx.author.activities):
                activity_info = f"Activity {i}: type={type(activity).__name__}"
                if hasattr(activity, "name") and activity.name:
                    activity_info += f", name='{activity.name}'"
                if hasattr(activity, "details") and activity.details:
                    activity_info += f", details='{activity.details}'"
                if hasattr(activity, "state") and activity.state:
                    activity_info += f", state='{activity.state}'"
                # Special handling for CustomActivity
                if isinstance(activity, discord.CustomActivity):
                    activity_info += f" [CUSTOM STATUS]"
                activities_debug.append(activity_info)
        else:
            activities_debug.append("No activities found")

        # Additional debug info
        debug_extra = [
            f"User ID: {ctx.author.id}",
            f"User roles: {[role.name for role in ctx.author.roles]}",
            f"Activities count: {len(ctx.author.activities) if ctx.author.activities else 0}",
            f"Status: {ctx.author.status}",
            f"Is on mobile: {ctx.author.is_on_mobile()}",
            f"Desktop status: {ctx.author.desktop_status}",
            f"Mobile status: {ctx.author.mobile_status}",
            f"Web status: {ctx.author.web_status}",
        ]

        # Try to access member through guild to get more presence info
        try:
            guild_member = ctx.guild.get_member(ctx.author.id)
            if guild_member:
                debug_extra.append(
                    f"Guild member activities: {len(guild_member.activities) if guild_member.activities else 0}"
                )
                if guild_member.activities:
                    for i, activity in enumerate(guild_member.activities):
                        debug_extra.append(f"Guild Activity {i}: {type(activity).__name__}")
                        if hasattr(activity, "name"):
                            debug_extra.append(f"  - name: {activity.name}")
        except Exception as e:
            debug_extra.append(f"Guild member fetch error: {e}")

        activities_text = "\n".join(activities_debug)
        extra_text = "\n".join(debug_extra)

        return (
            f"Debug alternative access for {ctx.author.mention}:\n"
            f"- Has booster role: {has_booster}\n"
            f"- Has discord.gg/zagadka in status: {has_status}\n"
            f"- Invite count: {invite_count}/4\n"
            f"- Qualifies: {has_booster and has_status and invite_count >= 4}\n\n"
            f"Activities debug:\n{activities_text}\n\n"
            f"Extra debug:\n{extra_text}"
        )

    def has_premium_role(self, ctx: commands.Context, min_tier: str = "zG50") -> bool:
        """
        Check if user has required premium role or higher.
        Args:
            ctx: Command context
            min_tier: Minimum required tier (e.g. "zG50", "zG500")
        Returns:
            bool: True if user has the required tier or higher
        """
        min_level = self.PREMIUM_ROLE_LEVELS.get(min_tier, 0)
        user_roles = [role.name for role in ctx.author.roles]

        # Check if user has any premium role at or above the required level
        for role_name, level in self.PREMIUM_ROLE_LEVELS.items():
            if level >= min_level and role_name in user_roles:
                return True

        return False

    @staticmethod
    def requires_premium_tier(command_name: str):
        """
        Decorator to check premium access requirements WITHOUT requiring voice channel.
        This is suitable for commands that need premium status but don't need a voice channel.
        """

        async def predicate(ctx):
            # Skip checks for help/pomoc command
            if ctx.command.name in ["help", "pomoc"] or ctx.invoked_with in ["help", "pomoc"]:
                return True

            # Skip checks for help context
            if getattr(ctx, "help_command", None):
                return True

            checker = PremiumChecker(ctx.bot)
            command_tier = checker.get_command_tier(command_name)
            if command_tier is None:
                logger.warning(f"Command {command_name} has no defined tier")
                await checker.message_sender.send_no_permission(ctx)
                return False

            has_booster = checker.has_booster_roles(ctx)
            has_bypass = await checker.has_active_bypass(ctx)
            has_alternative_access = await checker.has_alternative_bypass_access(ctx)
            has_premium = checker.has_premium_role(ctx)
            has_high_premium = checker.has_premium_role(ctx, "zG500")

            # TIER_0 - Available to everyone without any requirements
            if command_tier == CommandTier.TIER_0:
                return True

            # TIER_T - Requires only T>0 OR alternative access (booster + 4 invites + status)
            if command_tier == CommandTier.TIER_T:
                if not has_bypass and not has_premium and not has_alternative_access:
                    await checker.message_sender.send_tier_t_bypass_required(ctx)
                    return False
                return True

            # TIER_1 - Requires (booster/invite role + T>0) or any premium OR alternative access
            if command_tier == CommandTier.TIER_1:
                if has_premium:
                    return True
                if has_booster and (has_bypass or has_alternative_access):
                    return True
                if has_booster:
                    await checker.message_sender.send_bypass_expired(ctx)
                else:
                    await checker.message_sender.send_premium_required(ctx)
                return False

            # TIER_2 - Requires any premium role
            if command_tier == CommandTier.TIER_2:
                if not has_premium:
                    await checker.message_sender.send_specific_roles_required(
                        ctx, ["zG50", "zG100", "zG500", "zG1000"]
                    )
                    return False
                return True

            # TIER_3 - Requires high premium role
            if command_tier == CommandTier.TIER_3:
                if not has_high_premium:
                    await checker.message_sender.send_specific_roles_required(
                        ctx, ["zG500", "zG1000"]
                    )
                    return False
                return True

            # Default case - deny access
            await checker.message_sender.send_no_permission(ctx)
            return False

        return commands.check(predicate)

    @staticmethod
    def requires_voice_access(command_name: str):
        """
        Decorator to check voice command access requirements.
        """

        async def predicate(ctx):
            # Skip checks for help/pomoc command
            if ctx.command.name in ["help", "pomoc"] or ctx.invoked_with in ["help", "pomoc"]:
                return True

            # Skip checks for help context
            if getattr(ctx, "help_command", None):
                return True

            checker = PremiumChecker(ctx.bot)
            command_tier = checker.get_command_tier(command_name)
            if command_tier is None:
                logger.warning(f"Command {command_name} has no defined tier")
                await checker.message_sender.send_no_permission(ctx)
                return False

            has_booster = checker.has_booster_roles(ctx)
            has_bypass = await checker.has_active_bypass(ctx)
            has_alternative_access = await checker.has_alternative_bypass_access(ctx)
            has_premium = checker.has_premium_role(ctx)
            has_high_premium = checker.has_premium_role(ctx, "zG500")

            # Check if user is in voice channel first (for all tiers above TIER_T)
            if not ctx.author.voice or not ctx.author.voice.channel:
                await checker.message_sender.send_not_in_voice_channel(ctx)
                return False

            # Check if user is channel mod
            is_channel_mod = False
            voice_channel = ctx.author.voice.channel
            if voice_channel:
                perms = voice_channel.overwrites_for(ctx.author)
                is_channel_mod = (
                    perms and perms.manage_messages is True and perms.priority_speaker is not True
                )

            # TIER_0 - Available to everyone without any requirements
            if command_tier == CommandTier.TIER_0:
                return True

            # TIER_T - Requires only T>0 OR alternative access (booster + 4 invites + status)
            if command_tier == CommandTier.TIER_T:
                if not has_bypass and not has_premium and not has_alternative_access:
                    await checker.message_sender.send_tier_t_bypass_required(ctx)
                    return False
                return True

            # TIER_1 - Requires (booster/invite role + T>0) or any premium OR alternative access
            if command_tier == CommandTier.TIER_1:
                if has_premium:
                    return True
                if (has_booster or is_channel_mod) and (has_bypass or has_alternative_access):
                    return True
                if has_booster or is_channel_mod:
                    await checker.message_sender.send_bypass_expired(ctx)
                else:
                    await checker.message_sender.send_premium_required(ctx)
                return False

            # TIER_2 - Requires any premium role
            if command_tier == CommandTier.TIER_2:
                # Special case for view and live - allow channel mods with active bypass or alternative access
                if (
                    command_name in ["view", "live"]
                    and is_channel_mod
                    and (has_bypass or has_alternative_access)
                ):
                    return True

                # For all TIER_2 commands, require premium unless exception above
                if not has_premium:
                    await checker.message_sender.send_specific_roles_required(
                        ctx, ["zG50", "zG100", "zG500", "zG1000"]
                    )
                    return False
                return True

            # TIER_3 - Requires high premium role
            if command_tier == CommandTier.TIER_3:
                if not has_high_premium:
                    await checker.message_sender.send_specific_roles_required(
                        ctx, ["zG500", "zG1000"]
                    )
                    return False
                return True

            # Default case - deny access
            await checker.message_sender.send_no_permission(ctx)
            return False

        return commands.check(predicate)

    @staticmethod
    def requires_premium(command_name: str):
        """
        Legacy decorator - replaced by requires_voice_access
        Kept for backward compatibility
        """
        return PremiumChecker.requires_voice_access(command_name)

    @staticmethod
    async def extend_bypass(bot, member_id: int, hours: int = 12) -> Optional[datetime]:
        """
        Extend voice bypass duration for a member.
        Returns new expiration datetime or None if failed.
        """
        from datetime import timedelta

        async with bot.get_db() as session:
            return await MemberQueries.extend_voice_bypass(
                session, member_id, timedelta(hours=hours)
            )

    @staticmethod
    def requires_specific_roles(required_roles: list[str]):
        """
        Decorator to check if a user has any of the specified roles.
        Args:
            required_roles: List of role names that grant access to the command
        """

        async def predicate(ctx):
            # Skip checks for help/pomoc command
            if ctx.command.name in ["help", "pomoc"] or ctx.invoked_with in ["help", "pomoc"]:
                return True

            # Skip checks for help context
            if getattr(ctx, "help_command", None):
                return True

            checker = PremiumChecker(ctx.bot)

            # Sprawdź czy użytkownik ma którąkolwiek z wymaganych ról
            has_required_role = any(role.name in required_roles for role in ctx.author.roles)

            if not has_required_role:
                await checker.message_sender.send_specific_roles_required(ctx, required_roles)
                return False

            return True

        return commands.check(predicate)
