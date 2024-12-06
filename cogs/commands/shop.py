"""Shop cog for the Zagadka bot."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands

from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries
from main import Zagadka
from utils.currency import CURRENCY_UNIT
from utils.premium import PaymentData, PremiumManager
from utils.refund import calculate_refund

logger = logging.getLogger(__name__)


class ShopCog(commands.Cog):
    """Shop cog for managing the purchase and assignment of roles."""

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="shop", description="Wyświetla sklep z rolami.")
    @commands.has_permissions(administrator=True)
    async def shop(self, ctx: commands.Context):
        viewer = ctx.author

        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, viewer.id)
            balance = db_viewer.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, viewer.id)
            await session.commit()

        view = RoleShopView(
            ctx,
            self.bot,
            self.bot.config["premium_roles"],
            balance,
            page=1,
            viewer=viewer,
            member=viewer,
        )
        embed = await create_shop_embed(
            ctx,
            balance,
            view.role_price_map,
            premium_roles,
            page=1,
            viewer=viewer,
            member=viewer,
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="add", description="Dodaje środki do portfela użytkownika.")
    @commands.has_permissions(administrator=True)
    async def add_balance(self, ctx: commands.Context, user: discord.User, amount: int):
        """Add balance to a user's wallet."""
        payment_data = PaymentData(
            name=ctx.author.display_name,
            amount=amount,
            paid_at=datetime.now(timezone.utc),
            payment_type="command",
        )

        async with self.bot.get_db() as session:
            await HandledPaymentQueries.add_payment(
                session,
                user.id,
                payment_data.name,
                payment_data.amount,
                payment_data.paid_at,
                payment_data.payment_type,
            )
            await MemberQueries.get_or_add_member(session, user.id)
            await MemberQueries.add_to_wallet_balance(session, user.id, payment_data.amount)
            await session.commit()

        await ctx.reply(f"Dodano {amount} do portfela {user.mention}.")

    @commands.command(name="assign_payment")
    @commands.has_permissions(administrator=True)
    async def assign_payment(self, ctx: commands.Context, payment_id: int, user: discord.Member):
        """Assign a payment ID to a user."""
        async with self.bot.get_db() as session:
            payment = await HandledPaymentQueries.get_payment_by_id(session, payment_id)

            if payment:
                payment.member_id = user.id
                await MemberQueries.add_to_wallet_balance(session, user.id, payment.amount)
                await session.commit()

                msg1 = (
                    "Proszę pamiętać o podawaniu swojego ID "
                    "podczas dokonywania wpłat w przyszłości. Twoje ID to:"
                )
                msg2 = (
                    f"Nie mogłem wysłać DM do {user.mention}. "
                    f"Proszę przekazać mu te informacje ręcznie."
                )

                try:
                    await user.send(msg1)
                    await user.send(f"```{user.id}```")
                except discord.Forbidden:
                    await ctx.send(msg2)
            else:
                await ctx.send(f"Nie znaleziono płatności o ID: {payment_id}")

    @commands.hybrid_command(name="payments", description="Wyświetla wszystkie płatności")
    @commands.has_permissions(administrator=True)
    async def all_payments(self, ctx: commands.Context):
        """Fetch and display the initial set of payments."""
        async with self.bot.get_db() as session:
            payments = await HandledPaymentQueries.get_last_payments(session, limit=10)

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

        view = PaymentsView(ctx, self.bot)
        await ctx.send(embed=embed, view=view)

    @commands.command(
        name="set_role_expiry", description="Ustawia czas wygaśnięcia roli (tylko dla testów)."
    )
    @commands.has_permissions(administrator=True)
    async def set_role_expiry(self, ctx: commands.Context, member: discord.Member, hours: int):
        """
        Ustawia czas wygaśnięcia roli dla użytkownika.

        Args:
            ctx: Kontekst komendy
            member: Użytkownik, którego rola ma być zmodyfikowana
            hours: Liczba godzin do wygaśnięcia roli
        """
        async with self.bot.get_db() as session:
            premium_roles = await RoleQueries.get_member_premium_roles(session, member.id)

            if not premium_roles:
                await ctx.reply("Ten użytkownik nie ma żadnej roli premium.")
                return

            member_role, role = premium_roles[0]
            new_expiry = datetime.now(timezone.utc) + timedelta(hours=hours)

            await RoleQueries.update_role_expiration_date_direct(
                session, member.id, role.id, new_expiry
            )
            await session.commit()

            await ctx.reply(
                f"Zaktualizowano czas wygaśnięcia roli {role.name} dla {member.display_name}.\n"
                f"Nowy czas wygaśnięcia: {discord.utils.format_dt(new_expiry, 'R')}"
            )


