"""Views for the shop cog."""
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext.commands import Context

from cogs.ui.shop_embeds import create_role_description_embed, create_shop_embed
from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries
from utils.currency import CURRENCY_UNIT
from utils.refund import calculate_refund

logger = logging.getLogger(__name__)


class PaymentsView(discord.ui.View):
    """View for navigating through payment history."""

    def __init__(self, ctx: Context, bot):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.current_offset = 0

    async def display_payments(self, interaction: discord.Interaction):
        """Display the payments."""
        self.current_offset = max(0, self.current_offset)
        async with self.bot.get_db() as session:
            payments = await HandledPaymentQueries.get_last_payments(
                session, offset=self.current_offset, limit=10
            )

        embed = discord.Embed(title="Wszystkie płatności")
        for payment in payments:
            name = f"ID płatności: {payment.id}"
            value = (
                f"ID członka: {payment.member_id}\n"
                f"Nazwa: {payment.name}\n"
                f"Kwota: {payment.amount}\n"
                f"Zapłacono: {discord.utils.format_dt(payment.paid_at, 'D')}\n"
                f"Typ płatności: {payment.payment_type}"
            )
            embed.add_field(name=name, value=value, inline=False)
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Nowsze", style=discord.ButtonStyle.primary)
    async def newer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to the newer payments."""
        self.current_offset -= 10
        await self.display_payments(interaction)

    @discord.ui.button(label="Starsze", style=discord.ButtonStyle.primary)
    async def older_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to the older payments."""
        self.current_offset += 10
        await self.display_payments(interaction)


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

        # Tworzenie podstawowej mapy cen
        self.base_price_map = {role["name"]: role["price"] for role in premium_roles}
        # Tworzenie mapy cen z uwzględnieniem strony (miesięczne/roczne)
        self.role_price_map = self.get_price_map()

        self.role_ids = {
            role["name"]: discord.utils.get(self.guild.roles, name=role["name"]).id
            for role in premium_roles
        }

        # Przyciski dla każdej roli
        for role_name, price in self.role_price_map.items():
            price = (
                price * 10 if self.page == 2 else price
            )  # Upewniamy się, że używamy właściwej ceny
            button = discord.ui.Button(
                label=role_name,
                style=discord.ButtonStyle.primary,
                disabled=self.balance < price,  # Porównujemy z właściwą ceną
            )
            button.callback = self.create_button_callback(role_name)
            self.add_item(button)

        # Przyciski nawigacji stron
        if page == 1:
            next_button = discord.ui.Button(
                label="Ceny roczne ➡️", style=discord.ButtonStyle.secondary
            )
            next_button.callback = self.next_page
            self.add_item(next_button)
        else:
            previous_button = discord.ui.Button(
                label="⬅️ Ceny miesięczne", style=discord.ButtonStyle.secondary
            )
            previous_button.callback = self.previous_page
            self.add_item(previous_button)

        # Przycisk opisu ról
        description_button = discord.ui.Button(label="Opis ról", style=discord.ButtonStyle.primary)
        description_button.callback = self.show_role_description
        self.add_item(description_button)

        donate_url = self.bot.config.get("donate_url")
        if donate_url:
            self.add_item(
                discord.ui.Button(
                    label="Doładuj konto",
                    style=discord.ButtonStyle.link,
                    url=donate_url,
                )
            )

        self.mute_roles = {role["name"]: role for role in self.bot.config["mute_roles"]}

    async def create_view_for_user(
        self, interaction: discord.Interaction
    ) -> tuple[discord.Embed, "RoleShopView"]:
        """Create a new view instance for a different user."""
        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, interaction.user.id)
            balance = db_viewer.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, interaction.user.id)
            await session.commit()

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

    def get_price_map(self):
        """Get price map based on current page."""
        price_map = {}
        for role_name, base_price in self.base_price_map.items():
            if self.page == 2:  # Ceny roczne (10 miesięcy)
                price_map[role_name] = base_price * 10
            else:  # Ceny miesięczne
                price_map[role_name] = base_price
        return price_map

    def create_button_callback(self, role_name):
        """Create a button callback for the specified role name."""

        async def button_callback(interaction: discord.Interaction):
            if interaction.user.id != self.viewer.id:
                embed, view = await self.create_view_for_user(interaction)
                await interaction.response.send_message(
                    "Oto twój własny widok sklepu:", embed=embed, view=view, ephemeral=True
                )
                return

            duration_days = 365 if self.page == 2 else 30
            price = self.role_price_map[role_name]
            await self.handle_buy_role(interaction, role_name, self.member, duration_days, price)

        return button_callback

    async def next_page(self, interaction: discord.Interaction):
        """Go to the next page in the role shop."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            await interaction.response.send_message(
                "Oto twój własny widok sklepu:", embed=embed, view=view, ephemeral=True
            )
            return

        self.page = 2
        self.role_price_map = self.get_price_map()

        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
            balance = db_member.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, self.member.id)
            await session.commit()

        view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            balance,
            self.page,
            self.viewer,
            self.member,
        )
        embed = await create_shop_embed(
            self.ctx,
            balance,
            view.role_price_map,
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to the previous page in the role shop."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            await interaction.response.send_message(
                "Oto twój własny widok sklepu:", embed=embed, view=view, ephemeral=True
            )
            return

        self.page = 1
        self.role_price_map = self.get_price_map()

        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
            balance = db_member.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, self.member.id)
            await session.commit()

        view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            balance,
            self.page,
            self.viewer,
            self.member,
        )
        embed = await create_shop_embed(
            self.ctx,
            balance,
            view.role_price_map,
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_role_description(self, interaction: discord.Interaction):
        """Show the description of the role."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            await interaction.response.send_message(
                "Oto twój własny widok sklepu:", embed=embed, view=view, ephemeral=True
            )
            return

        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
            balance = db_member.wallet_balance
            await session.commit()

        embed = await create_role_description_embed(
            self.ctx, self.page, self.premium_roles, balance, self.viewer, self.member
        )
        view = RoleDescriptionView(
            self.ctx,
            self.bot,
            self.page,
            self.premium_roles,
            balance,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def handle_buy_role(self, interaction, role_name, member, duration_days=30, price=None):
        role_id = self.role_ids[role_name]
        role = discord.utils.get(self.guild.roles, id=role_id)

        if price is None:
            base_price = next(
                r["price"] for r in self.bot.config["premium_roles"] if r["name"] == role_name
            )
            price = base_price * 10 if self.page == 2 else base_price

        if isinstance(member, discord.User):
            member = self.guild.get_member(member.id)
            if member is None:
                await interaction.response.send_message("Nie jesteś członkiem tego serwera.")
                return

        confirm_message = f"Czy potwierdzasz zakup roli {role_name} za {price}{CURRENCY_UNIT}?"

        confirm_view = ConfirmView()
        await interaction.response.send_message(confirm_message, ephemeral=True, view=confirm_view)
        await confirm_view.wait()

        if not confirm_view.value:
            await interaction.followup.send("Anulowano zakup.", ephemeral=True)
            return

        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, self.viewer.id)
            await MemberQueries.get_or_add_member(session, member.id)
            premium_roles = await RoleQueries.get_member_premium_roles(session, member.id)
            has_mute_roles = self.check_mute_roles(member)

            if premium_roles:
                await self.handle_existing_premium_roles(
                    interaction,
                    session,
                    member,
                    role,
                    price,
                    premium_roles,
                    duration_days,
                    has_mute_roles,
                )
            else:
                await self.purchase_role(interaction, session, member, role, price, duration_days)

            await session.commit()

        # Generate and update embed after the transaction is complete
        async with self.bot.get_db() as session:
            embed = await self.generate_embed(session)
        await interaction.message.edit(embed=embed)

    def check_mute_roles(self, member):
        """Check if member has mute roles."""
        return any(
            role for role in self.mute_roles.values() if role["id"] in [r.id for r in member.roles]
        )

    async def purchase_role(self, interaction, session, member, role, price, duration_days):
        """Purchase a role for a member"""
        try:
            # Sprawdź, czy rola już istnieje
            existing_role = await RoleQueries.get_member_role(session, member.id, role.id)

            if existing_role:
                # Jeśli rola istnieje, zaktualizuj datę wygaśnięcia
                await RoleQueries.update_role_expiration_date(
                    session, member.id, role.id, timedelta(days=duration_days)
                )
            else:
                # Jeśli rola nie istnieje, dodaj nową
                await RoleQueries.add_role_to_member(
                    session, member.id, role.id, timedelta(days=duration_days)
                )

            # Dodaj rolę na Discordzie
            await member.add_roles(role)

            # Odejmij cenę z portfela
            await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)

            await session.commit()

            expiry_date = datetime.now(timezone.utc) + timedelta(days=duration_days)
            await interaction.followup.send(
                f"Gratulacje! Zakupiłeś rolę {role.name} do {discord.utils.format_dt(expiry_date, 'R')}."
            )

        except Exception as e:
            logger.error(f"Error purchasing role: {str(e)}")
            await session.rollback()
            await interaction.followup.send("Wystąpił błąd podczas zakupu roli.")

    async def remove_mute_roles(self, member: discord.Member):
        """Remove all mute roles from the member and notify them."""
        roles_to_remove = [
            self.guild.get_role(role["id"])
            for role in self.mute_roles.values()
            if self.guild.get_role(role["id"]) in member.roles
        ]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            roles_removed = [role.name for role in roles_to_remove]
            message = f"Usunięto następujące role mutujące: {', '.join(roles_removed)}"
            await member.send(message)

    async def generate_embed(self, session):
        """Generate the embed for the role shop."""
        db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
        balance = db_member.wallet_balance
        premium_roles = await RoleQueries.get_member_premium_roles(session, self.member.id)
        return await create_shop_embed(
            self.ctx,
            balance,
            self.role_price_map,
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )

    async def handle_existing_premium_roles(
        self,
        interaction,
        session,
        member,
        role,
        price,
        premium_roles,
        duration_days,
        has_mute_roles,
    ):
        """
        Handle the process of buying or extending a premium role for a member who already has one.
        """
        last_member_role, last_role = premium_roles[0]
        last_role_price = self.role_price_map.get(last_role.name)

        if last_role_price is None:
            await interaction.followup.send("Nie można znaleźć ceny poprzedniej roli użytkownika.")
            return

        if price < last_role_price:
            if has_mute_roles:
                await self.remove_mute_roles(member)
                await interaction.followup.send("Usunięto mutujące role.")
                return
            else:
                await interaction.followup.send(
                    "Nie możesz kupić niższej rangi, jeśli nie masz nałożonych mutów."
                )
                return

        refund_amount = calculate_refund(last_member_role.expiration_date, last_role_price)
        msg_refund = (
            f" Część kwoty została zwrócona za poprzednią rangę ({refund_amount}{CURRENCY_UNIT})."
        )

        db_viewer = await MemberQueries.get_or_add_member(session, self.viewer.id)

        if db_viewer.wallet_balance < price:
            await interaction.followup.send("Nie masz wystarczająco dużo pieniędzy.")
            return

        if has_mute_roles:
            await self.remove_mute_roles(member)
            await interaction.followup.send("Usunięto mutujące role.")

        if last_role.id == role.id:
            extend_days = 31 if duration_days == 30 else 365
            await RoleQueries.update_role_expiration_date(
                session, member.id, role.id, timedelta(days=extend_days)
            )
            msg = f"Gratulacje! Przedłużyłeś rolę {role.name} o kolejne {extend_days} dni."
        else:
            await member.remove_roles(last_role)
            await RoleQueries.delete_member_role(session, member.id, last_role.id)
            await member.add_roles(role)
            await RoleQueries.add_role_to_member(
                session, member.id, role.id, timedelta(days=duration_days)
            )
            msg = f"Uaktualniono rolę {member.display_name} z {last_role.name} do {role.name} na {duration_days} dni.{msg_refund}"
            await MemberQueries.add_to_wallet_balance(session, member.id, refund_amount)

        await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)
        await interaction.followup.send(msg)

        embed = await self.generate_embed(session)
        await interaction.message.edit(embed=embed)


