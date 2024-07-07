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
    async def shop(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        if not member:
            member = ctx.author

        viewer = ctx.author  # Osoba przeglądająca sklep (ta, która kliknęła przycisk)

        if not isinstance(member, discord.Member):
            member = self.bot.guild.get_member(member.id)
            if not member:
                raise commands.UserInputError("Nie można znaleźć członka na tym serwerze.")

        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, viewer.id)
            balance = db_viewer.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, member.id)
            await session.commit()

        view = RoleShopView(
            ctx,
            self.bot,
            self.bot.config["premium_roles"],
            balance,
            page=1,
            viewer=viewer,
            member=member,
        )
        embed = await create_shop_embed(
            ctx,
            balance,
            view.role_price_map,
            premium_roles,
            page=1,
            viewer=viewer,
            member=member,
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
        self.role_price_map = {role["name"]: role["price"] for role in premium_roles}
        self.role_ids = {
            role["name"]: discord.utils.get(self.guild.roles, name=role["name"]).id
            for role in premium_roles
        }
        self.mute_roles = {role["name"]: role for role in self.bot.config["mute_roles"]}
        self.viewer = viewer
        self.member = member

        for role_name, _ in self.role_ids.items():
            button = discord.ui.Button(
                label=role_name,
                style=discord.ButtonStyle.primary,
                disabled=self.balance < self.role_price_map[role_name],
            )
            button.callback = self.create_button_callback(role_name)
            self.add_item(button)

        if page == 1:
            next_button = discord.ui.Button(label="➡️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
        else:
            previous_button = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary)
            previous_button.callback = self.previous_page
            self.add_item(previous_button)

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

    def create_button_callback(self, role_name):
        """Create a button callback for the specified role name."""

        async def button_callback(interaction: discord.Interaction):
            duration_days = 365 if self.page != 1 else 1
            await self.handle_buy_role(interaction, role_name, self.member, duration_days)

        return button_callback

    async def next_page(self, interaction: discord.Interaction):
        """Go to the next page in the role shop."""
        self.page = 2
        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
            balance = db_member.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, self.member.id)
            await session.commit()

        embed = await create_shop_embed(
            self.ctx,
            balance,
            self.role_price_map,
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )
        view = RoleShopView(
            self.ctx,
            self.bot,
            self.bot.config["premium_roles"],
            balance,
            self.page,
            self.viewer,
            self.member,
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to the previous page in the role shop."""
        self.page = 1
        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, self.viewer.id)
            balance = db_member.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, self.member.id)
            await session.commit()

        embed = await create_shop_embed(
            self.ctx,
            balance,
            self.role_price_map,
            premium_roles,
            self.page,
            self.viewer,
            self.member,
        )
        view = RoleShopView(
            self.ctx,
            self.bot,
            self.bot.config["premium_roles"],
            balance,
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

    async def handle_buy_role(self, interaction, role_name, member, duration_days=30):
        role_id = self.role_ids[role_name]
        role = discord.utils.get(self.guild.roles, id=role_id)
        price = self.role_price_map[role_name]

        if isinstance(member, discord.User):
            member = self.guild.get_member(member.id)
            if member is None:
                await interaction.response.send_message("Nie jesteś członkiem tego serwera.")
                return

        if self.viewer != member:
            confirm_message = f"Czy na pewno chcesz kupić rolę {role_name} dla {member.display_name} za {price}{CURRENCY_UNIT}?"
        else:
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
        msg = f"Zakupiłeś rolę {role.name} dla {member.display_name}."
        await MemberQueries.add_to_wallet_balance(session, self.viewer.id, -price)
        await interaction.response.send_message(msg)

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

        This method checks if the new role is of higher value than the existing one,
        calculates refunds if necessary, and updates the member's roles accordingly.
        """
        last_member_role, last_role = premium_roles[0]
        last_role_price = self.role_price_map.get(last_role.name)

        if last_role_price is None:
            await interaction.followup.send("Nie można znaleźć ceny poprzedniej roli użytkownika.")
            return

        if price < last_role_price:
            if role.name == "★1" and has_mute_roles:
                await self.remove_mute_roles(member)
                await interaction.followup.send(
                    "Usunięto mutujące role z powodu zakupu najniższej rangi."
                )
            else:
                await interaction.followup.send(
                    "Nie możesz kupić niższej rangi, jeśli posiadasz już wyższą rangę."
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

        if last_role.id == role.id:
            extend_days = 31 if duration_days == 30 else 365
            await RoleQueries.update_role_expiration_date(
                session, member.id, role.id, timedelta(days=extend_days)
            )
            msg = f"Przedłużyłeś rolę {role.name} o kolejne {extend_days} dni."
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
    """Create the shop embed."""
    logger.info("Starting the creation of the shop embed for user %s", ctx.author.id)

    color = discord.Color.blurple()

    if page == 1:
        embed = discord.Embed(
            title="Sklep z rolami",
            description=(
                "Aby zakupić rangę, kliknij przycisk odpowiadający jej cenie.\n"
                "Za każde 10 zł jest 1000G.\n"
                "Kupno rangi ★1 jest równoznaczne ze zdjęciem wszystkich mutów na serwerze.\n"
                "Kupno wyższej rangi lub przedłużenie również zdejmie muty."
            ),
            color=color,
        )
    else:
        embed = discord.Embed(
            title="Sklep z rolami - ceny na rok",
            description=(
                "Za zakup na rok płacisz tylko za 10 miesięcy, 2 miesiące są gratis.\n"
                "Za każde 10 zł jest 1000G.\n"
                "Kupno rangi ★1 jest równoznaczne ze zdjęciem wszystkich mutów na serwerze.\n"
                "Kupno wyższej rangi lub przedłużenie również zdejmie muty."
            ),
            color=color,
        )

    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

    logger.info("Basic embed setup completed for user %s", ctx.author.id)

    embed.add_field(name="Twoje środki", value=f"{balance}{CURRENCY_UNIT}", inline=False)

    if premium_roles:
        current_role = premium_roles[0][1].name
        embed.add_field(name="Aktualna rola", value=current_role, inline=False)
        PremiumManager.add_premium_roles_to_embed(ctx, embed, premium_roles)
    else:
        embed.add_field(name="Aktualna rola", value="Brak", inline=False)

    for role_name, price in role_price_map.items():
        if page == 1:
            embed.add_field(name=role_name, value=f"{price}{CURRENCY_UNIT}", inline=True)
        else:
            annual_price = price * 10
            embed.add_field(name=role_name, value=f"{annual_price}{CURRENCY_UNIT}", inline=True)

    if viewer != member:
        embed.add_field(
            name="Informacja",
            value="Kupujesz rolę dla innego użytkownika, kwota będzie pobrana z twojego konta.",
            inline=False,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Rolę kupujesz dla: {member.display_name} ({member.id})")
    else:
        embed.set_thumbnail(url=viewer.display_avatar.url)

    logger.info("Added role price map to embed for user %s", ctx.author.id)

    embed.set_footer(text=f"Twoje ID: {ctx.author.id} wklej w polu (Wpisz swój nick)")

    logger.info("Created shop embed for user %s", ctx.author.id)
    return embed


async def create_role_description_embed(ctx, page, premium_roles, balance, viewer, member):
    """Create the role description embed."""
    descriptions = {
        "★1": (
            "Jeśli masz bana to ta opcja tylko odbanowuje Cię z serwera, bez poniższych opcji!\n"
            "Usunięcie wszystkich mutów\n"
            "Czarny kolor nicku\n"
            "Możliwość wyrzucania osób z kanałów (np ?connect - id)\n"
            'Możliwość tworzenia kanałów #"@PREM"\n'
            "Ranga wspierającego\n"
            "Emotki i stickery z każdego serwera\n"
            "25% więcej punktów dodawanych do aktywności"
        ),
        "★2": (
            "Wszystko co niżej\n"
            "Wybór jednego z 16 milionów kolorów nicku (np ?color ff00ff)\n"
            "Dodatkowe 25% więcej punktów do aktywności (razem 50%)"
        ),
        "★3": (
            "Wszystko co niżej\n"
            "Kolor Twojego nicku zmienia barwy!\n"
            "Dodatkowe 25% więcej punktów do aktywności (razem 75%)\n"
            "Masz opcję założenia klanu (8 osób) z własną rangą i kanałem tekstowym ?team + id"
        ),
        "★4": (
            "Wszystko co niżej\n"
            "Lądujesz na samej górze listy użytkowników\n"
            'Dostajesz możliwość tworzenia kanałów głosowych #"@VIP"\n'
            "Dodatkowe 25% więcej punktów do aktywności (razem 100%)\n"
            "Twój klan może mieć nawet 16 członków"
        ),
        "★5": (
            "Wszystko co niżej\n"
            "Lądujesz jeszcze wyżej na liście użytkowników\n"
            'Dostajesz możliwość tworzenia kanałów głosowych #"@VIP+" NAD lounge¹\n'
            "Dodatkowe 100% więcej punktów do aktywności (razem 200%)\n"
            "Twój klan może mieć nawet 24 członków"
        ),
        "★6": (
            "Wszystko co niżej\n"
            "Dodatkowe 100% więcej punktów do aktywności (razem 300%)\n"
            "Twój klan może mieć nawet 32 członków\n"
            "Możesz zmieniać kolor klanu (wszystkie 32 osoby otrzymują ten sam kolor nicku) "
            + "?teamcolor pink"
        ),
        "★7": (
            "Wszystko co niżej\n"
            "Możesz wybrać ikonkę roli klanu dla wszystkich członków (1 raz)\n"
            "Dodatkowe 100% więcej punktów do aktywności (razem 400%)\n"
            "Twój klan może mieć nawet 40 członków"
        ),
        "★8": (
            "Wszystko co niżej\n"
            "Lądujesz nad botem @zaGadka na liście użytkowników\n"
            "Dodatkowe 100% więcej punktów do aktywności (razem 500%)\n"
            "Twój klan może mieć nawet 48 członków"
        ),
        "★9": (
            "Wszystko co niżej\n"
            "Dodatkowe 200% więcej punktów do aktywności (razem 700%)\n"
            "Twój klan może mieć nawet 64 członków"
        ),
    }

    role_name = premium_roles[page - 1]["name"]
    price = premium_roles[page - 1]["price"]
    description = descriptions[role_name]

    balance_in_pln = (price - balance) / 100 if price > balance else 0

    embed = discord.Embed(
        title=f"Opis roli {role_name}",
        description=(
            f"{description}\n\n"
            f"Cena: {price}{CURRENCY_UNIT}\n"
            f"Twój stan konta: {balance}{CURRENCY_UNIT}\n"
            f"Dopłać: {balance_in_pln:.2f} zł aby kupić rangę"
        )
        if balance_in_pln > 0
        else (
            f"{description}\n\n"
            f"Cena: {price}{CURRENCY_UNIT}\n"
            f"Twój stan konta: {balance}{CURRENCY_UNIT}"
        ),
        color=discord.Color.blurple(),
    )

    if viewer != member:
        embed.add_field(
            name="Informacja",
            value="Kupujesz rolę dla innego użytkownika, kwota będzie pobrana z twojego konta.",
            inline=False,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Rolę kupujesz dla: {member.display_name} ({member.id})")
    else:
        embed.set_thumbnail(url=viewer.display_avatar.url)

    return embed


async def setup(bot: commands.Bot):
    """Setup function for ShopCog."""
    await bot.add_cog(ShopCog(bot))
