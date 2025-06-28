"""Premium role management service."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import discord

from core.interfaces.premium_interfaces import (
    ExtensionResult,
    ExtensionType,
    IPremiumRoleManager,
    PremiumRoleConfig,
)
from core.repositories.premium_repository import PremiumRepository
from core.services.base_service import BaseService

logger = logging.getLogger(__name__)


class PremiumRoleService(BaseService, IPremiumRoleManager):
    """Service for managing premium roles."""

    # Premium role configurations
    PREMIUM_ROLES = {
        "zG50": PremiumRoleConfig("zG50", 0, 50, 1, 30),
        "zG100": PremiumRoleConfig("zG100", 0, 100, 2, 30),
        "zG500": PremiumRoleConfig("zG500", 0, 500, 3, 30),
        "zG1000": PremiumRoleConfig("zG1000", 0, 1000, 4, 30),
    }

    # Premium role priorities
    PREMIUM_PRIORITY = {"zG50": 1, "zG100": 2, "zG500": 3, "zG1000": 4}

    # Duration constants
    MONTHLY_DURATION = 30
    YEARLY_DURATION = 365
    BONUS_DAYS = 3
    YEARLY_MONTHS = 10

    # Extension periods for different roles
    ZG50_EXTENSION = 30
    ZG100_EXTENSION = 15
    ZG500_EXTENSION = 3
    ZG1000_EXTENSION = 1

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
        self.mute_roles = {role["name"]: role for role in bot.config.get("mute_roles", [])}
        self.premium_roles_config = bot.config.get("premium_roles", [])

        # Initialize dynamic mappings
        self.partial_extensions = {}
        self.initialize_partial_extensions()

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate role operations."""
        return True

    def set_guild(self, guild: discord.Guild) -> None:
        """Set the guild for the service."""
        self.guild = guild
        logger.info(f"Guild set for PremiumRoleService: {guild.name}")

    def initialize_partial_extensions(self):
        """Initialize partial extension mappings based on config."""
        for role_config in self.premium_roles_config:
            role_name = role_config["name"]
            self.partial_extensions[role_name] = {}

            # Calculate extensions for each role
            for other_role_config in self.premium_roles_config:
                other_role_name = other_role_config["name"]
                if role_config["priority"] > other_role_config["priority"]:
                    # Higher priority role extending with lower priority payment
                    price_ratio = other_role_config["price"] / role_config["price"]
                    days = int(self.MONTHLY_DURATION * price_ratio)
                    self.partial_extensions[role_name][other_role_name] = days

    def get_role_price(self, role_name: str) -> int:
        """Get the price of a premium role."""
        for role_config in self.premium_roles_config:
            if role_config["name"] == role_name:
                return role_config["price"]
        return 0

    def has_mute_roles(self, member: discord.Member) -> bool:
        """Check if member has any mute roles."""
        mute_role_ids = [role["id"] for role in self.mute_roles.values()]
        return any(role.id in mute_role_ids for role in member.roles)

    async def remove_mute_roles(self, member: discord.Member):
        """Remove all mute roles from a member."""
        try:
            mute_role_ids = [role["id"] for role in self.mute_roles.values()]
            roles_to_remove = [role for role in member.roles if role.id in mute_role_ids]

            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Premium purchase removes mutes")
                logger.info(f"Removed {len(roles_to_remove)} mute roles from {member}")

        except Exception as e:
            logger.error(f"Error removing mute roles from {member}: {e}")

    async def get_member_premium_roles(self, member_id: int) -> list[dict]:
        """Get all premium roles for a member with expiration info."""
        try:
            async with self.bot.get_db() as session:
                premium_roles = await self.premium_repository.get_member_premium_roles(member_id)

                roles_info = []
                for role in premium_roles:
                    roles_info.append(
                        {
                            "role_name": role.role_name,
                            "expires_at": role.expires_at,
                            "duration_days": role.duration_days,
                            "source": role.source,
                        }
                    )

                return roles_info

        except Exception as e:
            logger.error(f"Error getting premium roles for member {member_id}: {e}")
            return []

    async def assign_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        duration_days: int = 30,
        source: str = "purchase",
    ) -> Tuple[bool, Optional[str]]:
        """Assign a premium role to a member."""
        try:
            # Get role from guild
            role_config = next((r for r in self.premium_roles_config if r["name"] == role_name), None)
            if not role_config:
                return False, "Role configuration not found"

            role = self.guild.get_role(role_config["id"])
            if not role:
                return False, "Role not found in guild"

            # Add role to member
            await member.add_roles(role, reason=f"Premium {source}")

            # Record in database
            async with self.bot.get_db() as session:
                expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
                await self.premium_repository.add_premium_role(
                    member_id=member.id,
                    role_name=role_name,
                    expires_at=expires_at,
                    duration_days=duration_days,
                    source=source,
                )
                await session.commit()

            # Remove mute roles
            await self.remove_mute_roles(member)

            self._log_operation(
                "assign_premium_role",
                member_id=member.id,
                role_name=role_name,
                duration_days=duration_days,
            )

            return True, None

        except Exception as e:
            self._log_error("assign_premium_role", e, member_id=member.id)
            return False, str(e)

    async def extend_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        additional_days: int,
        source: str = "extension",
    ) -> ExtensionResult:
        """Extend an existing premium role."""
        try:
            async with self.bot.get_db() as session:
                # Get current role
                current_role = await self.premium_repository.get_member_premium_role(member.id, role_name)

                if not current_role:
                    return ExtensionResult(
                        success=False,
                        error="Member does not have this role",
                        extension_type=ExtensionType.NONE,
                    )

                # Calculate new expiration
                current_expiry = current_role.expires_at
                if current_expiry < datetime.now(timezone.utc):
                    # Role has expired, start from now
                    new_expiry = datetime.now(timezone.utc) + timedelta(days=additional_days)
                else:
                    # Extend from current expiry
                    new_expiry = current_expiry + timedelta(days=additional_days)

                # Update in database
                current_role.expires_at = new_expiry
                current_role.duration_days += additional_days
                await session.commit()

                self._log_operation(
                    "extend_premium_role",
                    member_id=member.id,
                    role_name=role_name,
                    additional_days=additional_days,
                )

                return ExtensionResult(
                    success=True,
                    extension_type=ExtensionType.FULL_EXTENSION,
                    days_added=additional_days,
                    new_expiry=new_expiry,
                )

        except Exception as e:
            self._log_error("extend_premium_role", e, member_id=member.id)
            return ExtensionResult(
                success=False,
                error=str(e),
                extension_type=ExtensionType.NONE,
            )

    async def remove_premium_role(self, member: discord.Member, role_name: str) -> bool:
        """Remove a premium role from a member."""
        try:
            # Get role from guild
            role_config = next((r for r in self.premium_roles_config if r["name"] == role_name), None)
            if not role_config:
                return False

            role = self.guild.get_role(role_config["id"])
            if not role:
                return False

            # Remove role from member
            if role in member.roles:
                await member.remove_roles(role, reason="Premium expired or removed")

            # Remove from database
            async with self.bot.get_db() as session:
                await self.premium_repository.remove_premium_role(member.id, role_name)
                await session.commit()

            self._log_operation(
                "remove_premium_role",
                member_id=member.id,
                role_name=role_name,
            )

            return True

        except Exception as e:
            self._log_error("remove_premium_role", e, member_id=member.id)
            return False

    async def process_expired_premium_roles(self) -> list[dict[str, Any]]:
        """Process and remove expired premium roles."""
        try:
            expired_roles = []

            async with self.bot.get_db() as session:
                # Get all expired roles
                expired = await self.premium_repository.get_expired_premium_roles()

                for premium_role in expired:
                    member = self.guild.get_member(premium_role.member_id)
                    if member:
                        # Remove the role
                        success = await self.remove_premium_role(member, premium_role.role_name)
                        if success:
                            expired_roles.append(
                                {
                                    "member_id": premium_role.member_id,
                                    "role_name": premium_role.role_name,
                                    "expired_at": premium_role.expires_at,
                                }
                            )

            self._log_operation(
                "process_expired_premium_roles",
                expired_count=len(expired_roles),
            )

            return expired_roles

        except Exception as e:
            self._log_error("process_expired_premium_roles", e)
            return []
