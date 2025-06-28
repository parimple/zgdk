"""Role description view for displaying role details and purchase options."""
import discord
from discord.ext.commands import Context

from cogs.ui.shop_embeds import create_role_description_embed, create_shop_embed
from core.interfaces.premium_interfaces import IPremiumService
from datasources.queries import MemberQueries
from utils.message_sender import MessageSender


class RoleDescriptionView(discord.ui.View):
    """Role description view for displaying and handling role purchases."""

    def __init__(
        self,
        ctx: Context,
        bot,
        page=1,
        premium_roles=None,
        balance=0,
        viewer: discord.Member = None,
        member: discord.Member = None,
    ):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.page = page
        self.premium_roles = premium_roles or []
        self.balance = balance
        self.viewer = viewer
        self.member = member
        # Initialize MessageSender with bot instance for consistency
        self.message_sender = MessageSender(bot)

        # Add buttons
        previous_button = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary)
        previous_button.callback = self.previous_page
        self.add_item(previous_button)

        buy_button = discord.ui.Button(
            label="Kup rangę",
            style=discord.ButtonStyle.primary,
            disabled=premium_roles[page - 1]["price"] > balance,
            emoji=self.bot.config.get("emojis", {}).get("mastercard", "💳"),
        )
        buy_button.callback = self.buy_role
        self.add_item(buy_button)

        go_to_shop_button = discord.ui.Button(label="Do sklepu", style=discord.ButtonStyle.primary)
        go_to_shop_button.callback = self.go_to_shop
        self.add_item(go_to_shop_button)

        self.add_item(
            discord.ui.Button(
                label="Doładuj konto",
                style=discord.ButtonStyle.link,
                url=self.bot.config["donate_url"],
            )
        )

        next_button = discord.ui.Button(label="➡️", style=discord.ButtonStyle.secondary)
        next_button.callback = self.next_page
        self.add_item(next_button)

    def _add_premium_text_to_description(self, description: str) -> str:
        """Helper method to add premium text to description consistently."""
        _, premium_text = self.message_sender._get_premium_text(self.ctx)
        if premium_text:
            return f"{description}\n{premium_text}"
        return description

    async def create_view_for_user(
        self, interaction: discord.Interaction
    ) -> tuple[discord.Embed, "RoleDescriptionView"]:
        """Create a new view instance for a different user."""
        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, interaction.user.id)
            balance = db_viewer.wallet_balance
            await session.commit()

        new_view = RoleDescriptionView(
            self.ctx,
            self.bot,
            self.page,
            self.premium_roles,
            balance,
            viewer=interaction.user,
            member=interaction.user,
        )
        embed = await create_role_description_embed(
            self.ctx,
            self.page,
            self.premium_roles,
            balance,
            viewer=interaction.user,
            member=interaction.user,
        )
        return embed, new_view

    async def next_page(self, interaction: discord.Interaction):
        """Go to the next page in the role shop view."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok opisu ról:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        self.page = (self.page % len(self.premium_roles)) + 1
        embed = await create_role_description_embed(
            self.ctx,
            self.page,
            self.premium_roles,
            self.balance,
            self.viewer,
            self.member,
        )
        view = RoleDescriptionView(
            self.ctx,
            self.bot,
            self.page,
            self.premium_roles,
            self.balance,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to the previous page in the role description view."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok opisu ról:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        self.page = (self.page - 2) % len(self.premium_roles) + 1
        embed = await create_role_description_embed(
            self.ctx,
            self.page,
            self.premium_roles,
            self.balance,
            self.viewer,
            self.member,
        )
        view = RoleDescriptionView(
            self.ctx,
            self.bot,
            self.page,
            self.premium_roles,
            self.balance,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def buy_role(self, interaction: discord.Interaction):
        """Buy a role from description."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok opisu ról:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        role_name = self.premium_roles[self.page - 1]["name"]
        role_price = self.premium_roles[self.page - 1]["price"]

        # Import here to avoid circular imports
        from .role_shop_view import RoleShopView

        role_shop_view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            self.balance,
            self.page,
            self.viewer,
            self.member,
        )
        await role_shop_view.handle_buy_role(interaction, role_name, self.member, duration_days=30, price=role_price)

    async def go_to_shop(self, interaction: discord.Interaction):
        """Go to the role shop view."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            # Add premium text to the message
            base_text = self._add_premium_text_to_description("Oto twój własny widok opisu ról:")
            await interaction.response.send_message(base_text, embed=embed, view=view, ephemeral=True)
            return

        async with self.bot.get_db() as session:
            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_roles = await premium_service.get_member_premium_roles(self.member.id)

        # Import here to avoid circular imports
        from .role_shop_view import RoleShopView

        view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            self.balance,
            page=1,
            viewer=self.viewer,
            member=self.member,
        )
        embed = await create_shop_embed(
            self.ctx,
            self.balance,
            view.role_price_map,
            premium_roles,
            page=1,
            viewer=self.viewer,
            member=self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)
