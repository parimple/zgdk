"""Premium role management logic shared between shop and payment handlers."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import discord

from datasources.queries import RoleQueries

logger = logging.getLogger(__name__)

# Configuration constants
MONTHLY_DURATION = 30  # Base duration for monthly subscription
YEARLY_DURATION = 365  # Base duration for yearly subscription
BONUS_DAYS = 3  # Number of bonus days for monthly subscription
YEARLY_MONTHS = 10  # Number of months to pay for yearly subscription (2 months free)

# Okresy przedłużenia dla różnych poziomów ról przy wpłacie "zG50"
ZG50_EXTENSION = 30  # Standardowe przedłużenie dla zG50
ZG100_EXTENSION = 15  # Przedłużenie dla zG100 przy wpłacie 49/50
ZG500_EXTENSION = 3  # Przedłużenie dla zG500 przy wpłacie 49/50
ZG1000_EXTENSION = 1  # Przedłużenie dla zG1000 przy wpłacie 49/50

# Mapowanie kwot do dni przedłużenia dla poszczególnych ról premium
PARTIAL_EXTENSIONS = {}  # Will be initialized in PremiumRoleManager

# Mapowanie ścieżek upgrade'ów
UPGRADE_PATHS = {}  # Will be initialized in PremiumRoleManager

# Mapowanie starych kwot na nowe
LEGACY_AMOUNTS = {}  # Will be initialized in PremiumRoleManager

# Priorytety ról premium
PREMIUM_PRIORITY = {"zG50": 1, "zG100": 2, "zG500": 3, "zG1000": 4}


class PremiumRoleManager:
    """Manages premium role operations including purchases, extensions, and upgrades."""

    # Extension types
    class ExtensionType:
        """Typy przedłużeń roli."""

        NORMAL = "normal"  # Zwykłe przedłużenie
        PARTIAL = "partial"  # Partial extension (z mutem)
        UPGRADE = "upgrade"  # Upgrade do wyższej roli

    def __init__(self, bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.premium_roles = bot.config["premium_roles"]
        self.mute_roles = {role["name"]: role for role in bot.config["mute_roles"]}

        # Initialize mappings from config
        self.initialize_legacy_amounts()
        self.initialize_partial_extensions()
        self.initialize_upgrade_paths()

    def initialize_legacy_amounts(self):
        """Initialize LEGACY_AMOUNTS from config."""
        global LEGACY_AMOUNTS
        if self.bot.config.get("legacy_system", {}).get("enabled", False):
            LEGACY_AMOUNTS = self.bot.config["legacy_system"]["amounts"]
        else:
            LEGACY_AMOUNTS = {}

    def initialize_partial_extensions(self):
        """Initialize PARTIAL_EXTENSIONS based on config prices."""
        global PARTIAL_EXTENSIONS
        PARTIAL_EXTENSIONS = {}
        for role in self.premium_roles:
            role_name = role["name"]
            role_price = role["price"]
            PARTIAL_EXTENSIONS[role_name] = {}

            # Calculate days for each possible price point
            for price in [49, 50, 99, 100, 499, 500]:
                if price <= role_price:
                    days = int(price / role_price * MONTHLY_DURATION)
                    PARTIAL_EXTENSIONS[role_name][price] = days

            # Add exact price point
            PARTIAL_EXTENSIONS[role_name][role_price] = MONTHLY_DURATION

            logger.info(
                f"[PREMIUM] Initialized PARTIAL_EXTENSIONS for {role_name}:"
                f"\n - Role price: {role_price}"
                f"\n - Extensions: {PARTIAL_EXTENSIONS[role_name]}"
            )

    def initialize_upgrade_paths(self):
        """Initialize UPGRADE_PATHS based on config prices."""
        global UPGRADE_PATHS
        UPGRADE_PATHS = {}
        sorted_roles = sorted(self.premium_roles, key=lambda x: x["price"])

        for i in range(len(sorted_roles) - 1):
            current_role = sorted_roles[i]
            next_role = sorted_roles[i + 1]
            upgrade_cost = next_role["price"] - current_role["price"]
            UPGRADE_PATHS[current_role["name"]] = {next_role["name"]: upgrade_cost}

    def get_role_price(self, role_name: str) -> int:
        """Get the price for a given role."""
        for role in self.premium_roles:
            if role["name"] == role_name:
                return role["price"]
        return 0

    def has_mute_roles(self, member: discord.Member) -> bool:
        """Check if member has any mute roles."""
        return any(role for role in self.mute_roles.values() if role["id"] in [r.id for r in member.roles])

    async def remove_mute_roles(self, member: discord.Member):
        """Remove all mute roles from the member."""
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
        user_highest_priority = 0
        for role_name, priority in PREMIUM_PRIORITY.items():
            role_obj = discord.utils.get(self.guild.roles, name=role_name)
            if role_obj and role_obj in member.roles:
                user_highest_priority = max(user_highest_priority, priority)
        return user_highest_priority

    def get_user_highest_role_name(self, member: discord.Member) -> Optional[str]:
        """Get the name of highest premium role a member has."""
        highest_priority = 0
        highest_role_name = None

        for role_name, priority in PREMIUM_PRIORITY.items():
            role_obj = discord.utils.get(self.guild.roles, name=role_name)
            if role_obj and role_obj in member.roles and priority > highest_priority:
                highest_priority = priority
                highest_role_name = role_name

        return highest_role_name

    async def check_partial_extension(
        self,
        session,
        member: discord.Member,
        role_name: str,
        amount: int,
        current_role=None,
    ) -> Optional[Tuple[discord.Embed, int]]:
        """
        Check if a partial extension is possible.
        Returns (embed, days_to_add) if partial extension is possible, None otherwise.
        """
        if not self.has_mute_roles(member):
            return None

        # Get the role object
        role = discord.utils.get(self.guild.roles, name=role_name)
        if not role:
            return None

        # Check if amount matches partial extension rules
        if role_name not in PARTIAL_EXTENSIONS:
            return None

        # Check if role priority is not higher than user's highest role
        role_priority = PREMIUM_PRIORITY.get(role_name, 0)
        user_highest_priority = self.get_user_highest_role_priority(member)
        if role_priority > user_highest_priority:
            return None

        days_to_add = PARTIAL_EXTENSIONS[role_name].get(amount, 0)
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

    async def check_upgrade_possible(
        self, session, member: discord.Member, current_role, new_role_name: str
    ) -> Optional[Tuple[str, int]]:
        """
        Check if an upgrade is possible.
        Returns (upgrade_role_name, refund_amount) if upgrade is possible, None otherwise.
        """
        if not current_role:
            return None

        days_left = (current_role.expiration_date - datetime.now(timezone.utc)).days
        if not (MONTHLY_DURATION - 1 <= days_left <= MONTHLY_DURATION):
            return None

        # Get role name - always use Discord to avoid lazy loading issues
        role = member.guild.get_role(current_role.role_id)
        if not role:
            return None
        current_role_name = role.name
            
        if current_role_name in UPGRADE_PATHS:
            upgrade_info = UPGRADE_PATHS[current_role_name]
            if new_role_name in upgrade_info:
                return new_role_name, upgrade_info[new_role_name]

        return None

    async def get_extension_type(
        self,
        session,
        member: discord.Member,
        role_name: str,
        amount: int,
        current_role=None,
    ) -> Tuple[str, Optional[int], Optional[str]]:
        """
        Determine the type of extension/purchase.
        Returns (extension_type, days_to_add/upgrade_cost, new_role_name).
        """
        # Check for partial extension first
        partial_result = await self.check_partial_extension(session, member, role_name, amount, current_role)
        if partial_result:
            embed, days_to_add = partial_result
            return self.ExtensionType.PARTIAL, days_to_add, None

        # Check for possible upgrade
        if current_role:
            upgrade_result = await self.check_upgrade_possible(session, member, current_role, role_name)
            if upgrade_result:
                new_role_name, upgrade_cost = upgrade_result
                return self.ExtensionType.UPGRADE, upgrade_cost, new_role_name

        # Normal extension/purchase
        return self.ExtensionType.NORMAL, None, None

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
        Returns (embed, refund_amount, add_to_wallet) where:
        - refund_amount is None if no refund is needed
        - add_to_wallet is True if the amount should be added to wallet, False otherwise, None if default logic should be used
        """
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
        highest_role_priority = PREMIUM_PRIORITY.get(highest_role_name, 0) if highest_role_name else 0
        current_role_priority = PREMIUM_PRIORITY.get(role_name, 0)

        # Special case for payment == 49/50 - remove mute and extend role based on current highest role
        is_zg50_payment = role_name == "zG50" and amount in [49, 50]

        if is_zg50_payment and self.has_mute_roles(member):
            await self.remove_mute_roles(member)

            # If user already has a premium role, extend it based on their highest role
            if highest_role_name:
                role_to_extend = discord.utils.get(self.guild.roles, name=highest_role_name)
                if role_to_extend:
                    # Get the role database entry
                    _db_role = await RoleQueries.get_member_role(session, member.id, role_to_extend.id)

                    # Calculate days to extend based on highest role
                    if highest_role_name == "zG50":
                        days_to_add = ZG50_EXTENSION
                    elif highest_role_name == "zG100":
                        days_to_add = ZG100_EXTENSION
                    elif highest_role_name == "zG500":
                        days_to_add = ZG500_EXTENSION
                    elif highest_role_name == "zG1000":
                        days_to_add = ZG1000_EXTENSION
                    else:
                        days_to_add = ZG50_EXTENSION  # Default

                    # Update expiration date
                    updated_role = await RoleQueries.update_role_expiration_date(
                        session,
                        member.id,
                        role_to_extend.id,
                        timedelta(days=days_to_add),
                    )

                    if updated_role:
                        await session.flush()
                        embed = discord.Embed(
                            title="Gratulacje!",
                            description=f"Przedłużyłeś rolę {highest_role_name} o {days_to_add} dni i zdjęto ci muta!",
                            color=discord.Color.green(),
                        )
                        return embed, None, False  # Nie dodawaj do portfela

        # If user has a higher role than the one they're trying to buy, add to wallet instead
        if highest_role_priority > current_role_priority and source == "payment":
            logger.info(
                f"User {member.display_name} has higher role ({highest_role_name}) than {role_name}. "
                "Adding amount to wallet instead."
            )
            embed = discord.Embed(
                title="Doładowanie konta",
                description=f"Posiadasz już wyższą rolę ({highest_role_name}). "
                "Kwota została dodana do Twojego portfela.",
                color=discord.Color.blue(),
            )
            return embed, None, True  # Dodaj do portfela

        # Check extension type
        extension_type, extension_value, new_role_name = await self.get_extension_type(
            session, member, role_name, amount, current_role
        )

        if extension_type == self.ExtensionType.PARTIAL:
            days_to_add = extension_value
            updated_role = await RoleQueries.update_role_expiration_date(
                session, member.id, role.id, timedelta(days=days_to_add)
            )
            if updated_role:
                await session.flush()
                await self.remove_mute_roles(member)
                embed = discord.Embed(
                    title="Gratulacje!",
                    description=f"Przedłużyłeś rolę {role_name} o {days_to_add} dni i zdjęto ci muta!",
                    color=discord.Color.green(),
                )
                return embed, None, False
            else:
                raise ValueError(f"Failed to update role expiration for {role_name}")

        elif extension_type == self.ExtensionType.UPGRADE:
            _upgrade_cost = extension_value
            new_role = discord.utils.get(self.guild.roles, name=new_role_name)

            # Remove old role
            await member.remove_roles(role)
            await RoleQueries.delete_member_role(session, member.id, role.id)
            await session.flush()

            # Add new role
            await member.add_roles(new_role)
            await RoleQueries.add_role_to_member(session, member.id, new_role.id, timedelta(days=duration_days))
            await session.flush()

            embed = discord.Embed(
                title="Gratulacje!",
                description=f"Ulepszono twoją rolę z {role_name} na {new_role_name}!",
                color=discord.Color.green(),
            )
            return embed, None, None

        else:  # ExtensionType.NORMAL
            if current_role and role in member.roles:
                # Extend existing role
                extend_days = MONTHLY_DURATION if duration_days == MONTHLY_DURATION else YEARLY_DURATION
                logger.info(
                    f"[PREMIUM] Extending role {role_name} for {member.display_name}:"
                    f"\n - Current expiry: {current_role.expiration_date}"
                    f"\n - Days to add: {extend_days}"
                    f"\n - Duration type: {'monthly' if duration_days == MONTHLY_DURATION else 'yearly'}"
                )

                # Update expiration date
                updated_role = await RoleQueries.update_role_expiration_date(
                    session, member.id, role.id, timedelta(days=extend_days)
                )
                if updated_role:
                    await session.flush()
                    if duration_days == MONTHLY_DURATION:
                        description = f"Przedłużyłeś rolę {role_name} o {MONTHLY_DURATION} dni!"
                    else:
                        description = f"Przedłużyłeś rolę {role_name} o {YEARLY_DURATION} dni!"

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

    async def assign_temporary_roles(self, session, member: discord.Member, amount: int):
        """Assign temporary roles based on donation amount."""
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
            logger.info(
                f"[TEMP_ROLES] Checking tier: {amount_required} -> {role_name}, amount >= required: {amount >= amount_required}"
            )
            if amount >= amount_required:
                role = discord.utils.get(self.guild.roles, name=role_name)
                logger.info(f"[TEMP_ROLES] Looking for role {role_name}, found: {role is not None}")
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
                        logger.error(
                            f"[TEMP_ROLES] Error assigning/updating role {role_name} to {member.display_name}: {str(e)}"
                        )
                else:
                    logger.warning(f"[TEMP_ROLES] Role {role_name} not found on server")