class PaymentsView(discord.ui.View):
    """View for navigating through payment history."""

    def __init__(self, ctx: commands.Context, bot):
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
        ctx: commands.Context,
        bot: Zagadka,
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
            duration_days = 365 if self.page == 2 else 30
            price = self.role_price_map[role_name]
            if self.page == 2:
                price = price * 10  # Używamy ceny rocznej
            await self.handle_buy_role(interaction, role_name, self.member, duration_days, price)

        return button_callback

    async def next_page(self, interaction: discord.Interaction):
        """Go to the next page in the role shop."""
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
            view.role_price_map,  # Używamy cen z nowego widoku
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to the previous page in the role shop."""
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
            view.role_price_map,  # Używamy cen z nowego widoku
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_role_description(self, interaction: discord.Interaction):
        """Show the description of the role."""
        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
            balance = db_member.wallet_balance
            await session.commit()

        embed = await create_role_description_embed(
            self.ctx, self.page, self.bot.config["premium_roles"], balance, self.viewer, self.member
        )
        view = RoleDescriptionView(
            self.ctx,
            self.bot,
            self.page,
            self.bot.config["premium_roles"],
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
        """Handle logic for purchasing a role without existing premium roles."""
        await member.add_roles(role)
        await RoleQueries.add_role_to_member(
            session, member.id, role.id, timedelta(days=duration_days)
        )
        msg = f"Gratulacje! Otrzymałeś rolę {role.name}."
        await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)
        await interaction.followup.send(msg)

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
        ctx: commands.Context,
        bot: Zagadka,
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

    async def next_page(self, interaction: discord.Interaction):
        """Go to the next page in the role shop view."""
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


async def create_shop_embed(ctx, balance, role_price_map, premium_roles, page, viewer, member):
    if page == 1:
        title = "Sklep z rolami - ceny miesięczne"
        description = (
            "Aby zakupić rangę, kliknij przycisk odpowiadający jej nazwie.\n"
            "Za każde 10 zł jest 1000G.\n"
            "Zakup lub przedłużenie dowolnej rangi zdejmuje wszystkie muty na serwerze.\n\n"
            f"**Twoje ID: {viewer.id}**\n"
            "Pamiętaj, aby podczas wpłaty wpisać swoje ID w polu 'Wpisz swój nick'"
        )
    else:
        title = "Sklep z rolami - ceny roczne"
        description = (
            "Za zakup na rok płacisz tylko za 10 miesięcy, 2 miesiące są gratis.\n"
            "Za każde 10 zł jest 1000G.\n"
            "Zakup lub przedłużenie dowolnej rangi zdejmuje wszystkie muty na serwerze.\n\n"
            f"**Twoje ID: {viewer.id}**\n"
            "Pamiętaj, aby podczas wpłaty wpisać swoje ID w polu 'Wpisz swój nick'"
        )

    embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
    embed.add_field(name="Twoje środki", value=f"{balance}{CURRENCY_UNIT}", inline=False)

    # Wyświetlanie aktualnych ról
    if premium_roles:
        current_role, role_obj = premium_roles[0]
        expiration_date = discord.utils.format_dt(current_role.expiration_date, "R")
        embed.add_field(
            name="Aktualna rola", value=f"{role_obj.name}\nWygasa: {expiration_date}", inline=False
        )

    # Wyświetlanie dostępnych ról
    for role_name, price in role_price_map.items():
        if page == 2:  # Ceny roczne (10 miesięcy)
            display_price = price * 10
        else:  # Ceny miesięczne
            display_price = price
        embed.add_field(name=role_name, value=f"Cena: {display_price}{CURRENCY_UNIT}", inline=True)

    embed.set_footer(text="Użyj przycisku 'Opis ról' aby zobaczyć szczegółowe informacje o rangach")
    return embed


async def create_role_description_embed(ctx, page, premium_roles, balance, viewer, member):
    role = premium_roles[page - 1]
    role_name = role["name"]

    embed = discord.Embed(
        title=f"Opis roli {role_name}",
        description="\n".join([f"• {feature}" for feature in role["features"]]),
        color=discord.Color.blurple(),
    )

    # Dodanie informacji o cenie
    price = role["price"]
    annual_price = price * 10
    embed.add_field(
        name="Ceny",
        value=(
            f"Miesięcznie: {price}{CURRENCY_UNIT}\n"
            f"Rocznie: {annual_price}{CURRENCY_UNIT} (2 miesiące gratis)"
        ),
        inline=False,
    )

    # Dodanie informacji o koncie
    embed.add_field(name="Stan konta", value=f"{balance}{CURRENCY_UNIT}", inline=False)

    # Dodatkowe informacje o roli
    if role.get("team_size", 0) > 0:
        embed.add_field(
            name="Drużyna", value=f"Maksymalna liczba osób: {role['team_size']}", inline=True
        )
    if role.get("moderator_count", 0) > 0:
        embed.add_field(
            name="Moderatorzy", value=f"Liczba moderatorów: {role['moderator_count']}", inline=True
        )
    if role.get("points_multiplier", 0) > 0:
        embed.add_field(name="Bonus punktów", value=f"+{role['points_multiplier']}%", inline=True)

    return embed


async def setup(bot: commands.Bot):
    """Setup function for ShopCog."""
    await bot.add_cog(ShopCog(bot))
