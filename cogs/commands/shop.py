""" Shop cog. """

import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries
from main import Zagadka
from utils.premium import PaymentData, PremiumManager

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
            paid_at=datetime.now(),
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
        self.role_price_map = {role["symbol"]: role["price"] for role in premium_roles}
        self.inverse_role_price_map = {role["symbol"]: role["price"] for role in premium_roles}
        self.role_ids = {
            role["symbol"]: discord.utils.get(self.guild.roles, name=role["symbol"]).id
            for role in premium_roles
        }
        self.config = bot.config

        for role_symbol, role_id in self.role_ids.items():
            button = discord.ui.Button(
                label=role_symbol,
                style=discord.ButtonStyle.primary,
                disabled=self.balance < self.role_price_map[role_symbol],
            )
            button.callback = self.create_button_callback(role_symbol)
            self.add_item(button)

        if page == 1:
            next_button = discord.ui.Button(label="➡️", style=discord.ButtonStyle.secondary)
            next_button.callback = self.next_page
            self.add_item(next_button)
        else:
            previous_button = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary)
            previous_button.callback = self.previous_page
            self.add_item(previous_button)

    def create_button_callback(self, role_symbol):
        async def button_callback(interaction: discord.Interaction):
            await self.buy_role(interaction, role_symbol)

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

    async def generate_embed(self):
        """Generate the embed for the role shop."""
        db_member = await MemberQueries.get_or_add_member(self.session, self.ctx.author.id)
        await self.session.commit()
        balance = db_member.wallet_balance
        premium_roles = await RoleQueries.get_member_premium_roles(self.session, self.ctx.author.id)
        return await create_shop_embed(
            self.ctx, balance, self.role_price_map, premium_roles, self.page
        )

    async def buy_role(self, interaction: discord.Interaction, role_symbol: str):
        """Buy a role."""
        if self.guild is None or interaction.user.id != self.ctx.author.id:
            return

        role_id = self.role_ids[role_symbol]
        role = discord.utils.get(self.guild.roles, id=role_id)
        price = (
            self.role_price_map[role_symbol]
            if self.page == 1
            else self.role_price_map[role_symbol] * 10
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

            if premium_roles:
                last_role = premium_roles[0]
                last_role_price = self.inverse_role_price_map.get(last_role.role.name)

                if last_role_price is None:
                    await interaction.response.send_message(
                        "Nie można znaleźć ceny poprzedniej roli użytkownika."
                    )
                    return

                if price < last_role_price:
                    await interaction.response.send_message(
                        "Nie możesz kupić niższej rangi, jeśli posiadasz już wyższą rangę."
                    )
                    return
                difference = price - last_role_price
            else:
                difference = price

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
                        msg = f"Przedłużyłeś rolę {role_symbol} o kolejne 31 dni."
                    else:
                        await RoleQueries.update_role_expiration_date(
                            session, member.id, role.id, timedelta(days=365)
                        )
                        msg = f"Przedłużyłeś rolę {role_symbol} o kolejne 12 miesięcy."
                    difference = price

                else:
                    await member.remove_roles(existing_role)
                    await RoleQueries.delete_member_role(session, member.id, existing_role.id)
                    await member.add_roles(role)
                    if self.page == 1:
                        await RoleQueries.add_role_to_member(
                            session, member.id, role.id, timedelta(days=30)
                        )
                        msg = f"Uaktualniono twoją rolę z {existing_role.name} do {role_symbol}."
                    else:
                        await RoleQueries.add_role_to_member(
                            session, member.id, role.id, timedelta(days=365)
                        )
                        msg = f"Uaktualniono twoją rolę z {existing_role.name} do {role_symbol} na 12 miesięcy."

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
                msg = f"Zakupiłeś rolę {role_symbol}."

            await MemberQueries.add_to_wallet_balance(session, member.id, -difference)
            await session.commit()
            await interaction.response.send_message(msg)
            embed = await self.generate_embed()
            await interaction.message.edit(embed=embed)


async def create_shop_embed(ctx, balance, role_price_map, premium_roles, page):
    """Create the shop embed."""
    logger.info("Starting the creation of the shop embed for user %s", ctx.author.id)

    color = ctx.author.color if ctx.author.color.value else discord.Color.blue()

    if page == 1:
        embed = discord.Embed(
            title="Sklep z rolami",
            description="Aby zakupić rangę, kliknij przycisk odpowiadający jej cenie.\nZa każde 10 zł jest 1000G.",
            color=color,
        )
    else:
        embed = discord.Embed(
            title="Sklep z rolami - ceny na rok",
            description="Za zakup na rok płacisz tylko za 10 miesięcy, 2 miesiące są gratis.\nZa każde 10 zł jest 1000G.",
            color=color,
        )

    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

    logger.info("Basic embed setup completed for user %s", ctx.author.id)

    embed.add_field(name="Twoje środki", value=f"{balance}{CURRENCY_UNIT}", inline=False)

    if premium_roles:
        logger.info("Handling premium roles for user %s", ctx.author.id)
        PremiumManager.add_premium_roles_to_embed(ctx, embed, premium_roles)

    for role_symbol, price in role_price_map.items():
        if page == 1:
            embed.add_field(name=role_symbol, value=f"{price}{CURRENCY_UNIT}", inline=True)
        else:
            annual_price = price * 10
            embed.add_field(name=role_symbol, value=f"{annual_price}{CURRENCY_UNIT}", inline=True)

    logger.info("Added role price map to embed for user %s", ctx.author.id)

    embed.add_field(name="Zakup środków", value="https://tipply.pl/u/zagadka", inline=False)
    embed.set_footer(text=f"Twoje ID: {ctx.author.id}")

    logger.info("Created shop embed for user %s", ctx.author.id)
    return embed


async def setup(bot: commands.Bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(ShopCog(bot))
