"""
Premium role and bypass checking functionality.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from discord.ext import commands

from datasources.models import Member
from datasources.queries import MemberQueries
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class PremiumChecker:
    """Class for checking premium role requirements and bypass status."""

    # Command categories
    BASIC_VOICE_COMMANDS = ["speak", "connect", "view"]
    MOD_COMMANDS = ["text", "mod", "live"]
    AUTOKICK_COMMANDS = ["autokick"]
    LIMIT_COMMAND = ["limit"]

    # Role IDs
    BOOSTER_ROLE_ID = 1052692705718829117  # ♼
    INVITE_ROLE_ID = 960665311760248879  # ♵

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config.get("voice_permission_levels", {})
        self.message_sender = MessageSender()

    async def has_active_bypass(self, ctx: commands.Context) -> bool:
        """Check if user has active T (bypass)."""
        async with self.bot.get_db() as session:
            bypass_until = await MemberQueries.get_voice_bypass_status(session, ctx.author.id)
            return bypass_until is not None and bypass_until > datetime.now(timezone.utc)

    def has_booster_roles(self, ctx: commands.Context) -> bool:
        """Check if user has booster or invite role."""
        return any(
            role.id in [self.BOOSTER_ROLE_ID, self.INVITE_ROLE_ID] for role in ctx.author.roles
        )

    def has_premium_role(self, ctx: commands.Context, min_tier: str = "zG50") -> bool:
        """Check if user has required premium role or higher."""
        premium_roles = ["zG50", "zG100", "zG500", "zG1000"]
        min_index = premium_roles.index(min_tier)
        user_roles = [role.name for role in ctx.author.roles]
        return any(role in user_roles for role in premium_roles[min_index:])

    @staticmethod
    def requires_voice_access(command_name: str):
        """
        Decorator to check voice command access requirements.
        """

        async def predicate(ctx):
            checker = PremiumChecker(ctx.bot)

            # Skip checks for help command
            if ctx.command.name in ["help", "pomoc"] or ctx.invoked_with in ["help", "pomoc"]:
                return True

            has_bypass = await checker.has_active_bypass(ctx)
            has_premium = checker.has_premium_role(ctx)

            # Special case for limit command - available to everyone with T>0
            if command_name in checker.LIMIT_COMMAND:
                if not (has_premium or has_bypass):
                    # Get current T value for the message
                    current_t = "0T"
                    async with ctx.bot.get_db() as session:
                        db_member = await session.get(Member, ctx.author.id)
                        if db_member and db_member.voice_bypass_until:
                            now = datetime.now(timezone.utc)
                            if db_member.voice_bypass_until > now:
                                remaining = db_member.voice_bypass_until - now
                                current_t = f"{int(remaining.total_seconds() // 3600)}T"

                    if current_t == "0T":
                        await checker.message_sender.send_bypass_expired(ctx)
                    return False
                return True

            # Commands requiring zG500+
            if command_name in checker.AUTOKICK_COMMANDS:
                if not checker.has_premium_role(ctx, "zG500"):
                    await checker.message_sender.send_specific_roles_required(
                        ctx, ["zG500", "zG1000"]
                    )
                    return False
                return True

            # Commands requiring zG50+
            if command_name in checker.MOD_COMMANDS:
                if not checker.has_premium_role(ctx, "zG50"):
                    await checker.message_sender.send_specific_roles_required(
                        ctx, ["zG50", "zG100", "zG500", "zG1000"]
                    )
                    return False
                return True

            # Basic voice commands require booster/invite role or premium role
            if command_name in checker.BASIC_VOICE_COMMANDS:
                if not (checker.has_booster_roles(ctx) or checker.has_premium_role(ctx)):
                    await checker.message_sender.send_premium_required(ctx)
                    return False
                if not has_bypass and not checker.has_premium_role(ctx):
                    await checker.message_sender.send_bypass_expired(ctx)
                    return False
                return True

            return True

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
