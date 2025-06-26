"""Permission service for managing user permissions and role checks."""

import logging
from typing import List, Union

import discord
from discord.ext import commands

from core.interfaces.permission_interfaces import IPermissionService, PermissionLevel
from core.services.base_service import BaseService


class PermissionService(BaseService, IPermissionService):
    """Service for checking user permissions and role-based access control."""

    def __init__(self, bot=None, **kwargs):
        # Permission service doesn't need unit_of_work for its operations
        super().__init__(unit_of_work=None, **kwargs)
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate permission checking operation."""
        return self.bot is not None and hasattr(self.bot, "config")

    def check_permission_level(
        self, member: discord.Member, level: PermissionLevel
    ) -> bool:
        """Check if a member has the required permission level."""
        if not self.bot or not hasattr(self.bot, "config"):
            self._log_error(
                "check_permission_level",
                ValueError("Bot or config not available"),
                level=level.name,
                member_id=member.id,
            )
            return False

        try:
            if level == PermissionLevel.ALL:
                return True

            # Check bot owner (ID from config)
            if level == PermissionLevel.OWNER:
                return member.id == self.bot.config["owner_id"]

            # Check admin role (from config)
            has_admin = discord.utils.get(
                member.roles, id=self.bot.config["admin_roles"]["admin"]
            )
            if level == PermissionLevel.ADMIN:
                return bool(has_admin)

            # Check mod role (from config)
            has_mod = discord.utils.get(
                member.roles, id=self.bot.config["admin_roles"]["mod"]
            )
            if level == PermissionLevel.MOD:
                return bool(has_mod)

            # Check combined permissions
            if level == PermissionLevel.MOD_OR_ADMIN:
                return bool(has_mod or has_admin)

            if level == PermissionLevel.OWNER_OR_ADMIN:
                return member.id == self.bot.config["owner_id"] or bool(has_admin)

            # Check premium roles (from config)
            if level == PermissionLevel.PREMIUM:
                for role_config in self.bot.config.get("premium_roles", []):
                    if discord.utils.get(member.roles, name=role_config["name"]):
                        return True
                return False

            return False

        except Exception as e:
            self._log_error(
                "check_permission_level",
                e,
                level=level.name,
                member_id=member.id,
            )
            return False

    def is_owner(self, member: discord.Member) -> bool:
        """Check if member is the bot owner."""
        return self.check_permission_level(member, PermissionLevel.OWNER)

    def is_admin(self, member: discord.Member) -> bool:
        """Check if member has admin role."""
        return self.check_permission_level(member, PermissionLevel.ADMIN)

    def is_mod(self, member: discord.Member) -> bool:
        """Check if member has mod role."""
        return self.check_permission_level(member, PermissionLevel.MOD)

    def is_mod_or_admin(self, member: discord.Member) -> bool:
        """Check if member has mod or admin role."""
        return self.check_permission_level(member, PermissionLevel.MOD_OR_ADMIN)

    def is_owner_or_admin(self, member: discord.Member) -> bool:
        """Check if member is owner or has admin role."""
        return self.check_permission_level(member, PermissionLevel.OWNER_OR_ADMIN)

    def is_premium(self, member: discord.Member) -> bool:
        """Check if member has any premium role."""
        return self.check_permission_level(member, PermissionLevel.PREMIUM)

    def has_permission_levels(
        self,
        member: discord.Member,
        levels: Union[PermissionLevel, List[PermissionLevel]],
        require_all: bool = False,
    ) -> bool:
        """Check if member has required permission level(s)."""
        if isinstance(levels, PermissionLevel):
            levels = [levels]

        try:
            if require_all:
                return all(
                    self.check_permission_level(member, level) for level in levels
                )
            else:
                return any(
                    self.check_permission_level(member, level) for level in levels
                )
        except Exception as e:
            self._log_error(
                "has_permission_levels",
                e,
                member_id=member.id,
                levels=[level.name for level in levels],
                require_all=require_all,
            )
            return False

    def create_permission_check(
        self,
        level: Union[PermissionLevel, List[PermissionLevel]],
        require_all: bool = False,
    ):
        """Create a permission check decorator for commands."""
        levels = [level] if isinstance(level, PermissionLevel) else level

        async def predicate(ctx):
            if self.has_permission_levels(ctx.author, levels, require_all=require_all):
                return True
            else:
                await ctx.send("Nie masz uprawnień do użycia tej komendy!")
                return False

        async def app_predicate(interaction: discord.Interaction):
            if self.has_permission_levels(
                interaction.user, levels, require_all=require_all
            ):
                return True
            else:
                await interaction.response.send_message(
                    "Nie masz uprawnień do użycia tej komendy!", ephemeral=True
                )
                return False

        def decorator(func):
            if isinstance(func, commands.Command):
                func.checks.append(predicate)
            else:
                func.__commands_checks__ = [
                    *getattr(func, "__commands_checks__", []),
                    predicate,
                ]
                func.__app_commands_checks__ = [
                    *getattr(func, "__app_commands_checks__", []),
                    app_predicate,
                ]
            return func

        return decorator

    # Convenience methods that match the original utility function names
    def is_zagadka_owner(self):
        """Decorator to check if a user is the bot owner (ID from config)."""
        return self.create_permission_check(PermissionLevel.OWNER)

    def requires_admin(self):
        """Decorator to check if a user has the admin role (from config)."""
        return self.create_permission_check(PermissionLevel.ADMIN)

    def requires_mod(self):
        """Decorator to check if a user has the mod role (from config)."""
        return self.create_permission_check(PermissionLevel.MOD)

    def requires_mod_or_admin(self):
        """Decorator to check if a user has either mod or admin role (from config)."""
        return self.create_permission_check(PermissionLevel.MOD_OR_ADMIN)

    def requires_owner_or_admin(self):
        """Decorator to check if a user is either the owner (ID from config) or has admin role."""
        return self.create_permission_check(PermissionLevel.OWNER_OR_ADMIN)

    def requires_premium(self):
        """Decorator to check if a user has any premium role (from config)."""
        return self.create_permission_check(PermissionLevel.PREMIUM)

    def requires_permissions(
        self, *levels: PermissionLevel, require_all: bool = False
    ):
        """
        Decorator to check if a user has multiple permission levels.

        Args:
            *levels: Permission levels to check
            require_all: If True, user must have all permission levels. If False, any level is sufficient.
        """
        return self.create_permission_check(list(levels), require_all=require_all)