class BuyRoleButton(discord.ui.Button):
    """Button to buy a role."""

    def __init__(self, bot, member, role_name, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.member = member
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        ctx = await self.bot.get_context(interaction.message)
        ctx.author = self.member
        await ctx.invoke(self.bot.get_command("shop"), role_name=self.role_name)


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

        # Add buttons
        previous_button = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary)
        previous_button.callback = self.previous_page
        self.add_item(previous_button)

        buy_button = discord.ui.Button(
            label="Kup rangę",
            style=discord.ButtonStyle.primary,
            disabled=premium_roles[page - 1]["price"] > balance,
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
            await interaction.response.send_message(
                "Oto twój własny widok opisu ról:", embed=embed, view=view, ephemeral=True
            )
            return

        self.page = (self.page % len(self.premium_roles)) + 1
        embed = await create_role_description_embed(
            self.ctx, self.page, self.premium_roles, self.balance, self.viewer, self.member
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
            await interaction.response.send_message(
                "Oto twój własny widok opisu ról:", embed=embed, view=view, ephemeral=True
            )
            return

        self.page = (self.page - 2) % len(self.premium_roles) + 1
        embed = await create_role_description_embed(
            self.ctx, self.page, self.premium_roles, self.balance, self.viewer, self.member
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
            await interaction.response.send_message(
                "Oto twój własny widok opisu ról:", embed=embed, view=view, ephemeral=True
            )
            return

        role_name = self.premium_roles[self.page - 1]["name"]
        role_shop_view = RoleShopView(
            self.ctx,
            self.bot,
            self.premium_roles,
            self.balance,
            self.page,
            self.viewer,
            self.member,
        )
        await role_shop_view.handle_buy_role(interaction, role_name, self.member, duration_days=30)

    async def go_to_shop(self, interaction: discord.Interaction):
        """Go to the role shop view."""
        if interaction.user.id != self.viewer.id:
            embed, view = await self.create_view_for_user(interaction)
            await interaction.response.send_message(
                "Oto twój własny widok opisu ról:", embed=embed, view=view, ephemeral=True
            )
            return

        async with self.bot.get_db() as session:
            premium_roles = await RoleQueries.get_member_premium_roles(session, self.member.id)

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


class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60.0)  # 60 seconds timeout
        self.value = None

    @discord.ui.button(label="Potwierdź", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.send_message("Potwierdzono zakup.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Anuluj", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.send_message("Anulowano zakup.", ephemeral=True)
        self.stop()

    async def on_timeout(self):
        self.value = False
        self.stop()
