import logging
from datetime import datetime, timedelta

import discord
import yaml
from discord.ext import commands

from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries
from utils.premium import PaymentData, PremiumManager

CURRENCY_UNIT = "G"

logger = logging.getLogger(__name__)


class ShopCog(commands.Cog):
    """Shop cog."""

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        with open("config.yml", "r") as config_file:
            self.config = yaml.safe_load(config_file)
        self.role_price_map = {
            role["symbol"]: role["price"] for role in self.config["premium_roles"]
        }
        self.inverse_role_price_map = {
            role["price"]: role["symbol"] for role in self.config["premium_roles"]
        }
        self.role_symbols = {role["id"]: role["symbol"] for role in self.config["premium_roles"]}

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
        view = RoleShopView(
            ctx, self.bot, self.role_price_map, self.inverse_role_price_map, self.role_symbols
        )
        embed = create_shop_embed(ctx, balance, self.role_price_map, premium_roles)
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
                    await user.send(f"`{user.id}`")
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

    def __init__(
        self, ctx: commands.Context, bot, role_price_map, inverse_role_price_map, role_symbols
    ):
        super().__init__()
        self.ctx = ctx
        self.guild = bot.guild
        self.bot = bot
        self.session = bot.session
        self.role_price_map = role_price_map
        self.inverse_role_price_map = inverse_role_price_map
        self.role_symbols = role_symbols

        for role_id, symbol in role_symbols.items():
            button = discord.ui.Button(label=symbol, style=discord.ButtonStyle.primary)
            button.callback = self.create_button_callback(role_id)
            self.add_item(button)

    def create_button_callback(self, role_id):
        async def button_callback(interaction: discord.Interaction):
            await self.buy_role(interaction, role_id)

        return button_callback

    async def get_affordable_roles(self, balance):
        return [role_name for role_name, price in self.role_price_map.items() if price <= balance]

    async def generate_embed(self):
        """Generate the embed for the role shop."""
        db_member = await MemberQueries.get_or_add_member(self.session, self.ctx.author.id)
        await self.session.commit()
        balance = db_member.wallet_balance
        premium_roles = await RoleQueries.get_member_premium_roles(self.session, self.ctx.author.id)
        return create_shop_embed(self.ctx, balance, self.role_price_map, premium_roles)

    async def buy_role(self, interaction: discord.Interaction, role_id):
        """Buy a role."""
        if self.guild is None or interaction.user.id != self.ctx.author.id:
            return

        role_name = self.role_symbols[role_id]
        price = self.role_price_map[role_name]

        role = discord.utils.get(self.guild.roles, name=role_name)

        if role is None:
            await interaction.response.send_message(f"Rola {role_name} nie została znaleziona.")
            return

        member = self.ctx.author
        if isinstance(member, discord.User):
            member = self.guild.get_member(member.id)
            if member is None:
                await interaction.response.send_message("Nie jesteś członkiem tego serwera.")
                return

        async with self.session() as session:
            db_member = await MemberQueries.get_or_add_member(session, member.id)

            # Fetch all premium roles of the user
            premium_roles = await RoleQueries.get_member_premium_roles(session, member.id)

            # If user has a premium role, calculate the price difference
            if premium_roles:
                last_role_price = self.inverse_role_price_map[premium_roles[0].role.name]
                # Check if the user is trying to buy a lower-priced role
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

            # If the user has another premium role within the last 24h,
            # check if it's the same role or a different one
            if premium_roles:
                existing_role = premium_roles[0].role

                # If the user is repurchasing the same role they already have
                if existing_role.id == role.id:
                    await RoleQueries.update_role_expiration_date(
                        session, member.id, role.id, timedelta(days=31)
                    )
                    msg = f"Przedłużyłeś rolę {role_name} o kolejne 31 dni."
                    difference = price  # Set the difference to the full price of the role

                # If the user is upgrading their role
                else:
                    await member.remove_roles(existing_role)
                    await RoleQueries.delete_member_role(session, member.id, existing_role.id)
                    await member.add_roles(role)
                    await RoleQueries.add_role_to_member(
                        session, member.id, role.id, timedelta(days=30)
                    )
                    msg = f"Uaktualniono twoją rolę z {existing_role.name} do {role_name}."

            # If the user doesn't have the role, set the appropriate message.
            else:
                await member.add_roles(role)
                await RoleQueries.add_role_to_member(
                    session, member.id, role.id, timedelta(days=30)
                )
                msg = f"Zakupiłeś rolę {role_name}."

            await MemberQueries.add_to_wallet_balance(session, member.id, -difference)
            await session.commit()
            await interaction.response.send_message(msg)
            embed = await self.generate_embed()
            await interaction.message.edit(embed=embed)


def create_shop_embed(ctx, balance, role_price_map, premium_roles):
    """Create the shop embed."""
    logger.info("Starting the creation of the shop embed for user %s", ctx.author.id)

    embed = discord.Embed(title="Sklep z rolami", color=discord.Color.blue())
    embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

    logger.info("Basic embed setup completed for user %s", ctx.author.id)

    embed.add_field(name="Twoje środki", value=f"{balance}{CURRENCY_UNIT}", inline=False)

    if premium_roles:
        logger.info("Handling premium roles for user %s", ctx.author.id)
        PremiumManager.add_premium_roles_to_embed(ctx, embed, premium_roles)

    embed.add_field(
        name="Zakup rangi",
        value="Aby zakupić rangę, kliknij przycisk odpowiadający jej symbolowi.",
        inline=False,
    )

    for symbol, price in role_price_map.items():
        embed.add_field(name=symbol, value=f"{price}{CURRENCY_UNIT}", inline=True)

    logger.info("Added role price map to embed for user %s", ctx.author.id)

    embed.add_field(name="Zakup środków", value="https://tipply.pl/u/zagadka", inline=False)
    embed.set_footer(text=f"Twoje ID: {ctx.author.id}")

    logger.info("Created shop embed for user %s", ctx.author.id)
    return embed


async def setup(bot: commands.Bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(ShopCog(bot))
