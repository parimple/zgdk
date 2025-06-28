"""Embed builders for user profile commands."""

from datetime import datetime, timezone
from typing import Dict, List

import discord

from core.services.currency_service import CurrencyService

# Currency constant
CURRENCY_UNIT = CurrencyService.CURRENCY_UNIT


def create_profile_embed(
    member: discord.Member, profile_data: dict, active_mutes: List[str], is_voice_muted: bool
) -> discord.Embed:
    """Create profile embed with all member information."""
    import logging

    logger = logging.getLogger(__name__)

    logger.info(f"Creating profile embed for {member.display_name}")
    logger.info(f"Profile data keys: {list(profile_data.keys())}")

    # Create embed directly
    embed = discord.Embed(
        title=f"Profil użytkownika {member.display_name}",
        color=member.color if member.color.value != 0 else discord.Color.blue(),
        timestamp=datetime.now(timezone.utc),
    )

    embed.set_thumbnail(url=member.display_avatar.url)

    # Basic info
    embed.add_field(
        name="👤 Podstawowe informacje",
        value=f"ID: {member.id}\n"
        f"Dołączył: {member.joined_at.strftime('%Y-%m-%d') if member.joined_at else 'Nieznane'}",
        inline=False,
    )

    # Wallet balance
    embed.add_field(name="💰 Portfel", value=f"{profile_data['db_member'].wallet_balance}{CURRENCY_UNIT}", inline=True)

    # Invites
    embed.add_field(name="📨 Zaproszenia", value=str(profile_data["invites"]), inline=True)

    # Teams
    embed.add_field(name="👥 Teamy", value=str(profile_data["teams"]), inline=True)

    # Activity summary
    if profile_data["activity_summary"]:
        activity = profile_data["activity_summary"]
        embed.add_field(
            name="📊 Aktywność",
            value=f"Punkty: {activity.get('total_points', 0)}\n" f"Pozycja: #{activity.get('position', 'N/A')}",
            inline=False,
        )

    # Premium roles
    if profile_data["premium_roles"]:
        roles_text = []
        for role in profile_data["premium_roles"]:
            expiry = role["expiration"].strftime("%Y-%m-%d %H:%M") if role["expiration"] else "Nigdy"
            roles_text.append(f"{role['name']} (do: {expiry})")
        embed.add_field(name="⭐ Role Premium", value="\n".join(roles_text), inline=False)

    # Owned teams
    if profile_data["owned_teams"]:
        embed.add_field(name="👑 Własne teamy", value=", ".join(profile_data["owned_teams"]), inline=False)

    # Active mutes
    if active_mutes:
        embed.add_field(name="🔇 Aktywne kary", value="\n".join(active_mutes), inline=False)

    # Add additional fields if needed
    if profile_data.get("db_member") and profile_data["db_member"].voice_bypass_until:
        bypass_until = profile_data["db_member"].voice_bypass_until
        if bypass_until > datetime.now(timezone.utc):
            time_left = bypass_until - datetime.now(timezone.utc)
            hours_left = int(time_left.total_seconds() // 3600)
            embed.add_field(name="⏰ Bypass Głosowy", value=f"Aktywny przez {hours_left}h", inline=True)

    logger.info(f"Embed created with {len(embed.fields)} fields")
    return embed


def create_role_sale_embed(roles_data: List[Dict], refund_info: List[Dict]) -> discord.Embed:
    """Create embed for role sale interface."""
    embed = discord.Embed(
        title="💰 Sprzedaj Rolę Premium",
        description="Wybierz rolę, którą chcesz sprzedać. Otrzymasz zwrot proporcjonalny do pozostałego czasu.",
        color=discord.Color.gold(),
    )

    for info in refund_info:
        role_data = info["role_data"]
        embed.add_field(
            name=f"{role_data['role_name']}",
            value=f"Pozostało: {info['time_left']}\n" f"Zwrot: {info['refund']}{CURRENCY_UNIT}",
            inline=True,
        )

    return embed


def create_sale_confirmation_embed(role_name: str, refund: int, time_left: str) -> discord.Embed:
    """Create embed for sale confirmation."""
    embed = discord.Embed(
        title="⚠️ Potwierdź Sprzedaż",
        description=f"Czy na pewno chcesz sprzedać rolę **{role_name}**?",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Otrzymasz", value=f"{refund}{CURRENCY_UNIT}", inline=True)
    embed.add_field(name="Pozostały czas", value=time_left, inline=True)

    return embed


def create_sale_success_embed(role_name: str, refund: int) -> discord.Embed:
    """Create embed for successful role sale."""
    embed = discord.Embed(
        title="✅ Rola Sprzedana", description=f"Pomyślnie sprzedano rolę **{role_name}**", color=discord.Color.green()
    )
    embed.add_field(name="Otrzymano", value=f"{refund}{CURRENCY_UNIT}", inline=True)

    return embed
