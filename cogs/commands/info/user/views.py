"""Discord UI views for user info commands."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import discord
from discord.ext import commands

from core.interfaces.premium_interfaces import IPremiumService
from core.services.currency_service import CurrencyService
from datasources.queries import MemberQueries, RoleQueries
from utils.refund import calculate_refund

from ..admin.helpers import remove_premium_role_mod_permissions
from .embed_builders import create_role_sale_embed, create_sale_confirmation_embed, create_sale_success_embed

# Currency constant
CURRENCY_UNIT = CurrencyService.CURRENCY_UNIT

logger = logging.getLogger(__name__)


class ProfileView(discord.ui.View):
    """View for profile command."""

    def __init__(self, ctx, member, bot):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.member = member
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command author to interact."""
        return interaction.user == self.ctx.author


class BuyRoleButton(discord.ui.Button):
    """Button to open shop for buying roles."""

    def __init__(self):
        super().__init__(label="🛒 Kup Rolę", style=discord.ButtonStyle.primary, custom_id="buy_role")

    async def callback(self, interaction: discord.Interaction):
        """Open shop when clicked."""
        # Import here to avoid circular imports
        from cogs.commands.shop import ShopCog

        shop_cog = interaction.client.get_cog("ShopCog")
        if shop_cog:
            await interaction.response.defer()
            # Trigger shop command
            ctx = await interaction.client.get_context(interaction.message)
            ctx.author = interaction.user
            await shop_cog.shop(ctx)
        else:
            await interaction.response.send_message("❌ Sklep jest obecnie niedostępny.", ephemeral=True)


