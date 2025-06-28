"""Premium related message senders."""

from typing import Optional, Union

import discord
from discord.ext import commands

from .base import BaseMessageSender


class PremiumMessageSender(BaseMessageSender):
    """Handles premium related messages."""

    async def send_premium_required(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        feature: str = None,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send premium required message."""
        if feature:
            description = f"Ta funkcja **{feature}** wymaga roli premium!"
        else:
            description = "Ta funkcja wymaga roli premium!"
        
        embed = self._create_embed(
            title="💎 Premium wymagane",
            description=description,
            color="warning",
        )
        
        # Add premium benefits
        embed.add_field(
            name="🎁 Korzyści z Premium",
            value=(
                "• Brak limitów na kanałach głosowych\n"
                "• Więcej moderatorów i autokick\n"
                "• Dostęp do ekskluzywnych funkcji\n"
                "• Wsparcie rozwoju bota\n"
                "• Priorytetowe wsparcie"
            ),
            inline=False,
        )
        
        # Add how to get premium
        embed.add_field(
            name="🛒 Jak zdobyć Premium?",
            value=(
                "Użyj komendy </premium shop:1315400801102909451> "
                "aby zobaczyć dostępne pakiety premium!"
            ),
            inline=False,
        )
        
        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_no_premium_role(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send no premium role message."""
        embed = self._create_embed(
            title="💎 Brak roli premium",
            description="Nie posiadasz żadnej roli premium!",
            color="error",
        )
        
        embed.add_field(
            name="🛒 Kup Premium",
            value=(
                "Użyj komendy </premium shop:1315400801102909451> "
                "aby kupić rolę premium i odblokować wszystkie funkcje!"
            ),
            inline=False,
        )
        
        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_tier_t_bypass_required(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        required_hours: int,
        current_hours: int = 0,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send tier T bypass required message."""
        missing_hours = required_hours - current_hours
        
        embed = self._create_embed(
            title="⏱️ Wymagany czas bypass",
            description=(
                f"Ta funkcja wymaga **{required_hours}T** czasu bypass.\n"
                f"Obecnie masz: **{current_hours}T**\n"
                f"Brakuje Ci: **{missing_hours}T**"
            ),
            color="warning",
        )
        
        # Add how to get T
        embed.add_field(
            name="💰 Jak zdobyć T?",
            value=(
                "• Podbijaj serwer komendą `/bump`\n"
                "• Głosuj na serwer na stronach głosowania\n"
                "• Bądź aktywny na kanałach głosowych\n"
                "• Pisz wiadomości na czacie"
            ),
            inline=False,
        )
        
        # Add premium info
        embed.add_field(
            name="💎 Premium = Brak limitów",
            value=(
                "Z rolą premium nie musisz martwić się o czas bypass!\n"
                "Użyj </premium shop:1315400801102909451> aby kupić premium."
            ),
            inline=False,
        )
        
        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_bypass_expired(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send bypass expired message."""
        embed = self._create_embed(
            title="⏱️ Czas bypass wygasł",
            description=(
                "Twój czas bypass wygasł!\n"
                "Musisz zdobyć więcej T, aby korzystać z tej funkcji."
            ),
            color="error",
        )
        
        # Add quick actions
        embed.add_field(
            name="🚀 Szybkie akcje",
            value=(
                "• `/bump` - sprawdź dostępne bumpy\n"
                "• `/voice info` - zobacz ile T masz\n"
                "• `/premium shop` - kup premium"
            ),
            inline=False,
        )
        
        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_specific_roles_required(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        required_roles: list,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send specific roles required message."""
        roles_text = ", ".join([f"`{role}`" for role in required_roles])
        
        embed = self._create_embed(
            title="🎭 Wymagane role",
            description=f"Ta funkcja wymaga jednej z następujących ról: {roles_text}",
            color="warning",
        )
        
        # Check if these are premium roles
        if any("premium" in role.lower() for role in required_roles):
            embed.add_field(
                name="💎 To są role premium!",
                value=(
                    "Użyj </premium shop:1315400801102909451> "
                    "aby kupić jedną z tych ról."
                ),
                inline=False,
            )
        
        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)