""" Shop cog for the Zagadka bot. """
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries
from main import Zagadka
from utils.premium import PaymentData, PremiumManager
from utils.refund import calculate_refund

CURRENCY_UNIT = "G"

logger = logging.getLogger(__name__)


class ShopCog(commands.Cog):
    """Shop cog."""

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @commands.hybrid_command(name="shop", description="Wyświetla sklep z rolami.")
    @commands.has_permissions(administrator=True)
    async def shop(self, ctx: commands.Context):
        """Display the shop with all available roles."""
        db_member = await MemberQueries.get_or_add_member(self.session, ctx.author.id)
        await self.session.commit()
        balance = db_member.wallet_balance
        premium_roles = await RoleQueries.get_member_premium_roles(self.session, ctx.author.id)
        logger.info(
            "User %s requested shop. Balance: %s, %s", ctx.author.id, balance, premium_roles
        )
        view = RoleShopView(ctx, self.bot, self.bot.config["premium_roles"], balance, page=1)
        embed = await create_shop_embed(ctx, balance, view.role_price_map, premium_roles, page=1)
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

        async with self.session() as session:
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
        async with self.session() as session:
            # Fetch the payment by its ID
            payment = await HandledPaymentQueries.get_payment_by_id(session, payment_id)

            if payment:
                # Assign the member ID to the payment
                payment.member_id = user.id

                # Update the user's wallet balance
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

                # Send a DM to the user
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

        payments = await HandledPaymentQueries.get_last_payments(self.session, limit=10)
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
    """Payments view."""

    def __init__(self, ctx: commands.Context, bot):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.session = bot.session
        self.current_offset = 0  # Start at the most recent payments

    async def display_payments(self, interaction: discord.Interaction):
        """Display the payments."""
        self.current_offset = max(0, self.current_offset)
        payments = await HandledPaymentQueries.get_last_payments(
            self.session, offset=self.current_offset, limit=10
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
    async def newer_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):  # pylint: disable=unused-argument
        """Go to the newer payments."""
        self.current_offset -= 10
        await self.display_payments(interaction)

    @discord.ui.button(label="Starsze", style=discord.ButtonStyle.primary)
    async def older_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):  # pylint: disable=unused-argument
        """Go to the older payments."""
        self.current_offset += 10
        await self.display_payments(interaction)