class SellRoleButton(discord.ui.Button):
    """Button to sell premium roles."""

    def __init__(self, bot):
        super().__init__(label="💰 Sprzedaj Rolę", style=discord.ButtonStyle.danger, custom_id="sell_role")
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        """Show sell role interface."""
        async with self.bot.get_db() as session:
            # Get user's premium roles
            premium_service = await self.bot.get_service(IPremiumService, session)
            if not premium_service:
                await interaction.response.send_message("❌ Usługa premium jest niedostępna.", ephemeral=True)
                return

            roles_data = await premium_service.get_member_premium_roles(interaction.user.id)

            if not roles_data:
                await interaction.response.send_message(
                    "❌ Nie posiadasz żadnych ról premium do sprzedania.", ephemeral=True
                )
                return

            # Calculate refunds
            refund_info = []
            for role_data in roles_data:
                if role_data["expiration_date"]:
                    # Get role price from config
                    role_price = 0
                    for premium_role in self.bot.config.get("premium_roles", []):
                        if premium_role["name"] == role_data["role_name"]:
                            role_price = premium_role["price"]
                            break

                    refund = calculate_refund(role_data["expiration_date"], role_price, role_data["role_name"])

                    time_left = role_data["expiration_date"] - datetime.now(timezone.utc)
                    days_left = time_left.days
                    hours_left = time_left.seconds // 3600

                    refund_info.append(
                        {"role_data": role_data, "refund": refund, "time_left": f"{days_left}d {hours_left}h"}
                    )

            # Create embed and view
            embed = create_role_sale_embed(roles_data, refund_info)
            view = ConfirmSaleView(interaction.user, refund_info, self.bot)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ConfirmSaleView(discord.ui.View):
    """View for confirming role sale."""

    def __init__(self, user: discord.User, refund_info: List[Dict], bot):
        super().__init__(timeout=60)
        self.user = user
        self.refund_info = refund_info
        self.bot = bot

        # Add dropdown if multiple roles
        if len(refund_info) > 1:
            self.add_item(RoleSelectDropdown(refund_info))
        else:
            # Single role - add confirm/cancel directly
            self.selected_role_id = refund_info[0]["role_data"]["role_id"]
            self.selected_info = refund_info[0]
            self.add_confirm_buttons()

    def add_confirm_buttons(self):
        """Add confirmation buttons."""
        confirm_btn = discord.ui.Button(
            label="✅ Potwierdź", style=discord.ButtonStyle.success, custom_id="confirm_sale"
        )
        confirm_btn.callback = self.confirm_sale

        cancel_btn = discord.ui.Button(label="❌ Anuluj", style=discord.ButtonStyle.danger, custom_id="cancel_sale")
        cancel_btn.callback = self.cancel_sale

        self.add_item(confirm_btn)
        self.add_item(cancel_btn)

    async def confirm_sale(self, interaction: discord.Interaction):
        """Process the sale."""
        if interaction.user != self.user:
            await interaction.response.send_message("To nie twoja transakcja!", ephemeral=True)
            return

        async with self.bot.get_db() as session:
            try:
                # Remove role from Discord
                role_name = self.selected_info["role_data"]["role_name"]
                discord_role = discord.utils.get(interaction.guild.roles, name=role_name)
                if discord_role and discord_role in interaction.user.roles:
                    await interaction.user.remove_roles(discord_role, reason="Sprzedaż roli premium")

                # Remove from database
                await RoleQueries.delete_member_role(session, interaction.user.id, self.selected_role_id)

                # Add refund to wallet
                await MemberQueries.add_to_wallet_balance(session, interaction.user.id, self.selected_info["refund"])

                # Remove premium permissions
                await remove_premium_role_mod_permissions(session, self.bot, interaction.user.id)

                await session.commit()

                # Send success message
                success_embed = create_sale_success_embed(role_name, self.selected_info["refund"])
                await interaction.response.edit_message(embed=success_embed, view=None)

                # Log the transaction
                logger.info(
                    f"User {interaction.user.id} sold premium role {role_name} for {self.selected_info['refund']}{CURRENCY_UNIT}"
                )

            except Exception as e:
                logger.error(f"Error selling premium role: {e}")
                await interaction.response.send_message("❌ Wystąpił błąd podczas sprzedaży roli.", ephemeral=True)

    async def cancel_sale(self, interaction: discord.Interaction):
        """Cancel the sale."""
        if interaction.user != self.user:
            await interaction.response.send_message("To nie twoja transakcja!", ephemeral=True)
            return

        await interaction.response.edit_message(
            embed=discord.Embed(
                title="❌ Anulowano", description="Sprzedaż roli została anulowana.", color=discord.Color.red()
            ),
            view=None,
        )

    async def on_timeout(self):
        """Disable all items on timeout."""
        for item in self.children:
            item.disabled = True


class RoleSelectDropdown(discord.ui.Select):
    """Dropdown for selecting role to sell."""

    def __init__(self, refund_info: List[Dict]):
        options = []
        for info in refund_info:
            role_data = info["role_data"]
            options.append(
                discord.SelectOption(
                    label=role_data["role_name"],
                    description=f"Zwrot: {info['refund']}{CURRENCY_UNIT} | Pozostało: {info['time_left']}",
                    value=str(role_data["role_id"]),
                )
            )

        super().__init__(placeholder="Wybierz rolę do sprzedania...", options=options, custom_id="role_select")
        self.refund_info = refund_info

    async def callback(self, interaction: discord.Interaction):
        """Handle role selection."""
        selected_role_id = int(self.values[0])

        # Find selected role info
        selected_info = None
        for info in self.refund_info:
            if info["role_data"]["role_id"] == selected_role_id:
                selected_info = info
                break

        if not selected_info:
            await interaction.response.send_message("❌ Błąd wyboru roli.", ephemeral=True)
            return

        # Update parent view
        self.view.selected_role_id = selected_role_id
        self.view.selected_info = selected_info

        # Create confirmation embed
        embed = create_sale_confirmation_embed(
            selected_info["role_data"]["role_name"], selected_info["refund"], selected_info["time_left"]
        )

        # Clear current items and add confirm buttons
        self.view.clear_items()
        self.view.add_confirm_buttons()

        await interaction.response.edit_message(embed=embed, view=self.view)
