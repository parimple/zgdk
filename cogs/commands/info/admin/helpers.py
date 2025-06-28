"""Helper functions and classes for admin info commands."""

import logging
from datetime import datetime
from typing import Optional

import discord
from sqlalchemy import select

from core.interfaces.team_interfaces import ITeamManagementService
from datasources.models import Role
from datasources.queries import ChannelPermissionQueries, RoleQueries

logger = logging.getLogger(__name__)


async def remove_premium_role_mod_permissions(session, bot, member_id: int):
    """
    Remove moderator permissions granted by a user and delete their teams.

    This function is called both when a premium role is manually sold and
    when a premium role automatically expires.

    :param session: Database session
    :param bot: Bot instance
    :param member_id: User ID
    """
    logger.info(f"Removing premium role-related privileges for user {member_id}")

    # 1. Usuń uprawnienia moderatorów kanałów głosowych
    await ChannelPermissionQueries.remove_mod_permissions_granted_by_member(session, member_id)
    logger.info(f"Voice channel permissions granted by {member_id} removed")

    # 2. Usuń teamy należące do tego użytkownika - używamy bezpieczniejszej metody SQL
    team_service = await bot.get_service(ITeamManagementService, session)
    deleted_teams = 0
    if team_service:
        deleted_teams = await team_service.delete_user_teams_by_sql(session, member_id)
    if deleted_teams > 0:
        logger.info(f"Deleted {deleted_teams} teams owned by {member_id} using SQL method")

    return deleted_teams


class InviteInfo:
    """Helper class for invite information."""

    def __init__(self, invite_data, creator=None):
        self.code = invite_data.get("code", "Unknown")
        self.uses = invite_data.get("uses", 0)
        self.created_at = invite_data.get("created_at", datetime.now())
        self.last_used_at = invite_data.get("last_used_at")
        self.creator = creator
        self.creator_id = invite_data.get("creator_id")


async def get_member_premium_roles_info(session, guild: discord.Guild, member: discord.Member):
    """Get detailed information about member's premium roles."""
    premium_roles = []
    role_names = ["zG50", "zG100", "zG500", "zG1000"]

    for role_name in role_names:
        role = discord.utils.get(guild.roles, name=role_name)
        if role and role in member.roles:
            # Sprawdź w bazie
            db_role = await session.execute(select(Role).where(Role.name == role_name))
            db_role = db_role.scalar_one_or_none()

            if db_role:
                member_role = await RoleQueries.get_member_role(session, member.id, db_role.id)
                if member_role:
                    expiry = (
                        member_role.expiration_date.strftime("%Y-%m-%d %H:%M")
                        if member_role.expiration_date
                        else "Nigdy"
                    )
                    premium_roles.append(f"{role_name} (do: {expiry})")
                else:
                    premium_roles.append(f"{role_name} (brak w bazie!)")
            else:
                premium_roles.append(f"{role_name} (rola nieznana w bazie)")

    return premium_roles


async def get_member_teams_info(bot, guild: discord.Guild, member: discord.Member):
    """Get information about member's teams."""
    owned_teams = []
    member_teams = []
    team_symbol = bot.config.get("team", {}).get("symbol", "☫")

    for role in guild.roles:
        if role.name.startswith(team_symbol):
            # Sprawdź czy użytkownik jest właścicielem (ma manage_roles)
            if role.permissions.manage_roles:
                # Sprawdź członków roli
                members_with_manage = [m for m in role.members if m.guild_permissions.manage_roles]
                if member in members_with_manage:
                    team_members = len(role.members)
                    owned_teams.append(f"{role.name} ({team_members} członków)")
            else:
                # Sprawdź czy jest członkiem
                if member in role.members:
                    # Sprawdź czy to nie jego własny team
                    is_owner = any(m == member and m.guild_permissions.manage_roles for m in role.members)
                    if not is_owner:
                        member_teams.append(role.name)

    return owned_teams, member_teams


async def get_member_voice_permissions_info(session, guild: discord.Guild, member: discord.Member):
    """Get information about member's voice channel permissions."""
    voice_permissions = await ChannelPermissionQueries.get_member_mod_permissions(session, member.id)

    channels = []
    if voice_permissions:
        for perm in voice_permissions:
            channel = guild.get_channel(perm.channel_id)
            if channel:
                granter = guild.get_member(perm.granted_by_member_id)
                granter_name = granter.display_name if granter else "Nieznany"
                channels.append(f"{channel.name} (od: {granter_name})")

    return channels


def get_member_active_mutes(guild: discord.Guild, member: discord.Member):
    """Get member's active mutes."""
    active_mutes = []
    mute_roles = ["mutedimg", "mutedtxt", "mutednick", "mutedlive"]

    for role_name in mute_roles:
        role = discord.utils.get(guild.roles, name=role_name)
        if role and role in member.roles:
            active_mutes.append(role_name)

    return active_mutes
