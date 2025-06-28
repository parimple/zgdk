"""Interfaces for premium management system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Any, Optional

import discord


@dataclass
class PaymentData:
    """Data class for payment information."""

    name: str
    amount: int
    paid_at: datetime
    payment_type: str
    converted_amount: Optional[int] = None


class CommandTier(IntEnum):
    """Enum representing command access tiers."""

    TIER_0 = 0  # Available to everyone without any requirements
    TIER_T = 1  # Requires only T>0
    TIER_1 = 2  # Requires (booster/invite role + T>0) or any premium
    TIER_2 = 3  # Requires any premium role (zG50+)
    TIER_3 = 4  # Requires high premium role (zG500+)


class ExtensionType:
    """Types of premium role extensions."""

    NORMAL = "normal"  # Regular extension
    PARTIAL = "partial"  # Partial extension (with mute)
    UPGRADE = "upgrade"  # Upgrade to higher role


@dataclass
class PremiumRoleConfig:
    """Configuration for a premium role."""

    name: str
    role_id: int
    price: int
    priority: int
    duration_days: int


@dataclass
class ExtensionResult:
    """Result of a premium role extension operation."""

    success: bool
    extension_type: str
    days_added: int
    new_expiry: Optional[datetime]
    message: str
    upgraded_from: Optional[str] = None
    upgraded_to: Optional[str] = None


class IPremiumChecker(ABC):
    """Interface for checking premium role requirements and access."""

    @abstractmethod
    async def has_premium_role(self, member: discord.Member) -> bool:
        """Check if member has any premium role."""

    @abstractmethod
    async def get_member_premium_level(self, member: discord.Member) -> Optional[str]:
        """Get member's highest premium role level."""

    @abstractmethod
    async def check_command_access(self, member: discord.Member, command_name: str) -> tuple[bool, str]:
        """Check if member can access a specific command."""

    @abstractmethod
    async def get_command_tier(self, command_name: str) -> CommandTier:
        """Get the tier requirement for a command."""

    @abstractmethod
    async def has_bypass_permissions(self, member: discord.Member) -> bool:
        """Check if member has bypass permissions."""


class IPremiumRoleManager(ABC):
    """Interface for managing premium role operations."""

    @abstractmethod
    async def assign_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        duration_days: int,
        payment_amount: Optional[int] = None,
    ) -> ExtensionResult:
        """Assign a premium role to a member."""

    @abstractmethod
    async def extend_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        additional_days: int,
        payment_amount: Optional[int] = None,
    ) -> ExtensionResult:
        """Extend an existing premium role."""

    @abstractmethod
    async def upgrade_premium_role(
        self, member: discord.Member, from_role: str, to_role: str, payment_amount: int
    ) -> ExtensionResult:
        """Upgrade from one premium role to another."""

    @abstractmethod
    async def remove_premium_role(self, member: discord.Member, role_name: str) -> bool:
        """Remove a premium role from a member."""

    @abstractmethod
    async def get_premium_role_info(self, member: discord.Member) -> list[dict[str, Any]]:
        """Get premium role information for a member."""

    @abstractmethod
    async def process_expired_premium_roles(self) -> list[dict[str, Any]]:
        """Process all expired premium roles."""


class IPaymentProcessor(ABC):
    """Interface for processing premium payments."""

    @abstractmethod
    async def fetch_recent_payments(self) -> list[PaymentData]:
        """Fetch recent payments from external service."""

    @abstractmethod
    async def process_payment(self, payment: PaymentData) -> tuple[bool, str]:
        """Process a single payment and assign premium benefits."""

    @abstractmethod
    async def is_payment_handled(self, payment: PaymentData) -> bool:
        """Check if payment has already been processed."""

    @abstractmethod
    async def mark_payment_as_handled(self, payment: PaymentData) -> bool:
        """Mark payment as processed."""

    @abstractmethod
    def extract_member_id(self, payment_name: str) -> Optional[int]:
        """Extract Discord member ID from payment name."""

    @abstractmethod
    def calculate_premium_benefits(self, amount: int) -> Optional[tuple[str, int]]:
        """Calculate premium role and duration from payment amount."""


class IPremiumService(ABC):
    """Main interface for premium system operations."""

    @abstractmethod
    async def validate_premium_access(self, member: discord.Member, required_tier: CommandTier) -> tuple[bool, str]:
        """Validate if member has required premium access."""

    @abstractmethod
    async def handle_premium_payment(self, payment: PaymentData) -> tuple[bool, str, Optional[discord.Member]]:
        """Handle a premium payment end-to-end."""

    @abstractmethod
    async def get_member_premium_status(self, member: discord.Member) -> dict[str, Any]:
        """Get comprehensive premium status for a member."""

    @abstractmethod
    async def process_premium_maintenance(self) -> dict[str, int]:
        """Process premium maintenance tasks (expired roles, etc.)."""

    @abstractmethod
    async def calculate_role_value(self, member: discord.Member, target_role: str) -> Optional[int]:
        """Calculate the value of a premium role for pricing."""

    @abstractmethod
    async def count_unique_premium_users(self) -> int:
        """Count unique users with any active premium role."""
