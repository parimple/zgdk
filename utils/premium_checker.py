"""
Premium role and bypass checking functionality.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from discord.ext import commands

from datasources.queries import MemberQueries
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class PremiumChecker:
    """Class for checking premium role requirements and bypass status."""

    VOICE_COMMANDS = ["speak", "connect", "text", "view", "live"]
    MOD_COMMANDS = ["mod"]
    AUTOKICK_COMMANDS = ["autokick"]

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config.get("voice_permission_levels", {})
        self.message_sender = MessageSender()

    async def check_premium_requirement(self, ctx: commands.Context, command_name: str) -> bool:
        """
        Check if user has required premium roles or active bypass for a command.
        Returns True if user can use the command, False otherwise.

        Logic:
        1. If user has zG role -> allow
        2. If user has booster role AND T > 0 -> allow
        3. Otherwise -> deny with appropriate message
        """
        # Get command config
        cmd_config = self.bot.config["voice_permissions"]["commands"].get(command_name, {})
        if not cmd_config:
            logger.warning(f"No config found for command {command_name}")
            return True  # Allow if no config

        member_roles = [role.name for role in ctx.author.roles]

        # First check for zG roles - they give direct access
        premium_roles = [role["name"] for role in self.bot.config["premium_roles"]]
        if any(role in premium_roles for role in member_roles):
            return True

        # For commands that don't allow bypass (like mod, autokick)
        if not cmd_config.get("require_bypass_if_no_role", True):
            allowed_roles = cmd_config.get("allowed_roles", [])
            if not any(role in allowed_roles for role in member_roles):
                await self.message_sender.send_specific_roles_required(ctx, allowed_roles)
                return False
            return True

        # Check if user has booster role and needs bypass
        booster_roles = self.bot.config["voice_permissions"]["boosters"]
        has_booster = any(role in booster_roles for role in member_roles)

        if has_booster:
            # Check if T > 0 (voice_bypass_until is in the future)
            async with self.bot.get_db() as session:
                bypass_until = await MemberQueries.get_voice_bypass_status(session, ctx.author.id)
                if bypass_until and bypass_until > datetime.now(timezone.utc):
                    return True
                else:
                    # T expired - send message about using /bump
                    await self.message_sender.send_bypass_expired(ctx)
                    return False

        # No zG role and no booster role with T > 0
        await self.message_sender.send_premium_required(ctx)
        return False

    @staticmethod
    def requires_premium(command_name: str):
        """
        Decorator to check premium requirements for a command.
        """

        async def predicate(ctx):
            # Skip checks for help command and help context
            if ctx.command.name == "help" or ctx.invoked_with == "help":
                return True

            checker = PremiumChecker(ctx.bot)
            return await checker.check_premium_requirement(ctx, command_name)

        return commands.check(predicate)

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
