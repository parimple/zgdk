"""Helper functions for creating consistent shop embeds."""
from typing import Optional

import discord


class ShopEmbedColors:
    """Consistent colors for shop embeds."""

    INFO = discord.Color.blue()  # Informacje
    SUCCESS = discord.Color.green()  # Sukces
    WARNING = discord.Color.orange()  # Ostrzeżenie/wybór
    ERROR = discord.Color.red()  # Błąd
    PREMIUM = discord.Color.gold()  # Premium/specjalne


def create_upgrade_embed(
    current_role: str, new_role: str, price: int, refund: int, member_color: discord.Color = None
) -> discord.Embed:
    """Create embed for role upgrade."""
    actual_cost = max(0, price - refund)

    description = (
        f"📍 `Obecna:` {current_role}\n"
        f"✨ `Nowa:` {new_role}\n\n"
        f"💰 `Cena:` {price} {CURRENCY_UNIT}\n"
        f"💸 `Zwrot:` {refund} {CURRENCY_UNIT}\n"
        f"💳 `Do zapłaty:` {actual_cost} {CURRENCY_UNIT}"
    )

    embed = discord.Embed(
        title="⬆️ Ulepszenie rangi",
        description=description,
        color=member_color if member_color else ShopEmbedColors.INFO,
    )

    return embed


def create_downgrade_embed(
    current_role: str, new_role: str, price: int, days: int = 30, member_color: discord.Color = None
) -> discord.Embed:
    """Create embed for role downgrade choice."""
    duration_text = f"{days} dni" if days == 30 else f"{days} dni (1 rok)"

    description = (
        f"Masz rangę `{current_role}`, wybierasz `{new_role}`\n\n"
        f"💡 Opcje:\n"
        f"• Przedłuż obecną - dodaje {duration_text} do {current_role}\n"
        f"• Zmień rangę - wymaga sprzedaży obecnej"
    )

    embed = discord.Embed(
        title="⬇️ Niższa ranga",
        description=description,
        color=member_color if member_color else ShopEmbedColors.WARNING,
    )

    return embed


def create_extension_embed(role_name: str, days: int, member_color: discord.Color = None) -> discord.Embed:
    """Create embed for role extension."""
    duration_text = f"{days} dni" if days <= 31 else f"{days} dni (1 rok)"
    embed = discord.Embed(
        description=f"🔄 Ranga `{role_name}` przedłużona o `{duration_text}`",
        color=member_color if member_color else ShopEmbedColors.SUCCESS,
    )
    return embed


def create_purchase_embed(role_name: str, days: int, member_color: discord.Color = None) -> discord.Embed:
    """Create embed for new purchase."""
    embed = discord.Embed(
        description=f"✅ Ranga `{role_name}` aktywna przez `{days} dni`",
        color=member_color if member_color else ShopEmbedColors.SUCCESS,
    )
    return embed


def create_error_embed(message: str, member_color: discord.Color = None) -> discord.Embed:
    """Create error embed."""
    embed = discord.Embed(description=f"❌ {message}", color=member_color if member_color else ShopEmbedColors.ERROR)
    return embed


def create_cancel_embed(member_color: discord.Color = None) -> discord.Embed:
    """Create cancellation embed."""
    embed = discord.Embed(
        description="❌ Transakcja została anulowana", color=member_color if member_color else ShopEmbedColors.ERROR
    )
    return embed


# Currency unit from config
CURRENCY_UNIT = "G"
