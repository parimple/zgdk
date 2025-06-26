"""Premium service implementation with business logic."""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import discord

from core.interfaces.premium_interfaces import (
    CommandTier,
    ExtensionResult,
    ExtensionType,
    IPremiumChecker,
    IPremiumRoleManager,
    IPremiumService,
    PaymentData,
    PremiumRoleConfig,
)
from core.repositories.premium_repository import PaymentRepository, PremiumRepository
from core.services.base_service import BaseService


class PremiumService(
    BaseService, IPremiumService, IPremiumChecker, IPremiumRoleManager
):
    """Comprehensive premium service handling all premium-related operations."""

    # Premium role configurations
    PREMIUM_ROLES = {
        "zG50": PremiumRoleConfig("zG50", 0, 50, 1, 30),
        "zG100": PremiumRoleConfig("zG100", 0, 100, 2, 30),
        "zG500": PremiumRoleConfig("zG500", 0, 500, 3, 30),
        "zG1000": PremiumRoleConfig("zG1000", 0, 1000, 4, 30),
    }

    # Command tier requirements
    COMMAND_TIERS = {
        CommandTier.TIER_0: ["voicechat"],
        CommandTier.TIER_T: ["limit"],
        CommandTier.TIER_1: ["speak", "connect", "text", "reset"],
        CommandTier.TIER_2: ["view", "mod", "live", "color"],
        CommandTier.TIER_3: ["autokick"],
    }

    # Role IDs for bypass checking
    BOOSTER_ROLE_ID = 1052692705718829117
    INVITE_ROLE_ID = 960665311760248879

    def __init__(
        self,
        premium_repository: PremiumRepository,
        payment_repository: PaymentRepository,
        bot: Any,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.premium_repository = premium_repository
        self.payment_repository = payment_repository
        self.bot = bot
        self.guild: Optional[discord.Guild] = None

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate premium operations."""
        return True

    def set_guild(self, guild: discord.Guild) -> None:
        """Set the guild for premium operations."""
        self.guild = guild
        self._log_operation("set_guild", guild_id=guild.id)

    # IPremiumChecker implementation
    async def has_premium_role(self, member: discord.Member) -> bool:
        """Check if member has any premium role."""
        try:
            premium_roles = await self.premium_repository.get_member_premium_roles(
                member.id
            )

            # Check if any premium role is still valid
            current_time = datetime.utcnow()
            for role_data in premium_roles:
                expiry = role_data["expiry_time"]
                if expiry is None or expiry > current_time:
                    return True

            return False
        except Exception as e:
            self._log_error("has_premium_role", e, member_id=member.id)
            return False

    async def get_member_premium_level(self, member: discord.Member) -> Optional[str]:
        """Get member's highest premium role level."""
        try:
            premium_roles = await self.premium_repository.get_member_premium_roles(
                member.id
            )
            current_time = datetime.utcnow()

            highest_priority = 0
            highest_role = None

            for role_data in premium_roles:
                # Check if role is still valid
                expiry = role_data["expiry_time"]
                if expiry and expiry <= current_time:
                    continue

                role_name = role_data["role_name"]
                if role_name in self.PREMIUM_ROLES:
                    priority = self.PREMIUM_ROLES[role_name].priority
                    if priority > highest_priority:
                        highest_priority = priority
                        highest_role = role_name

            return highest_role
        except Exception as e:
            self._log_error("get_member_premium_level", e, member_id=member.id)
            return None

    async def check_command_access(
        self, member: discord.Member, command_name: str
    ) -> Tuple[bool, str]:
        """Check if member can access a specific command."""
        try:
            command_tier = await self.get_command_tier(command_name)
            return await self.validate_premium_access(member, command_tier)
        except Exception as e:
            self._log_error(
                "check_command_access", e, member_id=member.id, command=command_name
            )
            return False, "Błąd sprawdzania uprawnień"

    async def get_command_tier(self, command_name: str) -> CommandTier:
        """Get the tier requirement for a command."""
        for tier, commands in self.COMMAND_TIERS.items():
            if command_name in commands:
                return tier
        return CommandTier.TIER_0

    async def has_bypass_permissions(self, member: discord.Member) -> bool:
        """Check if member has bypass permissions."""
        try:
            # Check for booster or invite role
            booster_role = discord.utils.get(member.roles, id=self.BOOSTER_ROLE_ID)
            invite_role = discord.utils.get(member.roles, id=self.INVITE_ROLE_ID)

            return booster_role is not None or invite_role is not None
        except Exception as e:
            self._log_error("has_bypass_permissions", e, member_id=member.id)
            return False

    # IPremiumRoleManager implementation
    async def assign_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        duration_days: int,
        payment_amount: Optional[int] = None,
    ) -> ExtensionResult:
        """Assign a premium role to a member."""
        try:
            if role_name not in self.PREMIUM_ROLES:
                return ExtensionResult(
                    success=False,
                    extension_type=ExtensionType.NORMAL,
                    days_added=0,
                    new_expiry=None,
                    message=f"Nieznana rola premium: {role_name}",
                )

            # Get role from database
            role_data = await self.premium_repository.get_role_by_name(role_name)
            if not role_data:
                return ExtensionResult(
                    success=False,
                    extension_type=ExtensionType.NORMAL,
                    days_added=0,
                    new_expiry=None,
                    message=f"Rola {role_name} nie została znaleziona w bazie danych",
                )

            # Get Discord role
            discord_role = discord.utils.get(
                self.guild.roles, id=role_data["discord_id"]
            )
            if not discord_role:
                return ExtensionResult(
                    success=False,
                    extension_type=ExtensionType.NORMAL,
                    days_added=0,
                    new_expiry=None,
                    message=f"Rola Discord {role_name} nie została znaleziona",
                )

            # Calculate expiry time
            expiry_time = datetime.utcnow() + timedelta(days=duration_days)

            # Add Discord role
            await member.add_roles(
                discord_role, reason=f"Premium role assignment: {role_name}"
            )

            # Add to database
            await self.premium_repository.create_member_role(
                member_id=member.id,
                role_id=role_data["id"],
                expiry_time=expiry_time,
                role_type="premium",
            )

            self._log_operation(
                "assign_premium_role",
                member_id=member.id,
                role_name=role_name,
                duration_days=duration_days,
                payment_amount=payment_amount,
            )

            return ExtensionResult(
                success=True,
                extension_type=ExtensionType.NORMAL,
                days_added=duration_days,
                new_expiry=expiry_time,
                message=f"Przyznano rolę {role_name} na {duration_days} dni",
            )

        except Exception as e:
            self._log_error(
                "assign_premium_role", e, member_id=member.id, role_name=role_name
            )
            return ExtensionResult(
                success=False,
                extension_type=ExtensionType.NORMAL,
                days_added=0,
                new_expiry=None,
                message=f"Błąd przyznawania roli: {str(e)}",
            )

    async def extend_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        additional_days: int,
        payment_amount: Optional[int] = None,
    ) -> ExtensionResult:
        """Extend an existing premium role."""
        try:
            # Get existing role
            premium_roles = await self.premium_repository.get_member_premium_roles(
                member.id
            )
            existing_role = None

            for role_data in premium_roles:
                if role_data["role_name"] == role_name:
                    existing_role = role_data
                    break

            if not existing_role:
                # If role doesn't exist, assign it
                return await self.assign_premium_role(
                    member, role_name, additional_days, payment_amount
                )

            # Calculate new expiry time
            current_expiry = existing_role["expiry_time"]
            if current_expiry and current_expiry > datetime.utcnow():
                # Extend from current expiry
                new_expiry = current_expiry + timedelta(days=additional_days)
            else:
                # Role expired, extend from now
                new_expiry = datetime.utcnow() + timedelta(days=additional_days)

            # Update in database
            await self.premium_repository.update_role_expiry(
                member_id=member.id,
                role_id=existing_role["role_id"],
                new_expiry=new_expiry,
            )

            self._log_operation(
                "extend_premium_role",
                member_id=member.id,
                role_name=role_name,
                additional_days=additional_days,
                payment_amount=payment_amount,
            )

            return ExtensionResult(
                success=True,
                extension_type=ExtensionType.NORMAL,
                days_added=additional_days,
                new_expiry=new_expiry,
                message=f"Przedłużono rolę {role_name} o {additional_days} dni",
            )

        except Exception as e:
            self._log_error(
                "extend_premium_role", e, member_id=member.id, role_name=role_name
            )
            return ExtensionResult(
                success=False,
                extension_type=ExtensionType.NORMAL,
                days_added=0,
                new_expiry=None,
                message=f"Błąd przedłużania roli: {str(e)}",
            )

    async def upgrade_premium_role(
        self, member: discord.Member, from_role: str, to_role: str, payment_amount: int
    ) -> ExtensionResult:
        """Upgrade from one premium role to another."""
        try:
            # Validate roles exist
            if from_role not in self.PREMIUM_ROLES or to_role not in self.PREMIUM_ROLES:
                return ExtensionResult(
                    success=False,
                    extension_type=ExtensionType.UPGRADE,
                    days_added=0,
                    new_expiry=None,
                    message="Nieprawidłowe role do upgrade'u",
                )

            # Check if upgrade is valid (higher priority)
            from_priority = self.PREMIUM_ROLES[from_role].priority
            to_priority = self.PREMIUM_ROLES[to_role].priority

            if to_priority <= from_priority:
                return ExtensionResult(
                    success=False,
                    extension_type=ExtensionType.UPGRADE,
                    days_added=0,
                    new_expiry=None,
                    message=f"Nie można wykonać upgrade'u z {from_role} do {to_role}",
                )

            # Remove old role and assign new one
            await self.remove_premium_role(member, from_role)

            # Calculate duration based on payment
            duration_days = self._calculate_duration_from_payment(
                payment_amount, to_role
            )

            result = await self.assign_premium_role(
                member, to_role, duration_days, payment_amount
            )

            if result.success:
                result.extension_type = ExtensionType.UPGRADE
                result.upgraded_from = from_role
                result.upgraded_to = to_role
                result.message = (
                    f"Upgrade z {from_role} do {to_role} zakończony sukcesem"
                )

            return result

        except Exception as e:
            self._log_error("upgrade_premium_role", e, member_id=member.id)
            return ExtensionResult(
                success=False,
                extension_type=ExtensionType.UPGRADE,
                days_added=0,
                new_expiry=None,
                message=f"Błąd upgrade'u roli: {str(e)}",
            )

    async def remove_premium_role(self, member: discord.Member, role_name: str) -> bool:
        """Remove a premium role from a member."""
        try:
            # Get role data
            role_data = await self.premium_repository.get_role_by_name(role_name)
            if not role_data:
                return False

            # Remove from Discord
            discord_role = discord.utils.get(
                self.guild.roles, id=role_data["discord_id"]
            )
            if discord_role and discord_role in member.roles:
                await member.remove_roles(
                    discord_role, reason=f"Premium role removal: {role_name}"
                )

            # Remove from database
            await self.premium_repository.remove_member_role(
                member_id=member.id, role_id=role_data["id"]
            )

            self._log_operation(
                "remove_premium_role", member_id=member.id, role_name=role_name
            )
            return True

        except Exception as e:
            self._log_error(
                "remove_premium_role", e, member_id=member.id, role_name=role_name
            )
            return False

    async def get_premium_role_info(
        self, member: discord.Member
    ) -> List[Dict[str, Any]]:
        """Get premium role information for a member."""
        try:
            return await self.premium_repository.get_member_premium_roles(member.id)
        except Exception as e:
            self._log_error("get_premium_role_info", e, member_id=member.id)
            return []

    async def process_expired_premium_roles(self) -> List[Dict[str, Any]]:
        """Process all expired premium roles."""
        try:
            current_time = datetime.utcnow()
            expired_roles = await self.premium_repository.get_expired_premium_roles(
                current_time
            )

            processed = []
            for role_data in expired_roles:
                try:
                    member = self.guild.get_member(role_data["member_id"])
                    if member:
                        await self.remove_premium_role(member, role_data["role_name"])
                        processed.append(role_data)
                except Exception as e:
                    self._log_error("process_expired_role", e, role_data=role_data)

            self._log_operation(
                "process_expired_premium_roles", processed_count=len(processed)
            )
            return processed

        except Exception as e:
            self._log_error("process_expired_premium_roles", e)
            return []

    # IPremiumService implementation
    async def validate_premium_access(
        self, member: discord.Member, required_tier: CommandTier
    ) -> Tuple[bool, str]:
        """Validate if member has required premium access."""
        try:
            if required_tier == CommandTier.TIER_0:
                return True, "Dostęp dozwolony"

            # Get activity data (simplified - would integrate with activity system)
            # For now, assume T > 0
            has_activity = True

            if required_tier == CommandTier.TIER_T:
                if has_activity:
                    return True, "Dostęp dozwolony"
                return False, "Wymagana aktywność na serwerze"

            # Check bypass permissions for TIER_1
            if required_tier == CommandTier.TIER_1:
                has_bypass = await self.has_bypass_permissions(member)
                has_premium = await self.has_premium_role(member)

                if (has_bypass and has_activity) or has_premium:
                    return True, "Dostęp dozwolony"
                return False, "Wymagana rola Booster/Invite lub Premium"

            # Check premium role for TIER_2+
            premium_level = await self.get_member_premium_level(member)
            if not premium_level:
                return False, "Wymagana rola Premium"

            if required_tier == CommandTier.TIER_2:
                return True, "Dostęp dozwolony"

            if required_tier == CommandTier.TIER_3:
                if premium_level in ["zG500", "zG1000"]:
                    return True, "Dostęp dozwolony"
                return False, "Wymagana wyższa rola Premium (zG500+)"

            return False, "Nieznany poziom dostępu"

        except Exception as e:
            self._log_error("validate_premium_access", e, member_id=member.id)
            return False, "Błąd sprawdzania uprawnień"

    async def handle_premium_payment(
        self, payment: PaymentData
    ) -> Tuple[bool, str, Optional[discord.Member]]:
        """Handle a premium payment end-to-end."""
        try:
            # Extract member ID from payment name
            member_id = self._extract_member_id_from_payment(payment.name)
            if not member_id:
                return (
                    False,
                    "Nie można znaleźć ID użytkownika w nazwie płatności",
                    None,
                )

            member = self.guild.get_member(member_id)
            if not member:
                return (
                    False,
                    f"Użytkownik {member_id} nie został znaleziony na serwerze",
                    None,
                )

            # Calculate premium benefits
            benefits = self.calculate_premium_benefits(payment.amount)
            if not benefits:
                return False, f"Nieprawidłowa kwota płatności: {payment.amount}", member

            role_name, duration_days = benefits

            # Assign or extend role
            result = await self.extend_premium_role(
                member, role_name, duration_days, payment.amount
            )

            if result.success:
                return True, result.message, member
            else:
                return False, result.message, member

        except Exception as e:
            self._log_error("handle_premium_payment", e, payment_name=payment.name)
            return False, f"Błąd przetwarzania płatności: {str(e)}", None

    async def get_member_premium_status(self, member: discord.Member) -> Dict[str, Any]:
        """Get comprehensive premium status for a member."""
        try:
            premium_roles = await self.get_premium_role_info(member)
            premium_level = await self.get_member_premium_level(member)
            has_premium = await self.has_premium_role(member)
            has_bypass = await self.has_bypass_permissions(member)

            return {
                "member_id": member.id,
                "has_premium": has_premium,
                "premium_level": premium_level,
                "has_bypass": has_bypass,
                "premium_roles": premium_roles,
                "access_tiers": {
                    "tier_0": True,
                    "tier_t": True,  # Assuming activity > 0
                    "tier_1": has_bypass or has_premium,
                    "tier_2": has_premium,
                    "tier_3": premium_level in ["zG500", "zG1000"]
                    if premium_level
                    else False,
                },
            }

        except Exception as e:
            self._log_error("get_member_premium_status", e, member_id=member.id)
            return {"error": str(e)}

    async def process_premium_maintenance(self) -> Dict[str, int]:
        """Process premium maintenance tasks."""
        try:
            expired_roles = await self.process_expired_premium_roles()

            return {
                "expired_roles_processed": len(expired_roles),
                "maintenance_completed": 1,
            }

        except Exception as e:
            self._log_error("process_premium_maintenance", e)
            return {"error": 1}

    async def calculate_role_value(
        self, member: discord.Member, target_role: str
    ) -> Optional[int]:
        """Calculate the value of a premium role for pricing."""
        if target_role not in self.PREMIUM_ROLES:
            return None
        return self.PREMIUM_ROLES[target_role].price

    def _extract_member_id_from_payment(self, payment_name: str) -> Optional[int]:
        """Extract Discord member ID from payment name."""
        # Look for Discord ID pattern (17-19 digits)
        match = re.search(r"\b(\d{17,19})\b", payment_name)
        if match:
            return int(match.group(1))
        return None

    def calculate_premium_benefits(self, amount: int) -> Optional[Tuple[str, int]]:
        """Calculate premium role and duration from payment amount."""
        # Mapping based on original premium logic
        amount_mapping = {
            50: ("zG50", 30),
            100: ("zG100", 30),
            500: ("zG500", 30),
            1000: ("zG1000", 30),
            # Add more mappings as needed
        }

        return amount_mapping.get(amount)

    def _calculate_duration_from_payment(self, amount: int, role_name: str) -> int:
        """Calculate duration days from payment amount for specific role."""
        base_price = self.PREMIUM_ROLES[role_name].price
        base_duration = self.PREMIUM_ROLES[role_name].duration_days

        # Simple calculation: amount / base_price * base_duration
        multiplier = amount / base_price
        return int(multiplier * base_duration)
