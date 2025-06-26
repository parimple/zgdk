"""Permission management system for the bot."""
import logging
from enum import Enum, auto
from typing import List, Union

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class PermissionLevel(Enum):
    """Enum for permission levels."""

    OWNER = auto()  # Bot owner (ID from config)
    ADMIN = auto()  # Server admin (role from config)
    MOD = auto()  # Server mod (role from config)
    MOD_OR_ADMIN = auto()  # Either mod or admin role
    OWNER_OR_ADMIN = auto()  # Either owner or admin role
    PREMIUM = auto()  # Premium roles from config
    ALL = auto()  # All levels combined


def check_permission_level(bot, member: discord.Member, level: PermissionLevel) -> bool:
    """Check if a member has the required permission level."""
    if level == PermissionLevel.ALL:
        return True

    # Check bot owner (ID from config)
    if level == PermissionLevel.OWNER:
        # New owner_ids list support
        owner_ids = bot.config.get("owner_ids", [])
        is_in_owner_list = member.id in owner_ids
        
        # Backward compatibility with single owner_id
        is_main_owner = member.id == bot.config.get("owner_id")
        
        # Legacy test owner support
        test_owner_ids = bot.config.get("test_owner_ids", [])
        is_test_owner = member.id in test_owner_ids
        single_test_owner = bot.config.get("test_owner_id")
        is_legacy_test_owner = single_test_owner and member.id == single_test_owner
        
        # Debug logging
        logger.info(f"OWNER CHECK: user_id={member.id}")
        logger.info(f"  owner_ids list: {owner_ids}, in_list={is_in_owner_list}")
        logger.info(f"  main_owner: {is_main_owner}, test_owners: {is_test_owner}, legacy: {is_legacy_test_owner}")
        
        result = is_in_owner_list or is_main_owner or is_test_owner or is_legacy_test_owner
        logger.info(f"OWNER FINAL RESULT: {result}")
        return result

    # Check admin role (from config)
    has_admin = discord.utils.get(member.roles, id=bot.config["admin_roles"]["admin"])
    if level == PermissionLevel.ADMIN:
        return bool(has_admin)

    # Check mod role (from config)
    has_mod = discord.utils.get(member.roles, id=bot.config["admin_roles"]["mod"])
    if level == PermissionLevel.MOD:
        return bool(has_mod)

    # Check combined permissions
    if level == PermissionLevel.MOD_OR_ADMIN:
        return bool(has_mod or has_admin)

    if level == PermissionLevel.OWNER_OR_ADMIN:
        # Check owner permissions (including test owners)
        is_owner = check_permission_level(bot, member, PermissionLevel.OWNER)
        return is_owner or bool(has_admin)

    # Check premium roles (from config)
    if level == PermissionLevel.PREMIUM:
        for role_config in bot.config["premium_roles"]:
            if discord.utils.get(member.roles, name=role_config["name"]):
                return True
        return False

    return False


def has_permission_level(
    level: Union[PermissionLevel, List[PermissionLevel]], *, require_all: bool = False
):
    """
    Decorator to check if a user has the required permission level(s).

    Args:
        level: Single permission level or list of permission levels to check
        require_all: If True, user must have all permission levels. If False, any level is sufficient.
    """
    levels = [level] if isinstance(level, PermissionLevel) else level

    async def predicate(ctx):
        logger.info(f"PERMISSION PREDICATE: user_id={ctx.author.id}, levels={levels}, require_all={require_all}")
        if require_all:
            for permission_level in levels:
                result = check_permission_level(ctx.bot, ctx.author, permission_level)
                logger.info(f"PERMISSION CHECK: level={permission_level}, result={result}")
                if not result:
                    await ctx.send("Nie masz uprawnień do użycia tej komendy!")
                    return False
            return True
        else:
            for permission_level in levels:
                result = check_permission_level(ctx.bot, ctx.author, permission_level)
                logger.info(f"PERMISSION CHECK: level={permission_level}, result={result}")
                if result:
                    return True
            await ctx.send("Nie masz uprawnień do użycia tej komendy!")
            return False

    async def app_predicate(interaction: discord.Interaction):
        if require_all:
            for permission_level in levels:
                if not check_permission_level(
                    interaction.client, interaction.user, permission_level
                ):
                    await interaction.response.send_message(
                        "Nie masz uprawnień do użycia tej komendy!", ephemeral=True
                    )
                    return False
            return True
        else:
            for permission_level in levels:
                if check_permission_level(
                    interaction.client, interaction.user, permission_level
                ):
                    return True
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


def is_zagadka_owner():
    """Decorator to check if a user is the bot owner (ID from config)."""
    return has_permission_level(PermissionLevel.OWNER)


def is_admin():
    """Decorator to check if a user has the admin role (from config)."""
    return has_permission_level(PermissionLevel.ADMIN)


def is_mod():
    """Decorator to check if a user has the mod role (from config)."""
    return has_permission_level(PermissionLevel.MOD)


def is_mod_or_admin():
    """Decorator to check if a user has either mod or admin role (from config)."""
    return has_permission_level(PermissionLevel.MOD_OR_ADMIN)


def is_owner_or_admin():
    """Decorator to check if a user is either the owner (ID from config) or has admin role."""
    return has_permission_level(PermissionLevel.OWNER_OR_ADMIN)


def is_premium():
    """Decorator to check if a user has any premium role (from config)."""
    return has_permission_level(PermissionLevel.PREMIUM)


def requires_permissions(*levels: PermissionLevel, require_all: bool = False):
    """
    Decorator to check if a user has multiple permission levels.

    Args:
        *levels: Permission levels to check
        require_all: If True, user must have all permission levels. If False, any level is sufficient.
    """
    return has_permission_level(list(levels), require_all=require_all)
