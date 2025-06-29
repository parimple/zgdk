"""Refactored consolidated premium service that delegates to specialized services."""

import logging
from typing import Any, Optional, Tuple

import discord

from core.interfaces.premium_interfaces import (
    CommandTier,
    ExtensionResult,
    IPremiumChecker,
    IPremiumRoleManager,
    IPremiumService,
    PaymentData,
)
from core.repositories.premium_repository import PaymentRepository, PremiumRepository
from core.services.base_service import BaseService
from core.services.premium import (
    PremiumCheckerService,
    PremiumMaintenanceService,
    PremiumPaymentService,
    PremiumRoleService,
)

logger = logging.getLogger(__name__)


class ConsolidatedPremiumService(BaseService, IPremiumService, IPremiumChecker, IPremiumRoleManager):
    """Consolidated premium service that delegates to specialized services."""

    def __init__(
        self,
        premium_repository: PremiumRepository,
        payment_repository: PaymentRepository,
        bot: Any,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.bot = bot
        self.guild: Optional[discord.Guild] = None

        # Initialize specialized services
        self.checker_service = PremiumCheckerService(bot=bot, **kwargs)
        self.role_service = PremiumRoleService(premium_repository=premium_repository, bot=bot, **kwargs)
        self.payment_service = PremiumPaymentService(payment_repository=payment_repository, bot=bot, **kwargs)
        self.maintenance_service = PremiumMaintenanceService(premium_repository=premium_repository, bot=bot, **kwargs)

        # Keep references for backward compatibility
        self.premium_repository = premium_repository
        self.payment_repository = payment_repository
        self.config = bot.config

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate premium operations."""
        return True

    def set_guild(self, guild: discord.Guild) -> None:
        """Set the guild for all services."""
        self.guild = guild
        self.checker_service.set_guild(guild)
        self.role_service.set_guild(guild)
        self.payment_service.set_guild(guild)
        self.maintenance_service.set_guild(guild)
        logger.info(f"Guild set for ConsolidatedPremiumService: {guild.name}")

    # Delegate IPremiumChecker methods to checker service
    def get_user_highest_role_priority(self, member: discord.Member) -> int:
        """Delegate to checker service."""
        return self.checker_service.get_user_highest_role_priority(member)

    def get_user_highest_role_name(self, member: discord.Member) -> Optional[str]:
        """Delegate to checker service."""
        return self.checker_service.get_user_highest_role_name(member)

    async def has_premium_role(self, member: discord.Member) -> bool:
        """Delegate to checker service."""
        return await self.checker_service.has_premium_role(member)

    async def get_member_premium_level(self, member: discord.Member) -> Optional[str]:
        """Delegate to checker service."""
        return await self.checker_service.get_member_premium_level(member)

    async def has_active_bypass(self, member: discord.Member) -> bool:
        """Delegate to checker service."""
        return await self.checker_service.has_active_bypass(member)

    def has_booster_roles(self, member: discord.Member) -> bool:
        """Delegate to checker service."""
        return self.checker_service.has_booster_roles(member)

    def has_discord_invite_in_status(self, member: discord.Member) -> bool:
        """Delegate to checker service."""
        return self.checker_service.has_discord_invite_in_status(member)

    async def has_alternative_bypass_access(self, member: discord.Member) -> bool:
        """Delegate to checker service."""
        return await self.checker_service.has_alternative_bypass_access(member)

    async def get_command_tier(self, command_name: str) -> CommandTier:
        """Delegate to checker service."""
        return await self.checker_service.get_command_tier(command_name)

    async def has_bypass_permissions(self, member: discord.Member, command_name: Optional[str] = None) -> bool:
        """Delegate to checker service."""
        return await self.checker_service.has_bypass_permissions(member, command_name)

    async def get_member_premium_status(self, member: discord.Member) -> dict[str, Any]:
        """Delegate to checker service."""
        return await self.checker_service.get_member_premium_status(member)

    # Delegate IPremiumRoleManager methods to role service
    def get_role_price(self, role_name: str) -> int:
        """Delegate to role service."""
        return self.role_service.get_role_price(role_name)

    def has_mute_roles(self, member: discord.Member) -> bool:
        """Delegate to role service."""
        return self.role_service.has_mute_roles(member)

    async def remove_mute_roles(self, member: discord.Member):
        """Delegate to role service."""
        await self.role_service.remove_mute_roles(member)

    async def get_member_premium_roles(self, member_id: int) -> list[dict]:
        """Delegate to role service."""
        return await self.role_service.get_member_premium_roles(member_id)

    async def assign_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        duration_days: int = 30,
        source: str = "purchase",
    ) -> Tuple[bool, Optional[str]]:
        """Delegate to role service."""
        return await self.role_service.assign_premium_role(member, role_name, duration_days, source)

    async def extend_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        additional_days: int,
        source: str = "extension",
    ) -> ExtensionResult:
        """Delegate to role service."""
        return await self.role_service.extend_premium_role(member, role_name, additional_days, source)

    async def remove_premium_role(self, member: discord.Member, role_name: str) -> bool:
        """Delegate to role service."""
        return await self.role_service.remove_premium_role(member, role_name)

    async def process_expired_premium_roles(self) -> list[dict[str, Any]]:
        """Delegate to role service."""
        return await self.role_service.process_expired_premium_roles()

    # Delegate IPremiumService methods to payment service
    def extract_id(self, text: str) -> Optional[int]:
        """Delegate to payment service."""
        return self.payment_service.extract_id(text)

    async def get_banned_member(self, name_or_id: str) -> Optional[discord.User]:
        """Delegate to payment service."""
        return await self.payment_service.get_banned_member(name_or_id)

    async def get_member(self, name_or_id: str) -> Optional[discord.Member]:
        """Delegate to payment service."""
        return await self.payment_service.get_member(name_or_id)

    async def process_data(self, session, payment_data: PaymentData) -> None:
        """Delegate to payment service."""
        await self.payment_service.process_data(session, payment_data)

    async def notify_unban(self, member):
        """Delegate to payment service."""
        await self.payment_service.notify_unban(member)

    async def notify_member_not_found(self, name: str):
        """Delegate to payment service."""
        await self.payment_service.notify_member_not_found(name)

    def calculate_premium_benefits(self, amount: int) -> Optional[tuple[str, int]]:
        """Delegate to payment service."""
        return self.payment_service.calculate_premium_benefits(amount)

    # Delegate maintenance methods to maintenance service
    async def process_premium_maintenance(self) -> dict[str, int]:
        """Delegate to maintenance service."""
        return await self.maintenance_service.process_premium_maintenance()

    # Keep some backward compatibility properties
    @property
    def PREMIUM_PRIORITY(self):
        """Backward compatibility property."""
        return self.checker_service.PREMIUM_PRIORITY

    @property
    def PREMIUM_ROLES(self):
        """Backward compatibility property."""
        return self.role_service.PREMIUM_ROLES

    @property
    def COMMAND_TIERS(self):
        """Backward compatibility property."""
        return self.checker_service.COMMAND_TIERS
