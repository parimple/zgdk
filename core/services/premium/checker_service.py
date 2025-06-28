"""Premium checker service for permission and bypass validation."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import discord

from core.interfaces.premium_interfaces import CommandTier, IPremiumChecker
from core.services.base_service import BaseService
from core.services.cache_service import CacheService
from datasources.queries import MemberQueries

logger = logging.getLogger(__name__)


class PremiumCheckerService(BaseService, IPremiumChecker):
    """Service for checking premium permissions and bypass access."""

    # Command tier requirements
    COMMAND_TIERS = {
        CommandTier.TIER_0: ["voicechat"],
        CommandTier.TIER_T: ["limit"],
        CommandTier.TIER_1: ["speak", "connect", "text", "reset"],
        CommandTier.TIER_2: ["view", "mod", "live", "color"],
        CommandTier.TIER_3: ["autokick"],
    }

    # Role IDs for bypass checking
    BOOSTER_ROLE_ID = 1052692705718829117  # ♼
    INVITE_ROLE_ID = 960665311760248879  # ♵

    # Premium role priorities
    PREMIUM_PRIORITY = {"zG50": 1, "zG100": 2, "zG500": 3, "zG1000": 4}

    def __init__(self, bot: Any, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.guild: Optional[discord.Guild] = None
        self.cache_service = CacheService(max_size=1000, default_ttl=300)  # 5 min cache
        self.config = bot.config
        self.premium_roles_config = bot.config.get("premium_roles", [])

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate checker operations."""
        return True

    def set_guild(self, guild: discord.Guild) -> None:
        """Set the guild for the service."""
        self.guild = guild
        logger.info(f"Guild set for PremiumCheckerService: {guild.name}")

    def get_user_highest_role_priority(self, member: discord.Member) -> int:
        """Get the highest priority premium role of a member."""
        highest_priority = 0
        for role in member.roles:
            role_name = role.name
            if role_name in self.PREMIUM_PRIORITY:
                priority = self.PREMIUM_PRIORITY[role_name]
                if priority > highest_priority:
                    highest_priority = priority
        return highest_priority

    def get_user_highest_role_name(self, member: discord.Member) -> Optional[str]:
        """Get the name of the highest priority premium role of a member."""
        highest_priority = 0
        highest_role_name = None

        for role in member.roles:
            role_name = role.name
            if role_name in self.PREMIUM_PRIORITY:
                priority = self.PREMIUM_PRIORITY[role_name]
                if priority > highest_priority:
                    highest_priority = priority
                    highest_role_name = role_name

        return highest_role_name

    async def has_premium_role(self, member: discord.Member) -> bool:
        """Check if member has any premium role."""
        # Check cache first
        cache_key = f"has_premium:{member.id}"
        cached_result = await self.cache_service.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Check member roles
        result = any(role.name in self.PREMIUM_PRIORITY for role in member.roles)

        # Cache the result
        await self.cache_service.set(cache_key, result)
        return result

    async def get_member_premium_level(self, member: discord.Member) -> Optional[str]:
        """Get member's premium level."""
        return self.get_user_highest_role_name(member)

    async def has_active_bypass(self, member: discord.Member) -> bool:
        """Check if member has active bypass time."""
        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(
                session, member.id, wallet_balance=0, joined_at=member.joined_at
            )

            if db_member.voice_bypass_until:
                return db_member.voice_bypass_until > datetime.now(timezone.utc)

        return False

    def has_booster_roles(self, member: discord.Member) -> bool:
        """Check if member has Discord booster role."""
        return any(role.id == self.BOOSTER_ROLE_ID for role in member.roles)

    def has_discord_invite_in_status(self, member: discord.Member) -> bool:
        """Check if member has Discord invite link in status."""
        if not member.activities:
            return False

        custom_status = None
        for activity in member.activities:
            if isinstance(activity, discord.CustomActivity):
                custom_status = activity
                break

        if not custom_status or not custom_status.name:
            return False

        # Check for discord invite patterns
        invite_patterns = [
            r"discord\.gg/[a-zA-Z0-9]+",
            r"discord\.com/invite/[a-zA-Z0-9]+",
            r"discordapp\.com/invite/[a-zA-Z0-9]+",
        ]

        import re

        status_text = custom_status.name.lower()
        for pattern in invite_patterns:
            if re.search(pattern, status_text, re.IGNORECASE):
                # Check if it's not our server invite
                our_invites = ["discord.gg/zagadka", "discord.gg/dVbm39mSZH"]
                if not any(invite.lower() in status_text for invite in our_invites):
                    return False

                # Check for ♵ role
                return any(role.id == self.INVITE_ROLE_ID for role in member.roles)

        return False

    async def has_alternative_bypass_access(self, member: discord.Member) -> bool:
        """Check if member has any alternative bypass access (T, booster, invite)."""
        # Check cache first
        cache_key = f"alt_bypass:{member.id}"
        cached_result = await self.cache_service.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Check various bypass methods
        has_bypass = False

        # Check active bypass time (T)
        if await self.has_active_bypass(member):
            has_bypass = True

        # Check booster role
        elif self.has_booster_roles(member):
            has_bypass = True

        # Check invite in status
        elif self.has_discord_invite_in_status(member):
            has_bypass = True

        # Cache the result
        await self.cache_service.set(cache_key, has_bypass, ttl=60)  # Short TTL for bypass
        return has_bypass

    async def get_command_tier(self, command_name: str) -> CommandTier:
        """Get the tier requirement for a command."""
        for tier, commands in self.COMMAND_TIERS.items():
            if command_name.lower() in commands:
                return tier
        return CommandTier.TIER_0

    async def has_bypass_permissions(self, member: discord.Member, command_name: Optional[str] = None) -> bool:
        """Check if member has bypass permissions for a specific command or generally."""
        # Check premium role first
        if await self.has_premium_role(member):
            if not command_name:
                return True

            # Check command tier requirements
            tier = await self.get_command_tier(command_name)
            member_level = self.get_user_highest_role_priority(member)

            # Map priority to tier access
            tier_access = {
                0: [CommandTier.TIER_0],
                1: [CommandTier.TIER_0, CommandTier.TIER_1],
                2: [CommandTier.TIER_0, CommandTier.TIER_1, CommandTier.TIER_2],
                3: [CommandTier.TIER_0, CommandTier.TIER_1, CommandTier.TIER_2, CommandTier.TIER_3],
                4: [CommandTier.TIER_0, CommandTier.TIER_1, CommandTier.TIER_2, CommandTier.TIER_3],
            }

            return tier in tier_access.get(member_level, [])

        # Check alternative bypass for Tier T commands
        if command_name and await self.get_command_tier(command_name) == CommandTier.TIER_T:
            return await self.has_alternative_bypass_access(member)

        return False

    async def get_member_premium_status(self, member: discord.Member) -> dict[str, Any]:
        """Get comprehensive premium status for member."""
        try:
            premium_role = self.get_user_highest_role_name(member)
            has_premium = premium_role is not None
            has_bypass = await self.has_active_bypass(member)
            has_booster = self.has_booster_roles(member)
            has_invite = self.has_discord_invite_in_status(member)

            status = {
                "has_premium": has_premium,
                "premium_role": premium_role,
                "premium_level": self.PREMIUM_PRIORITY.get(premium_role, 0) if premium_role else 0,
                "has_bypass": has_bypass,
                "has_booster": has_booster,
                "has_invite": has_invite,
                "has_any_access": has_premium or has_bypass or has_booster or has_invite,
            }

            self._log_operation("get_member_premium_status", member_id=member.id)
            return status

        except Exception as e:
            self._log_error("get_member_premium_status", e, member_id=member.id)
            return {
                "has_premium": False,
                "premium_role": None,
                "premium_level": 0,
                "has_bypass": False,
                "has_booster": False,
                "has_invite": False,
                "has_any_access": False,
            }