class RoleShopView(discord.ui.View):
    """Role shop view."""

    def __init__(self, ctx: commands.Context, bot: Zagadka, premium_roles, balance, page=1):
        super().__init__()
        self.ctx = ctx
        self.guild = bot.guild
        self.bot = bot
        self.session = bot.session
        self.balance = balance
        self.page = page
        self.role_price_map = {role["name"]: role["price"] for role in premium_roles}
        self.role_ids = {
            role["name"]: discord.utils.get(self.guild.roles, name=role["name"]).id
            for role in premium_roles
        }
        self.mute_roles = {role["name"]: role for role in self.bot.config["mute_roles"]}

        for role_name, role_id in self.role_ids.items():
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

        # Add description button
        description_button = discord.ui.Button(label="Opis ról", style=discord.ButtonStyle.primary)
        description_button.callback = self.show_role_description
        self.add_item(description_button)

        # Check if donate_url exists in config
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
        async def button_callback(interaction: discord.Interaction):
            ctx = await self.bot.get_context(interaction.message)
            ctx.author = self.ctx.author
            await ctx.invoke(self.bot.get_command("buy_role"), role_name=role_name)

        return button_callback

    async def next_page(self, interaction: discord.Interaction):
        self.page = 2
        db_member = await MemberQueries.get_or_add_member(self.session, self.ctx.author.id)
        await self.session.commit()
        balance = db_member.wallet_balance
        premium_roles = await RoleQueries.get_member_premium_roles(self.session, self.ctx.author.id)
        embed = await create_shop_embed(
            self.ctx, balance, self.role_price_map, premium_roles, self.page
        )
        view = RoleShopView(
            self.ctx, self.bot, self.bot.config["premium_roles"], balance, self.page
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def previous_page(self, interaction: discord.Interaction):
        self.page = 1
        db_member = await MemberQueries.get_or_add_member(self.session, self.ctx.author.id)
        await self.session.commit()
        balance = db_member.wallet_balance
        premium_roles = await RoleQueries.get_member_premium_roles(self.session, self.ctx.author.id)
        embed = await create_shop_embed(
            self.ctx, balance, self.role_price_map, premium_roles, self.page
        )
        view = RoleShopView(
            self.ctx, self.bot, self.bot.config["premium_roles"], balance, self.page
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def show_role_description(self, interaction: discord.Interaction):
        embed = await create_role_description_embed(
            self.ctx, self.page, self.bot.config["premium_roles"]
        )
        view = RoleDescriptionView(self.ctx, self.bot, self.page, self.bot.config["premium_roles"])
        await interaction.response.edit_message(embed=embed, view=view)

    async def generate_embed(self):
        """Generate the embed for the role shop."""
        db_member = await MemberQueries.get_or_add_member(self.session, self.ctx.author.id)
        await self.session.commit()
        balance = db_member.wallet_balance
        premium_roles = await RoleQueries.get_member_premium_roles(self.session, self.ctx.author.id)
        return await create_shop_embed(
            self.ctx, balance, self.role_price_map, premium_roles, self.page
        )

    async def buy_role(self, interaction: discord.Interaction, role_name: str):
        """Buy a role."""
        if self.guild is None or interaction.user.id != self.ctx.author.id:
            return

        role_id = self.role_ids[role_name]
        role = discord.utils.get(self.guild.roles, id=role_id)
        price = (
            self.role_price_map[role_name]
            if self.page == 1
            else self.role_price_map[role_name] * 10
        )

        member = self.ctx.author
        if isinstance(member, discord.User):
            member = self.guild.get_member(member.id)
            if member is None:
                await interaction.response.send_message("Nie jesteś członkiem tego serwera.")
                return

        async with self.session() as session:
            db_member = await MemberQueries.get_or_add_member(session, member.id)
            premium_roles = await RoleQueries.get_member_premium_roles(session, member.id)

            # Check for mute roles
            has_mute_roles = any(
                role
                for role in self.mute_roles.values()
                if role["id"] in [r.id for r in member.roles]
            )

            if premium_roles:
                last_role = premium_roles[0]
                last_role_price = self.role_price_map.get(last_role.role.name)

                if last_role_price is None:
                    await interaction.response.send_message(
                        "Nie można znaleźć ceny poprzedniej roli użytkownika."
                    )
                    return

                if price < last_role_price:
                    # If user has mute roles and buying the lowest rank
                    if role_name == "★1" and has_mute_roles:
                        await self.remove_mute_roles(member)
                        await interaction.response.send_message(
                            "Usunięto mutujące role z powodu zakupu najniższej rangi."
                        )
                    else:
                        await interaction.response.send_message(
                            "Nie możesz kupić niższej rangi, jeśli posiadasz już wyższą rangę."
                        )
                    return

                # Calculate refund for the remaining time of the current role
                refund_amount = calculate_refund(last_role.expiration_date, last_role_price)
                difference = price - refund_amount
                msg_refund = f" Część kwoty została zwrócona za poprzednią rangę ({refund_amount}{CURRENCY_UNIT})."
            else:
                difference = price
                msg_refund = ""

            if db_member.wallet_balance < difference:
                await interaction.response.send_message("Nie masz wystarczająco dużo pieniędzy.")
                return

            if premium_roles:
                existing_role = premium_roles[0].role

                if existing_role.id == role.id:
                    if self.page == 1:
                        await RoleQueries.update_role_expiration_date(
                            session, member.id, role.id, timedelta(days=31)
                        )
                        msg = f"Przedłużyłeś rolę {role_name} o kolejne 31 dni."
                    else:
                        await RoleQueries.update_role_expiration_date(
                            session, member.id, role.id, timedelta(days=365)
                        )
                        msg = f"Przedłużyłeś rolę {role_name} o kolejne 12 miesięcy."
                    difference = price

                else:
                    await member.remove_roles(existing_role)
                    await RoleQueries.delete_member_role(session, member.id, existing_role.id)
                    await member.add_roles(role)
                    if self.page == 1:
                        await RoleQueries.add_role_to_member(
                            session, member.id, role.id, timedelta(days=30)
                        )
                        msg = f"Uaktualniono twoją rolę z {existing_role.name} do {role_name}.{msg_refund}"
                    else:
                        await RoleQueries.add_role_to_member(
                            session, member.id, role.id, timedelta(days=365)
                        )
                        msg = f"Uaktualniono twoją rolę z {existing_role.name} do {role_name} na 12 miesięcy.{msg_refund}"

            else:
                await member.add_roles(role)
                if self.page == 1:
                    await RoleQueries.add_role_to_member(
                        session, member.id, role.id, timedelta(days=30)
                    )
                else:
                    await RoleQueries.add_role_to_member(
                        session, member.id, role.id, timedelta(days=365)
                    )
                msg = f"Zakupiłeś rolę {role_name}.{msg_refund}"

            await MemberQueries.add_to_wallet_balance(session, member.id, -difference)
            await session.commit()
            await interaction.response.send_message(msg)
            embed = await self.generate_embed()
            await interaction.message.edit(embed=embed)

    async def remove_mute_roles(self, member: discord.Member):
        """Remove all mute roles from the member and notify them."""
        roles_to_remove = [
            self.guild.get_role(role["id"])
            for role in self.mute_roles.values()
            if self.guild.get_role(role["id"]) in member.roles
        ]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            await member.send(
                f"Usunięto następujące role mutujące: {', '.join([role.name for role in roles_to_remove])}"
            )


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
        await ctx.invoke(self.bot.get_command("buy_role"), role_name=self.role_name)


class RoleDescriptionView(discord.ui.View):
    """Role description view."""

    def __init__(self, ctx: commands.Context, bot: Zagadka, page=1, premium_roles=[]):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.session = bot.session
        self.page = page
        self.premium_roles = premium_roles

        # Add buttons
        previous_button = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary)
        previous_button.callback = self.previous_page
        self.add_item(previous_button)

        buy_button = BuyRoleButton(
            bot,
            ctx.author,
            premium_roles[page - 1]["name"],
            label="Kup rangę",
            style=discord.ButtonStyle.primary,
        )
        self.add_item(buy_button)

        self.add_item(
            discord.ui.Button(
                label="Do sklepu", style=discord.ButtonStyle.primary, custom_id="go_to_shop"
            )
        )

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
        self.page = (self.page % len(self.premium_roles)) + 1
        embed = await create_role_description_embed(self.ctx, self.page, self.premium_roles)
        view = RoleDescriptionView(self.ctx, self.bot, self.page, self.premium_roles)
        await interaction.response.edit_message(embed=embed, view=view)

    async def previous_page(self, interaction: discord.Interaction):
        self.page = (self.page - 2) % len(self.premium_roles) + 1
        embed = await create_role_description_embed(self.ctx, self.page, self.premium_roles)
        view = RoleDescriptionView(self.ctx, self.bot, self.page, self.premium_roles)
        await interaction.response.edit_message(embed=embed, view=view)


async def create_shop_embed(ctx, balance, role_price_map, premium_roles, page):
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
        logger.info("Handling premium roles for user %s", ctx.author.id)
        PremiumManager.add_premium_roles_to_embed(ctx, embed, premium_roles)

    for role_name, price in role_price_map.items():
        if page == 1:
            embed.add_field(name=role_name, value=f"{price}{CURRENCY_UNIT}", inline=True)
        else:
            annual_price = price * 10
            embed.add_field(name=role_name, value=f"{annual_price}{CURRENCY_UNIT}", inline=True)

    logger.info("Added role price map to embed for user %s", ctx.author.id)

    embed.set_footer(text=f"Twoje ID: {ctx.author.id} wklej w polu (Wpisz swój nick)")

    logger.info("Created shop embed for user %s", ctx.author.id)
    return embed


async def create_role_description_embed(ctx, page, premium_roles):
    """Create the role description embed."""
    descriptions = {
        "★1": (
            "Jeśli masz bana to ta opcja tylko odbanowuje Cię z serwera, bez poniższych opcji!\n"
            "Usunięcie wszystkich mutów\n"
            "Czarny kolor nicku\n"
            "Możliwość wyrzucania osób z kanałów (np ?connect - id)\n"
            'Możliwość tworzenia kanałów #"___________@PREM___________"\n'
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
            'Dostajesz możliwość tworzenia kanałów głosowych #"___________@VIP_____________"\n'
            "Dodatkowe 25% więcej punktów do aktywności (razem 100%)\n"
            "Twój klan może mieć nawet 16 członków"
        ),
        "★5": (
            "Wszystko co niżej\n"
            "Lądujesz jeszcze wyżej na liście użytkowników\n"
            'Dostajesz możliwość tworzenia kanałów głosowych #"___________@VIP+____________" NAD lounge¹\n'
            "Dodatkowe 100% więcej punktów do aktywności (razem 200%)\n"
            "Twój klan może mieć nawet 24 członków"
        ),
        "★6": (
            "Wszystko co niżej\n"
            "Dodatkowe 100% więcej punktów do aktywności (razem 300%)\n"
            "Twój klan może mieć nawet 32 członków\n"
            "Możesz zmieniać kolor klanu (wszystkie 32 osoby otrzymują ten sam kolor nicku) ?teamcolor pink"
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

    db_member = await MemberQueries.get_or_add_member(ctx.bot.session, ctx.author.id)
    balance = db_member.wallet_balance
    balance_in_pln = (price - balance) / 10

    embed = discord.Embed(
        title=f"Opis roli {role_name}",
        description=f"{description}\n\nCena: {price}{CURRENCY_UNIT}\nTwój stan konta: {balance}{CURRENCY_UNIT}\nPotrzebujesz jeszcze: {balance_in_pln:.2f} zł",
        color=discord.Color.blurple(),
    )

    return embed


async def setup(bot: commands.Bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(ShopCog(bot))
