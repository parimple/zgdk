"""Main role shop view for purchasing premium roles."""
import logging
from typing import Dict, List, Optional

import discord
from discord.ext.commands import Context

from cogs.ui.shop_embeds import create_shop_embed
from core.interfaces.premium_interfaces import IPremiumService
from datasources.queries import MemberQueries
from utils.message_sender import MessageSender
from utils.premium_logic import PremiumRoleManager

from .constants import MONTHLY_DURATION, YEARLY_DURATION, YEARLY_MONTHS
from .role_description_view import RoleDescriptionView
from .role_purchase_handler import RolePurchaseHandler
from .role_shop_helpers import RoleShopPricing, RoleShopFormatting

logger = logging.getLogger(__name__)


class RoleShopView(discord.ui.View):
    """View for displaying and handling the purchase of roles in the shop."""

    def __init__(
        self,
        ctx: Context,
        bot,
        premium_roles=None,
        balance=0,
        page=1,
        viewer: discord.Member = None,
        member: discord.Member = None,
    ):
        super().__init__()
        self.ctx = ctx
        self.guild = bot.guild
        self.bot = bot
        self.balance = balance
        self.page = page
        self.viewer = viewer
        self.member = member
        self.premium_roles = premium_roles
        self.premium_manager = PremiumRoleManager(bot, self.guild)
        # Initialize MessageSender with bot instance for consistency
        self.message_sender = MessageSender(bot)
        
        # Initialize purchase handler
        self.purchase_handler = RolePurchaseHandler(bot, self.guild, self.premium_manager)

        # Create price maps
        self.base_price_map = {role["name"]: role["price"] for role in premium_roles}
        self.role_price_map = self.get_price_map()

        self.role_ids = {
            role["name"]: discord.utils.get(self.guild.roles, name=role["name"]).id
            for role in premium_roles
        }

        # Add role buttons
        for role_name, price in self.role_price_map.items():
            price = price * 10 if self.page == 2 else price
            button = discord.ui.Button(
                label=role_name,
                style=discord.ButtonStyle.primary,
                disabled=self.balance < price,
            )
            button.callback = self.create_button_callback(role_name)
            self.add_item(button)

        # Add navigation buttons
        if page == 1:
            next_button = discord.ui.Button(
                label="Pokaż ceny roczne ➡️", style=discord.ButtonStyle.secondary
            )
            next_button.callback = self.next_page
            self.add_item(next_button)
        else:
            previous_button = discord.ui.Button(
                label="⬅️ Pokaż ceny miesięczne", style=discord.ButtonStyle.secondary
            )
            previous_button.callback = self.previous_page
            self.add_item(previous_button)

        # Add action buttons
        description_button = discord.ui.Button(
            label="📋 Opis ról", style=discord.ButtonStyle.secondary
        )
        description_button.callback = self.show_role_description
        self.add_item(description_button)

        my_id_button = discord.ui.Button(
            label="🆔 Moje ID", style=discord.ButtonStyle.secondary
        )
        my_id_button.callback = self.show_my_id
        self.add_item(my_id_button)

        # Add donate button
        self.add_item(
            discord.ui.Button(
                label="Doładuj konto",
                style=discord.ButtonStyle.link,
                url=self.bot.config["donate_url"],
                emoji=bot.config.get("emojis", {}).get("mastercard", "💳"),
            )
        )

    async def create_view_for_user(
        self, interaction: discord.Interaction
    ) -> tuple[discord.Embed, "RoleShopView"]:
        """Create a new view instance for a different user."""
        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(
                session, interaction.user.id
            )
            balance = db_viewer.wallet_balance
            await session.commit()

            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_roles = await premium_service.get_member_premium_roles(
                interaction.user.id
            )

        new_view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            balance,
            self.page,
            viewer=interaction.user,
            member=interaction.user,
        )
        embed = await create_shop_embed(
            self.ctx,
            balance,
            new_view.role_price_map,
            premium_roles,
            self.page,
            viewer=interaction.user,
            member=interaction.user,
        )
        return embed, new_view

    def get_price_map(self) -> Dict[str, int]:
        """Get price map based on current page."""
        return RoleShopPricing.get_price_map(self.premium_roles, self.page)

    def _add_premium_text_to_description(self, description: str) -> str:
        """Add premium text formatting to role description."""
        return RoleShopFormatting.add_premium_text_to_description(description)

    def create_button_callback(self, role_name):
        """Create a callback function for a role button."""

        async def button_callback(interaction: discord.Interaction):
            # Check if the viewer is different
            if interaction.user.id != self.viewer.id:
                embed, view = await self.create_view_for_user(interaction)
                # Add premium text to the message
                base_text = self._add_premium_text_to_description(
                    "Oto twój własny widok sklepu:"
                )
                await interaction.response.send_message(
                    base_text, embed=embed, view=view, ephemeral=True
                )
                return

            # Handle the role purchase
            await self.purchase_handler.handle_buy_role(
                interaction,
                self.ctx,
                self.member,
                role_name,
                self.page,
                self.balance,
                self.premium_roles
            )

        return button_callback

    async def handle_buy_role(
        self,
        interaction: discord.Interaction,
        role_name: str,
        member: discord.Member,
        duration_days: int = 30,
        price: int = None,
    ) -> None:
        """Public method for handling role purchase from other views."""
        await self.purchase_handler.handle_buy_role(
            interaction,
            self.ctx,
            member,
            role_name,
            self.page,
            self.balance,
            self.premium_roles
        )

    async def next_page(self, interaction: discord.Interaction):
        """Go to the next page (yearly prices)."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description(
                "Oto twój własny widok sklepu:"
            )
            await interaction.response.send_message(
                base_text, embed=embed, view=view, ephemeral=True
            )
            return

        self.page = 2
        async with self.bot.get_db() as session:
            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_roles = await premium_service.get_member_premium_roles(self.member.id)

        view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            self.balance,
            self.page,
            self.viewer,
            self.member,
        )
        embed = await create_shop_embed(
            self.ctx,
            self.balance,
            view.role_price_map,
            premium_roles,
            self.page,
            viewer=self.viewer,
            member=self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to the previous page (monthly prices)."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description(
                "Oto twój własny widok sklepu:"
            )
            await interaction.response.send_message(
                base_text, embed=embed, view=view, ephemeral=True
            )
            return

        self.page = 1
        async with self.bot.get_db() as session:
            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_roles = await premium_service.get_member_premium_roles(self.member.id)

        view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            self.balance,
            self.page,
            self.viewer,
            self.member,
        )
        embed = await create_shop_embed(
            self.ctx,
            self.balance,
            view.role_price_map,
            premium_roles,
            self.page,
            viewer=self.viewer,
            member=self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_role_description(self, interaction: discord.Interaction):
        """Show role description view."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description(
                "Oto twój własny widok sklepu:"
            )
            await interaction.response.send_message(
                base_text, embed=embed, view=view, ephemeral=True
            )
            return

        view = RoleDescriptionView(
            self.ctx,
            self.bot,
            1,
            self.premium_roles,
            self.balance,
            self.viewer,
            self.member,
        )
        embed = await self.generate_embed(session=None)
        await interaction.response.edit_message(embed=embed, view=view)

    async def generate_embed(self, session):
        """Generate the role description embed."""
        from cogs.ui.shop_embeds import create_role_description_embed
        
        return await create_role_description_embed(
            self.ctx,
            1,
            self.premium_roles,
            self.balance,
            viewer=self.viewer,
            member=self.member,
        )

    async def show_my_id(self, interaction: discord.Interaction):
        """Show the user's Discord ID."""
        user_id = (
            interaction.user.id
            if interaction.user.id != self.viewer.id
            else self.viewer.id
        )
        await interaction.response.send_message(
            f"Twoje ID Discord: `{user_id}`", ephemeral=True
        )