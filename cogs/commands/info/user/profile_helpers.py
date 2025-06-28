"""Helper functions for user profile commands."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple

import discord
from discord.ext import commands

from datasources.queries import MemberQueries
from core.repositories import InviteRepository
from core.interfaces.member_interfaces import IActivityService, IMemberService
from core.interfaces.premium_interfaces import IPremiumService
from core.interfaces.team_interfaces import ITeamManagementService
from core.services.team_management_service import TeamManagementService

logger = logging.getLogger(__name__)


async def get_profile_data(
    member: discord.Member, 
    session, 
    ctx: commands.Context,
    bot,
    team_symbol: str
) -> dict:
    """Get all necessary data for member profile."""
    # Get member data from database
    db_member = await MemberQueries.get_or_add_member(
        session, member.id, wallet_balance=0, joined_at=member.joined_at
    )
    
    # Get services
    member_service = await bot.get_service(IMemberService, session)
    activity_service = await bot.get_service(IActivityService, session)
    premium_service = await bot.get_service(IPremiumService, session)
    
    # Get basic data
    invite_repo = InviteRepository(session)
    invites = await invite_repo.get_member_invite_count(member.id)
    teams = TeamManagementService.count_member_teams(ctx.guild, member, team_symbol)
    
    # Get activity data
    activity_summary = None
    if activity_service:
        activity_summary = await activity_service.get_member_activity_summary(member.id)
    
    # Get premium roles
    premium_roles = []
    if premium_service:
        roles_data = await premium_service.get_member_premium_roles(member.id)
        for role_data in roles_data:
            premium_roles.append({
                'name': role_data['role_name'],
                'expiration': role_data['expiration_date']
            })
    
    return {
        'db_member': db_member,
        'invites': invites,
        'teams': teams,
        'activity_summary': activity_summary,
        'premium_roles': premium_roles,
        'owned_teams': TeamManagementService.get_owned_teams(ctx.guild, member, team_symbol),
        'voice_mods': []  # TODO: Fix when ChannelPermissionQueries has proper method
    }


async def get_active_mutes(member: discord.Member, ctx: commands.Context) -> Tuple[List[str], bool]:
    """Get active mute roles for a member."""
    mute_roles = {
        "mutedimg": "🖼️ Wyciszenie obrazków",
        "mutedtxt": "💬 Wyciszenie tekstu", 
        "mutednick": "📝 Blokada zmiany nicku",
        "mutedlive": "🎥 Blokada transmisji",
        "mutedvc": "🔇 Wyciszenie głosowe",
    }
    
    active_mutes = []
    is_voice_muted = False
    
    for role_name, description in mute_roles.items():
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role and role in member.roles:
            active_mutes.append(description)
            if role_name == "mutedvc":
                is_voice_muted = True
    
    return active_mutes, is_voice_muted