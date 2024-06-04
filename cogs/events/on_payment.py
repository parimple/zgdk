"""
On Payments Event Cog
"""

import logging
import os

import discord
from discord.ext import commands, tasks

from utils.premium import PremiumManager, TipplyDataProvider

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TIPO_API_TOKEN")
CURRENCY_UNIT = "G"


class OnPaymentEvent(commands.Cog):
    """Class for the Tipo Payments Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.guild = bot.guild
        self.premium_manager = PremiumManager(bot.session, bot.guild)
        self.data_provider = TipplyDataProvider(bot.session)
        self.check_payments.start()  # pylint: disable=no-member

    async def cog_unload(self):
        """Cog Unload"""
        self.check_payments.cancel()  # pylint: disable=no-member

    @tasks.loop(minutes=10.0)
    async def check_payments(self):
        """Check Payments"""
        logger.info("Checking for new payments")

        payments_data = await self.data_provider.get_data()
        logger.info("Found %s new payments", len(payments_data))

        for payment_data in payments_data:
            try:
                await self.premium_manager.process_data(payment_data)
                await self.handle_payment(payment_data)
                logger.info("Processed payment: %s", payment_data)
            except Exception as err:  # pylint: disable=broad-except
                logger.error("Error while processing payment %s: %s", payment_data, err)

    @check_payments.before_loop
    async def before_check_payments(self):
        """Before Check Payments"""
        await self.bot.wait_until_ready()
        if self.guild is None:
            logger.info("Guild is not set, fetching from bot")
            self.guild = self.bot.get_guild(self.bot.guild_id)

    async def handle_payment(self, payment_data):
        """Handle a single payment and send notification"""
        channel_id = self.bot.config["channels"]["donation"]
        channel = self.bot.get_channel(channel_id)

        if not channel:
            logger.error("Donation channel not found: %s", channel_id)
            return

        amount_g = payment_data.amount
        member = await self.premium_manager.get_member(payment_data.name)
        if member is None:
            logger.error("Member not found: %s", payment_data.name)
            return

        owner_id = self.bot.config.get("owner_id")
        owner = self.guild.get_member(owner_id)

        embed = discord.Embed(
            title="Gratulacje!",
            description=f"{member.mention}, Twoje konto zostało pomyślnie zasilone o {amount_g:.2f}{CURRENCY_UNIT}!",
            color=discord.Color.green(),
        )
        embed.set_image(url=self.bot.config["gifs"]["donation"])

        view = discord.ui.View()
        view.add_item(
            BuyRoleButton(
                bot=self.bot,
                member=member,
                label="Kup rangę",
                style=discord.ButtonStyle.success,
            )
        )
        view.add_item(
            discord.ui.Button(
                label="Doładuj konto",
                style=discord.ButtonStyle.link,
                url=self.bot.config["donate_url"],
            )
        )

        message = await channel.send(embed=embed, view=view)
        if owner:
            await message.reply(f"{owner.mention}")


class BuyRoleButton(discord.ui.Button):
    """Button to buy a role."""

    def __init__(self, bot, member, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.member = member

    async def callback(self, interaction: discord.Interaction):
        ctx = await self.bot.get_context(interaction.message)
        ctx.author = self.member
        await ctx.invoke(self.bot.get_command("shop"))


async def setup(bot: commands.Bot):
    """Setup function for the payment event cog"""
    await bot.add_cog(OnPaymentEvent(bot))
