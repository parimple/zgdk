"""On Payments Event"""

import logging
import os

from discord.ext import commands, tasks

from utils.premium import PremiumManager, TipplyDataProvider

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TIPO_API_TOKEN")


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

    @tasks.loop(minutes=60.0)
    async def check_payments(self):
        """Check Payments"""
        logger.info("Checking for new payments")

        payments_data = await self.data_provider.get_data()
        logger.info("Found %s new payments", len(payments_data))

        for payment_data in payments_data:
            try:
                await self.premium_manager.process_data(payment_data)
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


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnPaymentEvent(bot))
