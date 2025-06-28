"""Premium maintenance service for handling expiration and cleanup."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import discord

from core.repositories.premium_repository import PremiumRepository
from core.services.base_service import BaseService

logger = logging.getLogger(__name__)


class PremiumMaintenanceService(BaseService):
    """Service for premium maintenance operations."""

    def __init__(
        self,
        premium_repository: PremiumRepository,
        bot: Any,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.premium_repository = premium_repository
        self.bot = bot
        self.guild: Optional[discord.Guild] = None
        self.config = bot.config

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate maintenance operations."""
        return True

    def set_guild(self, guild: discord.Guild) -> None:
        """Set the guild for the service."""
        self.guild = guild
        logger.info(f"Guild set for PremiumMaintenanceService: {guild.name}")

    async def process_premium_maintenance(self) -> dict[str, int]:
        """Process all premium maintenance tasks."""
        try:
            results = {
                "expired_roles": 0,
                "expired_bypasses": 0,
                "errors": 0,
            }

            # Process expired premium roles
            expired_roles = await self._process_expired_roles()
            results["expired_roles"] = len(expired_roles)

            # Process expired bypasses
            expired_bypasses = await self._process_expired_bypasses()
            results["expired_bypasses"] = expired_bypasses

            self._log_operation("process_premium_maintenance", **results)

            return results

        except Exception as e:
            self._log_error("process_premium_maintenance", e)
            return {"expired_roles": 0, "expired_bypasses": 0, "errors": 1}

    async def _process_expired_roles(self) -> list[dict[str, Any]]:
        """Process and remove expired premium roles."""
        expired_roles = []

        try:
            # Get all expired premium roles
            expired = await self.premium_repository.get_expired_premium_roles()

            for premium_role in expired:
                member = self.guild.get_member(premium_role.member_id)
                if not member:
                    # Remove from database if member not in guild
                    await self.premium_repository.remove_premium_role(premium_role.member_id, premium_role.role_name)
                    continue

                # Get role object
                role = discord.utils.get(member.roles, name=premium_role.role_name)
                if role:
                    try:
                        await member.remove_roles(role, reason="Premium expired")
                        logger.info(f"Removed expired premium role {premium_role.role_name} " f"from {member}")

                        # Notify member
                        await self._notify_premium_expired(member, premium_role.role_name)

                        expired_roles.append(
                            {
                                "member_id": premium_role.member_id,
                                "member_name": str(member),
                                "role_name": premium_role.role_name,
                                "expired_at": premium_role.expires_at,
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error removing role {premium_role.role_name} " f"from {member}: {e}")

                # Remove from database
                await self.premium_repository.remove_premium_role(premium_role.member_id, premium_role.role_name)

        except Exception as e:
            logger.error(f"Error processing expired roles: {e}")

        return expired_roles

    async def _process_expired_bypasses(self) -> int:
        """Process expired voice bypasses."""
        count = 0

        try:
            from datasources.queries import MemberQueries

            async with self.bot.get_db() as session:
                # Get all members with bypass
                members = await MemberQueries.get_all_members(session)
                current_time = datetime.now(timezone.utc)

                for db_member in members:
                    if db_member.bypass_expiry and db_member.bypass_expiry <= current_time:
                        # Clear expired bypass
                        db_member.bypass_expiry = None
                        count += 1

                        # Notify member if they're in the guild
                        member = self.guild.get_member(db_member.id)
                        if member:
                            await self._notify_bypass_expired(member)

                await session.commit()

        except Exception as e:
            logger.error(f"Error processing expired bypasses: {e}")

        return count

    async def _notify_premium_expired(self, member: discord.Member, role_name: str) -> None:
        """Notify member that their premium has expired."""
        try:
            embed = discord.Embed(
                title="⏰ Premium wygasło",
                description=(
                    f"Twoja ranga premium **{role_name}** właśnie wygasła.\n\n"
                    f"Aby przedłużyć premium, użyj komendy `/sklep` "
                    f"lub odwiedź {self.bot.config['donate_url']}"
                ),
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text=f"Serwer: {self.guild.name}")

            await member.send(embed=embed)

        except discord.Forbidden:
            logger.info(f"Cannot send expiration notification to {member}")
        except Exception as e:
            logger.error(f"Error sending expiration notification: {e}")

    async def _notify_bypass_expired(self, member: discord.Member) -> None:
        """Notify member that their bypass time has expired."""
        try:
            embed = discord.Embed(
                title="⏰ Czas obejścia (T) wygasł",
                description=(
                    "Twój czas obejścia limitów kanałów głosowych właśnie wygasł.\n\n"
                    "Możesz otrzymać więcej czasu poprzez:\n"
                    "• Dawanie bumpów serwerowi\n"
                    "• Posiadanie rangi boostera\n"
                    "• Zakup rangi premium"
                ),
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.set_footer(text=f"Serwer: {self.guild.name}")

            await member.send(embed=embed)

        except discord.Forbidden:
            logger.info(f"Cannot send bypass expiration notification to {member}")
        except Exception as e:
            logger.error(f"Error sending bypass expiration notification: {e}")

    async def cleanup_invalid_premium_entries(self) -> int:
        """Clean up invalid premium entries (members no longer in guild)."""
        cleaned = 0

        try:
            all_premium = await self.premium_repository.get_all_premium_roles()

            for premium_role in all_premium:
                member = self.guild.get_member(premium_role.member_id)
                if not member:
                    # Member not in guild, remove entry
                    await self.premium_repository.remove_premium_role(premium_role.member_id, premium_role.role_name)
                    cleaned += 1
                    logger.info(f"Cleaned up premium entry for absent member " f"{premium_role.member_id}")

            self._log_operation("cleanup_invalid_premium_entries", cleaned=cleaned)
            return cleaned

        except Exception as e:
            self._log_error("cleanup_invalid_premium_entries", e)
            return 0

    async def generate_premium_report(self) -> dict[str, Any]:
        """Generate a report of current premium status."""
        try:
            report = {
                "total_premium_members": 0,
                "by_role": {},
                "expiring_soon": [],
                "total_bypass_active": 0,
            }

            # Get all premium roles
            all_premium = await self.premium_repository.get_all_premium_roles()
            valid_premium = []

            for premium_role in all_premium:
                member = self.guild.get_member(premium_role.member_id)
                if member:
                    valid_premium.append(premium_role)

                    # Count by role
                    if premium_role.role_name not in report["by_role"]:
                        report["by_role"][premium_role.role_name] = 0
                    report["by_role"][premium_role.role_name] += 1

                    # Check if expiring soon (within 3 days)
                    days_until_expiry = (premium_role.expires_at - datetime.now(timezone.utc)).days

                    if 0 < days_until_expiry <= 3:
                        report["expiring_soon"].append(
                            {
                                "member_id": premium_role.member_id,
                                "member_name": str(member),
                                "role_name": premium_role.role_name,
                                "expires_in_days": days_until_expiry,
                            }
                        )

            report["total_premium_members"] = len(valid_premium)

            # Count active bypasses
            from datasources.queries import MemberQueries

            async with self.bot.get_db() as session:
                members = await MemberQueries.get_all_members(session)
                current_time = datetime.now(timezone.utc)

                for db_member in members:
                    if db_member.bypass_expiry and db_member.bypass_expiry > current_time:
                        report["total_bypass_active"] += 1

            self._log_operation("generate_premium_report")
            return report

        except Exception as e:
            self._log_error("generate_premium_report", e)
            return {}
