"""Consolidated Premium service implementation with all business logic."""

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import discord
from sqlalchemy.exc import IntegrityError

from core.interfaces.member_interfaces import IMemberService
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
from core.repositories import InviteRepository
from core.repositories.premium_repository import PaymentRepository, PremiumRepository
from core.services.base_service import BaseService
from core.services.cache_service import CacheService
from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries

logger = logging.getLogger(__name__)


class ConsolidatedPremiumService(BaseService, IPremiumService, IPremiumChecker, IPremiumRoleManager):
    """Comprehensive premium service handling all premium-related operations."""

    # Premium role configurations from config
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
    BOOSTER_ROLE_ID = 1052692705718829117  # ♼
    INVITE_ROLE_ID = 960665311760248879  # ♵

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
        payment_repository: PaymentRepository,
        bot: Any,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.premium_repository = premium_repository
        self.payment_repository = payment_repository
        self.bot = bot
        self.guild: Optional[discord.Guild] = None
        self.cache_service = CacheService(max_size=5000, default_ttl=300)  # 5 min cache
        self.config = bot.config
        self.mute_roles = {role["name"]: role for role in bot.config.get("mute_roles", [])}
        self.premium_roles_config = bot.config.get("premium_roles", [])

        # Initialize dynamic mappings
        self.partial_extensions = {}
        self.upgrade_paths = {}
        self.legacy_amounts = {}

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate premium operations."""
        return True

    def set_guild(self, guild: discord.Guild) -> None:
        """Set the guild for premium operations."""
        self.guild = guild
        self._log_operation("set_guild", guild_id=guild.id)
        # Initialize mappings after guild is set
        self.initialize_legacy_amounts()
        self.initialize_partial_extensions()
        self.initialize_upgrade_paths()

    def initialize_legacy_amounts(self):
        """Initialize legacy amounts from config."""
        if self.bot.config.get("legacy_system", {}).get("enabled", False):
            self.legacy_amounts = self.bot.config["legacy_system"]["amounts"]

    def initialize_partial_extensions(self):
        """Initialize partial extensions based on config prices."""
        for role in self.premium_roles_config:
            role_name = role["name"]
            role_price = role["price"]
            self.partial_extensions[role_name] = {}

            # Calculate days for each possible price point
            for price in [49, 50, 99, 100, 499, 500]:
                if price <= role_price:
                    days = int(price / role_price * self.MONTHLY_DURATION)
                    self.partial_extensions[role_name][price] = days

            # Add exact price point
            self.partial_extensions[role_name][role_price] = self.MONTHLY_DURATION

    def initialize_upgrade_paths(self):
        """Initialize upgrade paths based on config prices."""
        sorted_roles = sorted(self.premium_roles_config, key=lambda x: x["price"])

        for i in range(len(sorted_roles) - 1):
            current_role = sorted_roles[i]
            next_role = sorted_roles[i + 1]
            upgrade_cost = next_role["price"] - current_role["price"]
            self.upgrade_paths[current_role["name"]] = {next_role["name"]: upgrade_cost}

    def extract_id(self, text: str) -> Optional[int]:
        """Extract ID from various formats"""
        match = re.search(r"\b\d{17,19}\b", text)
        return int(match.group()) if match else None

    async def get_banned_member(self, name_or_id: str) -> Optional[discord.User]:
        """Get banned Member by ID or exact name"""
        if not self.guild:
            logger.error("Guild is not set in get_banned_member. Skipping ban check.")
            return None

        user_id = self.extract_id(name_or_id)
        if user_id:
            try:
                user = discord.Object(id=user_id)
                ban_entry = await self.guild.fetch_ban(user)
                if ban_entry:
                    logger.info("User is banned by ID: %s", ban_entry.user.id)
                    return ban_entry.user
            except discord.NotFound:
                logger.info("User is not banned by ID: %s", user_id)
            except discord.Forbidden:
                logger.error("Bot doesn't have permission to fetch bans")
            except Exception as e:
                logger.error("Error checking ban by ID: %s", str(e))
            return None

        # Try by name only if no ID provided
        try:
            ban_list = [entry async for entry in self.guild.bans()]
            for ban_entry in ban_list:
                if name_or_id.lower() == ban_entry.user.name.lower():
                    logger.info("Banned user found by exact name: %s", ban_entry.user.id)
                    return ban_entry.user
        except discord.Forbidden:
            logger.error("Bot doesn't have permission to fetch bans")
        except Exception as e:
            logger.error("Error fetching bans: %s", str(e))

        return None

    async def get_member(self, name_or_id: str) -> Optional[discord.Member]:
        """Get Member by ID or Username"""
        if not self.guild:
            return None

        # Try to extract an ID
        user_id = self.extract_id(name_or_id)
        if user_id:
            logger.info("get_member_id: %s is digit", user_id)
            try:
                member = await self.guild.fetch_member(user_id)
                if member:
                    return member
            except discord.NotFound:
                logger.info("Member not found with ID: %s", user_id)

        # Try to get member by exact name or display name (case-insensitive)
        logger.info("get_member_id: %s from guild: %s", name_or_id, self.guild)
        name_or_id_lower = name_or_id.lower()
        for member in self.guild.members:
            if (
                (member.name and name_or_id_lower == member.name.lower())
                or (member.display_name and name_or_id_lower == member.display_name.lower())
                or (member.global_name and name_or_id_lower == member.global_name.lower())
            ):
                return member

        logger.warning(f"Member not found: {name_or_id}")
        return None

    def has_mute_roles(self, member: discord.Member) -> bool:
        """Check if member has any mute roles."""
        return any(role for role in self.mute_roles.values() if role["id"] in [r.id for r in member.roles])

    async def remove_mute_roles(self, member: discord.Member):
        """Remove all mute roles from the member."""
        if not self.guild:
            return

        roles_to_remove = [
            self.guild.get_role(role["id"])
            for role in self.mute_roles.values()
            if self.guild.get_role(role["id"]) in member.roles
        ]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            roles_removed = [role.name for role in roles_to_remove]
            try:
                message = f"Usunięto następujące role mutujące: {', '.join(roles_removed)}"
                await member.send(message)
            except discord.Forbidden:
                logger.warning(f"Could not send DM to {member.display_name} about removed mute roles")

    def get_user_highest_role_priority(self, member: discord.Member) -> int:
        """Get the highest premium role priority for a member."""
        if not self.guild:
            return 0

        user_highest_priority = 0
        for role_name, priority in self.PREMIUM_PRIORITY.items():
            role_obj = discord.utils.get(self.guild.roles, name=role_name)
            if role_obj and role_obj in member.roles:
                user_highest_priority = max(user_highest_priority, priority)
        return user_highest_priority

    def get_user_highest_role_name(self, member: discord.Member) -> Optional[str]:
        """Get the name of highest premium role a member has."""
        if not self.guild:
            return None

        highest_priority = 0
        highest_role_name = None

        for role_name, priority in self.PREMIUM_PRIORITY.items():
            role_obj = discord.utils.get(self.guild.roles, name=role_name)
            if role_obj and role_obj in member.roles and priority > highest_priority:
                highest_priority = priority
                highest_role_name = role_name

        return highest_role_name

    # IPremiumChecker implementation
    async def has_premium_role(self, member: discord.Member) -> bool:
        """Check if member has any premium role (cached)."""
        try:
            # Try cache first
            cached_result = await self.cache_service.get("premium", "has_premium_role", member_id=member.id)
            if cached_result is not None:
                return cached_result

            # Check Discord roles directly
            user_roles = [role.name for role in member.roles]
            has_premium = any(role_name in self.PREMIUM_PRIORITY for role_name in user_roles)

            # Cache result for 5 minutes
            await self.cache_service.set(
                "premium",
                "has_premium_role",
                has_premium,
                ttl=300,
                tags={f"member:{member.id}", "premium_roles"},
                member_id=member.id,
            )

            return has_premium
        except Exception as e:
            self._log_error("has_premium_role", e, member_id=member.id)
            return False

    async def get_member_premium_level(self, member: discord.Member) -> Optional[str]:
        """Get member's highest premium role level."""
        return self.get_user_highest_role_name(member)

    async def get_member_premium_roles(self, member_id: int) -> list[dict]:
        """Get all premium roles for a member from database."""
        try:
            async with self.bot.get_db() as session:
                roles = []
                for role_name in self.PREMIUM_PRIORITY:
                    role_obj = discord.utils.get(self.guild.roles, name=role_name)
                    if role_obj:
                        db_role = await RoleQueries.get_member_role(session, member_id, role_obj.id)
                        if db_role:
                            roles.append(
                                {
                                    "role_name": role_name,
                                    "role_id": role_obj.id,
                                    "expiration_date": db_role.expiration_date,
                                    "member_id": member_id,
                                }
                            )
                return roles
        except Exception as e:
            self._log_error("get_member_premium_roles", e, member_id=member_id)
            return []

    async def has_active_bypass(self, member: discord.Member) -> bool:
        """Check if user has active T (bypass)."""
        try:
            async with self.bot.get_db() as session:
                bypass_until = await MemberQueries.get_voice_bypass_status(session, member.id)
                return bypass_until is not None and bypass_until > datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Error in has_active_bypass for user {member.id}: {e}")
            return False

    def has_booster_roles(self, member: discord.Member) -> bool:
        """Check if user has booster or invite role."""
        return any(role.id in [self.BOOSTER_ROLE_ID, self.INVITE_ROLE_ID] for role in member.roles)

    def has_discord_invite_in_status(self, member: discord.Member) -> bool:
        """Check if user has 'discord.gg/zagadka' in their status."""
        target_text = "discord.gg/zagadka"

        # Check activities
        if member.activities:
            for activity in member.activities:
                if hasattr(activity, "name") and activity.name and target_text in activity.name.lower():
                    return True
                if hasattr(activity, "details") and activity.details and target_text in activity.details.lower():
                    return True
                if hasattr(activity, "state") and activity.state and target_text in activity.state.lower():
                    return True
                if isinstance(activity, discord.CustomActivity):
                    if activity.name and target_text in activity.name.lower():
                        return True

        # Try through guild member
        try:
            if self.guild:
                guild_member = self.guild.get_member(member.id)
                if guild_member and guild_member.activities:
                    for activity in guild_member.activities:
                        if hasattr(activity, "name") and activity.name and target_text in activity.name.lower():
                            return True
                        if isinstance(activity, discord.CustomActivity):
                            if activity.name and target_text in activity.name.lower():
                                return True
        except Exception:
            pass

        return False

    async def has_alternative_bypass_access(self, member: discord.Member) -> bool:
        """Check if user qualifies for alternative bypass access."""
        try:
            logger.debug(f"Checking alternative bypass access for user {member.id}")

            if not self.has_booster_roles(member):
                logger.debug(f"User {member.id} does not have booster roles")
                return False

            if not self.has_discord_invite_in_status(member):
                logger.debug(f"User {member.id} does not have discord invite in status")
                return False

            # Check invite count
            async with self.bot.get_db() as session:
                invite_repo = InviteRepository(session)
                invite_count = await invite_repo.get_member_valid_invite_count(member.id, self.guild, min_days=7)
                logger.debug(f"User {member.id} has {invite_count} valid invites")
                return invite_count >= 4
        except Exception as e:
            logger.error(f"Error in has_alternative_bypass_access for user {member.id}: {e}")
            return False

    async def check_command_access(self, member: discord.Member, command_name: str) -> tuple[bool, str]:
        """Check if member can access a specific command."""
        try:
            command_tier = await self.get_command_tier(command_name)
            return await self.validate_premium_access(member, command_tier)
        except Exception as e:
            self._log_error("check_command_access", e, member_id=member.id, command=command_name)
            return False, "Błąd sprawdzania uprawnień"

    async def get_command_tier(self, command_name: str) -> CommandTier:
        """Get the tier requirement for a command."""
        for tier, commands in self.COMMAND_TIERS.items():
            if command_name in commands:
                return tier
        return CommandTier.TIER_0

    async def has_bypass_permissions(self, member: discord.Member) -> bool:
        """Check if member has bypass permissions."""
        return self.has_booster_roles(member)

    # Premium role assignment and management
    async def assign_or_extend_premium_role(
        self,
        session,
        member: discord.Member,
        role_name: str,
        amount: int,
        duration_days: int = MONTHLY_DURATION,
        source: str = "shop",
    ) -> Tuple[discord.Embed, Optional[int], Optional[bool]]:
        """
        Main function to handle all premium role operations.
        Returns (embed, refund_amount, add_to_wallet).
        """
        if not self.guild:
            return (
                discord.Embed(
                    title="Błąd",
                    description="Guild nie jest ustawiony",
                    color=discord.Color.red(),
                ),
                None,
                None,
            )

        role = discord.utils.get(self.guild.roles, name=role_name)
        if not role:
            return (
                discord.Embed(
                    title="Błąd",
                    description=f"Nie znaleziono roli {role_name}",
                    color=discord.Color.red(),
                ),
                None,
                None,
            )

        # Get current role if exists
        current_role = await RoleQueries.get_member_role(session, member.id, role.id)

        # Get user's highest role
        highest_role_name = self.get_user_highest_role_name(member)
        highest_role_priority = self.PREMIUM_PRIORITY.get(highest_role_name, 0) if highest_role_name else 0
        current_role_priority = self.PREMIUM_PRIORITY.get(role_name, 0)

        # Special case for payment == 49/50 - remove mute and extend role
        is_zg50_payment = role_name == "zG50" and amount in [49, 50]

        if is_zg50_payment and self.has_mute_roles(member):
            await self.remove_mute_roles(member)

            # If user already has a premium role, extend it based on their highest role
            if highest_role_name:
                role_to_extend = discord.utils.get(self.guild.roles, name=highest_role_name)
                if role_to_extend:
                    # Get the role database entry
                    db_role = await RoleQueries.get_member_role(session, member.id, role_to_extend.id)

                    # Calculate days to extend based on highest role
                    days_to_add = {
                        "zG50": self.ZG50_EXTENSION,
                        "zG100": self.ZG100_EXTENSION,
                        "zG500": self.ZG500_EXTENSION,
                        "zG1000": self.ZG1000_EXTENSION,
                    }.get(highest_role_name, self.ZG50_EXTENSION)

                    # Update expiration date
                    updated_role = await RoleQueries.update_role_expiration_date(
                        session, member.id, role_to_extend.id, timedelta(days=days_to_add)
                    )

                    if updated_role:
                        await session.flush()
                        embed = discord.Embed(
                            title="Gratulacje!",
                            description=f"Przedłużyłeś rolę {highest_role_name} o {days_to_add} dni i zdjęto ci muta!",
                            color=discord.Color.green(),
                        )
                        return embed, None, False  # Don't add to wallet

        # If user has a higher role than the one they're trying to buy, add to wallet
        if highest_role_priority > current_role_priority and source == "payment":
            logger.info(
                f"User {member.display_name} has higher role ({highest_role_name}) than {role_name}. "
                f"Adding amount to wallet instead."
            )
            embed = discord.Embed(
                title="Doładowanie konta",
                description=f"Posiadasz już wyższą rolę ({highest_role_name}). "
                f"Kwota została dodana do Twojego portfela.",
                color=discord.Color.blue(),
            )
            return embed, None, True  # Add to wallet

        # Check for partial extension
        partial_result = await self.check_partial_extension(session, member, role_name, amount, current_role)
        if partial_result:
            embed, days_to_add = partial_result
            updated_role = await RoleQueries.update_role_expiration_date(
                session, member.id, role.id, timedelta(days=days_to_add)
            )
            if updated_role:
                await session.flush()
                await self.remove_mute_roles(member)
                return embed, None, False
            else:
                raise ValueError(f"Failed to update role expiration for {role_name}")

        # Normal extension/purchase
        if current_role and role in member.roles:
            # Extend existing role
            extend_days = duration_days
            logger.info(f"[PREMIUM] Extending role {role_name} for {member.display_name}")

            updated_role = await RoleQueries.update_role_expiration_date(
                session, member.id, role.id, timedelta(days=extend_days)
            )
            if updated_role:
                await session.flush()
                description = f"Przedłużyłeś rolę {role_name} o {extend_days} dni!"
                embed = discord.Embed(
                    title="Gratulacje!",
                    description=description,
                    color=discord.Color.green(),
                )
                return embed, None, None
            else:
                raise ValueError(f"Failed to update role expiration for {role_name}")
        else:
            # New purchase
            await RoleQueries.add_role_to_member(session, member.id, role.id, timedelta(days=duration_days))
            await session.flush()
            await member.add_roles(role)

            embed = discord.Embed(
                title="Gratulacje!",
                description=f"Zakupiłeś rolę {role_name}!",
                color=discord.Color.green(),
            )
            return embed, None, None

    async def check_partial_extension(
        self,
        session,
        member: discord.Member,
        role_name: str,
        amount: int,
        current_role=None,
    ) -> Optional[Tuple[discord.Embed, int]]:
        """Check if a partial extension is possible."""
        if not self.has_mute_roles(member) or not self.guild:
            return None

        role = discord.utils.get(self.guild.roles, name=role_name)
        if not role:
            return None

        # Check if amount matches partial extension rules
        if role_name not in self.partial_extensions:
            return None

        # Check if role priority is not higher than user's highest role
        role_priority = self.PREMIUM_PRIORITY.get(role_name, 0)
        user_highest_priority = self.get_user_highest_role_priority(member)
        if role_priority > user_highest_priority:
            return None

        days_to_add = self.partial_extensions[role_name].get(amount, 0)
        if days_to_add <= 0:
            return None

        # If user has the role, extend it
        if current_role and role in member.roles:
            embed = discord.Embed(
                title="Gratulacje!",
                description=f"Przedłużyłeś rolę {role_name} o {days_to_add} dni i zdjęto ci muta!",
                color=discord.Color.green(),
            )
            return embed, days_to_add

        return None

    async def assign_temporary_roles(self, session, member: discord.Member, amount: int):
        """Assign temporary roles based on donation amount."""
        if not self.guild:
            return

        logger.info(f"[TEMP_ROLES] Starting assign_temporary_roles for {member.display_name} with amount {amount}")

        roles_tiers = [
            (15, "$2"),
            (25, "$4"),
            (45, "$8"),
            (85, "$16"),
            (160, "$32"),
            (320, "$64"),
            (640, "$128"),
        ]

        for amount_required, role_name in roles_tiers:
            logger.info(f"[TEMP_ROLES] Checking tier: {amount_required} -> {role_name}")
            if amount >= amount_required:
                role = discord.utils.get(self.guild.roles, name=role_name)
                if role:
                    try:
                        current_role = await RoleQueries.get_member_role(session, member.id, role.id)
                        days_to_add = 30

                        if current_role and role in member.roles:
                            days_left = (current_role.expiration_date - datetime.now(timezone.utc)).days
                            if days_left < 1 or days_left >= 29:
                                days_to_add = 33

                        await RoleQueries.add_or_update_role_to_member(
                            session, member.id, role.id, timedelta(days=days_to_add)
                        )

                        if role not in member.roles:
                            await member.add_roles(role)
                            logger.info(f"[TEMP_ROLES] Added role {role_name} to {member.display_name}")
                        else:
                            logger.info(f"[TEMP_ROLES] Updated role {role_name} for {member.display_name}")

                        # After $4 and $8 roles, wait 5 seconds
                        if role_name in ["$4", "$8"]:
                            await asyncio.sleep(5)

                    except Exception as e:
                        logger.error(f"[TEMP_ROLES] Error assigning role {role_name}: {str(e)}")

    # Payment processing
    async def process_data(self, session, payment_data: PaymentData) -> None:
        """Process Payment using new service architecture"""
        if not self.guild:
            logger.error("Guild is not set in process_data. Cannot process payment: %s", payment_data)
            return

        logger.info("Processing payment: %s", payment_data)

        # Get services
        member_service = await self.bot.get_service(IMemberService, session)

        # First, try to find the banned member
        banned_member = await self.get_banned_member(payment_data.name)
        if banned_member:
            logger.info("unban: %s", banned_member)
            await self.guild.unban(banned_member)
            await self.notify_unban(banned_member)
            payment = await HandledPaymentQueries.add_payment(
                session,
                banned_member.id,
                payment_data.name,
                payment_data.amount,
                payment_data.paid_at,
                payment_data.payment_type,
            )
        else:
            # If not banned, find the member in the guild
            member = await self.get_member(payment_data.name)
            if member:
                logger.info("member id: %s", member)
                payment = await HandledPaymentQueries.add_payment(
                    session,
                    member.id,
                    payment_data.name,
                    payment_data.amount,
                    payment_data.paid_at,
                    payment_data.payment_type,
                )
                logger.info("payment: %s", payment)

                # Use new service architecture
                await member_service.get_or_create_member(member)

                # Check legacy conversion
                final_amount = payment_data.amount
                if self.bot.config.get("legacy_system", {}).get("enabled", False):
                    legacy_amounts = self.bot.config.get("legacy_system", {}).get("amounts", {})
                    if final_amount in legacy_amounts:
                        # Convert to new amount
                        final_amount = legacy_amounts[final_amount]
                        # Randomly add +1 (50% chance)
                        add_one = random.choice([True, False])
                        if add_one:
                            final_amount += 1
                        payment_data.converted_amount = final_amount
                        logger.info(f"Legacy amount converted: {payment_data.amount} -> {final_amount}")

                # Check if final amount matches premium role
                is_premium_payment = False
                for role_config in self.bot.config["premium_roles"]:
                    if final_amount in [role_config["price"], role_config["price"] + 1]:
                        is_premium_payment = True
                        logger.info(f"Found premium role match for amount {final_amount}")
                        break

                # Add to wallet only if not a premium payment
                if not is_premium_payment:
                    logger.info(f"No premium role match, adding to wallet: {payment_data.amount}")
                    db_member = await member_service.get_or_create_member(member)
                    new_balance = db_member.wallet_balance + payment_data.amount
                    await member_service.update_member_info(db_member, wallet_balance=new_balance)
            else:
                logger.warning("Member not found for payment: %s", payment_data.name)
                payment = await HandledPaymentQueries.add_payment(
                    session,
                    None,
                    payment_data.name,
                    payment_data.amount,
                    payment_data.paid_at,
                    payment_data.payment_type,
                )
                await self.notify_member_not_found(payment_data.name)

        try:
            await session.flush()
        except IntegrityError as e:
            logger.error(f"IntegrityError during payment processing: {str(e)}")
            await session.rollback()
        except Exception as e:
            logger.error(f"Unexpected error during payment processing: {str(e)}")
            await session.rollback()

    async def notify_unban(self, member):
        """Send notification about unban"""
        if not self.guild:
            return

        channel_id = self.config["channels"]["donation"]
        channel = self.guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="Użytkownik odbanowany",
                description=f"Użytkownik {member.mention} został odbanowany.",
                color=discord.Color.green(),
            )
            await channel.send(embed=embed)

    async def notify_member_not_found(self, name: str):
        """Send notification about member not found"""
        if not self.guild:
            return

        channel_id = self.config["channels"]["donation"]
        channel = self.guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="Użytkownik nie znaleziony",
                description=f"Nie znaleziono użytkownika o nazwie: {name}",
                color=discord.Color.red(),
            )
            await channel.send(embed=embed)

    # IPremiumService implementation
    async def validate_premium_access(self, member: discord.Member, required_tier: CommandTier) -> tuple[bool, str]:
        """Validate if member has required premium access."""
        try:
            if required_tier == CommandTier.TIER_0:
                return True, "Dostęp dozwolony"

            has_bypass = await self.has_active_bypass(member)
            has_alternative = await self.has_alternative_bypass_access(member)
            has_premium = await self.has_premium_role(member)
            has_booster = self.has_booster_roles(member)

            if required_tier == CommandTier.TIER_T:
                if has_bypass or has_premium or has_alternative:
                    return True, "Dostęp dozwolony"
                return False, "Wymagana aktywność (T>0) lub alternatywny dostęp"

            if required_tier == CommandTier.TIER_1:
                if has_premium:
                    return True, "Dostęp dozwolony"
                if has_booster and (has_bypass or has_alternative):
                    return True, "Dostęp dozwolony"
                if has_booster:
                    return False, "Twój bypass wygasł! Użyj `/bypass` aby go przedłużyć."
                else:
                    return False, "Wymagana rola premium lub booster"

            if required_tier == CommandTier.TIER_2:
                if has_premium:
                    return True, "Dostęp dozwolony"
                return False, "Wymagana rola: zG50, zG100, zG500, zG1000"

            if required_tier == CommandTier.TIER_3:
                premium_level = await self.get_member_premium_level(member)
                if premium_level in ["zG500", "zG1000"]:
                    return True, "Dostęp dozwolony"
                return False, "Wymagana rola: zG500, zG1000"

            return False, "Nieznany poziom dostępu"

        except Exception as e:
            self._log_error("validate_premium_access", e, member_id=member.id)
            return False, "Błąd sprawdzania uprawnień"

    async def handle_premium_payment(self, payment: PaymentData) -> tuple[bool, str, Optional[discord.Member]]:
        """Handle a premium payment end-to-end."""
        try:
            async with self.bot.get_db() as session:
                await self.process_data(session, payment)
                await session.commit()
                return True, "Płatność przetworzona", None
        except Exception as e:
            self._log_error("handle_premium_payment", e, payment_name=payment.name)
            return False, f"Błąd przetwarzania płatności: {str(e)}", None

    async def get_member_premium_status(self, member: discord.Member) -> dict[str, Any]:
        """Get comprehensive premium status for a member."""
        try:
            premium_roles = await self.get_member_premium_roles(member.id)
            premium_level = await self.get_member_premium_level(member)
            has_premium = await self.has_premium_role(member)
            has_bypass = await self.has_bypass_permissions(member)
            has_active_bypass = await self.has_active_bypass(member)
            has_alternative = await self.has_alternative_bypass_access(member)

            return {
                "member_id": member.id,
                "has_premium": has_premium,
                "premium_level": premium_level,
                "has_bypass": has_bypass,
                "has_active_bypass": has_active_bypass,
                "has_alternative_access": has_alternative,
                "premium_roles": premium_roles,
                "access_tiers": {
                    "tier_0": True,
                    "tier_t": has_active_bypass or has_alternative or has_premium,
                    "tier_1": has_bypass and (has_active_bypass or has_alternative) or has_premium,
                    "tier_2": has_premium,
                    "tier_3": premium_level in ["zG500", "zG1000"] if premium_level else False,
                },
            }

        except Exception as e:
            self._log_error("get_member_premium_status", e, member_id=member.id)
            return {"error": str(e)}

    async def process_premium_maintenance(self) -> dict[str, int]:
        """Process premium maintenance tasks."""
        try:
            # Process expired roles
            processed = 0
            async with self.bot.get_db() as session:
                # Get all premium roles
                for role_name in self.PREMIUM_PRIORITY:
                    role_obj = discord.utils.get(self.guild.roles, name=role_name)
                    if role_obj:
                        # Get expired roles from database
                        expired = await RoleQueries.get_expired_roles(session, role_obj.id)
                        for member_role in expired:
                            try:
                                member = self.guild.get_member(member_role.member_id)
                                if member and role_obj in member.roles:
                                    await member.remove_roles(role_obj)
                                    await RoleQueries.delete_member_role(session, member_role.member_id, role_obj.id)
                                    processed += 1
                            except Exception as e:
                                logger.error(f"Error removing expired role: {e}")
                await session.commit()

            return {
                "expired_roles_processed": processed,
                "maintenance_completed": 1,
            }

        except Exception as e:
            self._log_error("process_premium_maintenance", e)
            return {"error": 1}

    async def calculate_role_value(self, member: discord.Member, target_role: str) -> Optional[int]:
        """Calculate the value of a premium role for pricing."""
        if target_role not in self.PREMIUM_ROLES:
            return None
        return self.PREMIUM_ROLES[target_role].price

    def calculate_premium_benefits(self, amount: int) -> Optional[tuple[str, int]]:
        """Calculate premium role and duration from payment amount."""
        # Mapping based on config
        for role in self.premium_roles_config:
            if amount == role["price"]:
                return (role["name"], self.MONTHLY_DURATION)
        return None

    # Additional helper methods
    @staticmethod
    def add_premium_roles_to_embed(ctx, embed, premium_roles):
        """Add premium roles to the provided embed."""
        for role_data in premium_roles:
            role_name = role_data.get("role_name", "Unknown Role")
            expiration_date = role_data.get("expiration_date")

            if expiration_date:
                formatted_date = discord.utils.format_dt(expiration_date, "D")
                relative_date = discord.utils.format_dt(expiration_date, "R")
                embed.add_field(
                    name=f"Rola premium: {role_name}",
                    value=f"Do: {formatted_date} ({relative_date})",
                    inline=False,
                )
            else:
                embed.add_field(
                    name=f"Rola premium: {role_name}",
                    value="Permanentna",
                    inline=False,
                )

    # IPremiumRoleManager stubs (these would integrate with existing methods)
    async def assign_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        duration_days: int,
        payment_amount: Optional[int] = None,
    ) -> ExtensionResult:
        """Assign a premium role to a member."""
        async with self.bot.get_db() as session:
            embed, refund, add_to_wallet = await self.assign_or_extend_premium_role(
                session, member, role_name, payment_amount or 0, duration_days, "manual"
            )
            await session.commit()

            success = embed.title == "Gratulacje!"
            return ExtensionResult(
                success=success,
                extension_type=ExtensionType.NORMAL,
                days_added=duration_days if success else 0,
                new_expiry=datetime.now(timezone.utc) + timedelta(days=duration_days) if success else None,
                message=embed.description,
            )

    async def extend_premium_role(
        self,
        member: discord.Member,
        role_name: str,
        additional_days: int,
        payment_amount: Optional[int] = None,
    ) -> ExtensionResult:
        """Extend an existing premium role."""
        return await self.assign_premium_role(member, role_name, additional_days, payment_amount)

    async def upgrade_premium_role(
        self, member: discord.Member, from_role: str, to_role: str, payment_amount: int
    ) -> ExtensionResult:
        """Upgrade from one premium role to another."""
        # For now, remove old role and assign new one
        if not self.guild:
            return ExtensionResult(
                success=False,
                extension_type=ExtensionType.UPGRADE,
                days_added=0,
                new_expiry=None,
                message="Guild nie jest ustawiony",
            )

        old_role = discord.utils.get(self.guild.roles, name=from_role)
        if old_role and old_role in member.roles:
            await member.remove_roles(old_role)

        return await self.assign_premium_role(member, to_role, self.MONTHLY_DURATION, payment_amount)

    async def remove_premium_role(self, member: discord.Member, role_name: str) -> bool:
        """Remove a premium role from a member."""
        try:
            if not self.guild:
                return False

            role = discord.utils.get(self.guild.roles, name=role_name)
            if role and role in member.roles:
                await member.remove_roles(role)
                async with self.bot.get_db() as session:
                    await RoleQueries.delete_member_role(session, member.id, role.id)
                    await session.commit()
                return True
            return False
        except Exception as e:
            self._log_error("remove_premium_role", e, member_id=member.id, role_name=role_name)
            return False

    async def get_premium_role_info(self, member: discord.Member) -> list[dict[str, Any]]:
        """Get premium role information for a member."""
        return await self.get_member_premium_roles(member.id)

    async def process_expired_premium_roles(self) -> list[dict[str, Any]]:
        """Process all expired premium roles."""
        # Implemented in process_premium_maintenance
        result = await self.process_premium_maintenance()
        return [{"processed": result.get("expired_roles_processed", 0)}]
