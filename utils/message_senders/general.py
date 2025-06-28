"""General message senders for various purposes."""

from typing import Dict, List, Optional, Union

import discord
from discord.ext import commands

from .base import BaseMessageSender


class GeneralMessageSender(BaseMessageSender):
    """Handles general purpose messages."""

    async def send_giveaway_results(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        winners: List[discord.Member],
        prize: str,
        participants_count: int,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        """Send giveaway results."""
        if not winners:
            description = f"Nikt nie wygrał {prize} 😢"
            color = "warning"
        else:
            winner_mentions = ", ".join([w.mention for w in winners])
            description = f"🎊 Gratulacje {winner_mentions}!\nWygraliście: **{prize}**"
            color = "success"

        embed = self._create_embed(
            title="🎉 Wyniki Giveaway",
            description=description,
            color=color,
        )

        # Add statistics
        embed.add_field(
            name="📊 Statystyki",
            value=(
                f"• Liczba uczestników: **{participants_count}**\n"
                f"• Liczba zwycięzców: **{len(winners)}**\n"
                f"• Nagroda: **{prize}**"
            ),
            inline=False,
        )

        # Add timestamp
        embed.set_footer(text="Losowanie zakończone")

        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_command_on_cooldown(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        retry_after: float,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send command on cooldown message."""
        minutes = int(retry_after // 60)
        seconds = int(retry_after % 60)

        if minutes > 0:
            time_text = f"{minutes}m {seconds}s"
        else:
            time_text = f"{seconds}s"

        return await self.send_error(
            ctx=ctx,
            message=f"Ta komenda jest na cooldownie! Spróbuj ponownie za **{time_text}**.",
            title="⏱️ Cooldown",
            ephemeral=ephemeral,
        )

    async def send_invalid_argument(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        argument_name: str,
        expected_type: str,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send invalid argument message."""
        return await self.send_error(
            ctx=ctx,
            message=(f"Nieprawidłowy argument `{argument_name}`!\n" f"Oczekiwano: **{expected_type}**"),
            title="❌ Nieprawidłowy argument",
            ephemeral=ephemeral,
        )

    async def send_feature_disabled(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        feature_name: str,
        reason: str = None,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send feature disabled message."""
        description = f"Funkcja **{feature_name}** jest obecnie wyłączona."

        if reason:
            description += f"\n\n📝 Powód: {reason}"

        return await self.build_and_send_embed(
            ctx=ctx,
            title="🔒 Funkcja wyłączona",
            description=description,
            color="warning",
            ephemeral=ephemeral,
        )

    async def send_maintenance_mode(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        estimated_time: str = None,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send maintenance mode message."""
        description = "Bot jest obecnie w trybie konserwacji. Niektóre funkcje mogą być niedostępne."

        if estimated_time:
            description += f"\n\n⏰ Przewidywany czas: **{estimated_time}**"

        embed = self._create_embed(
            title="🔧 Tryb konserwacji",
            description=description,
            color="warning",
        )

        embed.add_field(
            name="💬 Kontakt",
            value="W razie pytań, skontaktuj się z administracją serwera.",
            inline=False,
        )

        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_confirmation(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        action: str,
        details: str = None,
        confirm_button_label: str = "Potwierdź",
        cancel_button_label: str = "Anuluj",
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send confirmation message with buttons."""
        description = f"Czy na pewno chcesz {action}?"

        if details:
            description += f"\n\n{details}"

        embed = self._create_embed(
            title="❓ Potwierdzenie",
            description=description,
            color="warning",
        )

        # Create view with confirm/cancel buttons
        from discord.ui import Button, View

        class ConfirmView(View):
            def __init__(self):
                super().__init__(timeout=60)
                self.value = None

            @discord.ui.button(label=confirm_button_label, style=discord.ButtonStyle.danger)
            async def confirm(self, interaction: discord.Interaction, button: Button):
                self.value = True
                self.stop()

            @discord.ui.button(label=cancel_button_label, style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction: discord.Interaction, button: Button):
                self.value = False
                self.stop()

        view = ConfirmView()

        return await self._send_embed(
            ctx=ctx,
            embed=embed,
            ephemeral=ephemeral,
            view=view,
        )

    async def send_list_embed(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        title: str,
        items: List[str],
        description: str = None,
        items_per_page: int = 10,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send a list in an embed with pagination if needed."""
        if not items:
            return await self.build_and_send_embed(
                ctx=ctx,
                title=title,
                description=description or "Lista jest pusta.",
                color="info",
                ephemeral=ephemeral,
            )

        # Calculate pagination
        total_pages = (len(items) + items_per_page - 1) // items_per_page
        current_page = 1

        # Get items for first page
        start_idx = (current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_items = items[start_idx:end_idx]

        embed = self._create_embed(
            title=title,
            description=description,
            color="info",
        )

        # Add items
        items_text = "\n".join(page_items)
        embed.add_field(
            name=f"Lista (Strona {current_page}/{total_pages})",
            value=items_text,
            inline=False,
        )

        if total_pages > 1:
            embed.set_footer(
                text=f"Strona {current_page}/{total_pages} • Pokazano {len(page_items)} z {len(items)} elementów"
            )

        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)
