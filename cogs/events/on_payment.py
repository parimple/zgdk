"""Tipo Payments Cog"""

import asyncio
import logging
import os

from discord.ext import commands, tasks

from utils import PremiumManager, TipplyDataProvider

logger = logging.getLogger(__name__)


TIPO_API_URL = "https://tipo.live/api/v2/payments?token="
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
        await asyncio.sleep(5)
        logger.info("check_payments")
        payments_data = await self.data_provider.get_data()
        logger.info("payments_data: %s", payments_data)
        for payment_data in payments_data:
            await self.premium_manager.process_data(payment_data)
        # for i, payment_data in enumerate(payments_data):
        #     if i > 10:
        #         break
        #     logger.info("payment_data %s: %s", i, payment_data)
        #     await self.premium_manager.process_data(payment_data)

    @check_payments.before_loop
    async def before_check_payments(self):
        """Before Check Payments"""
        await self.bot.wait_until_ready()
        if self.guild is None:
            logger.info("guild is None")
            self.guild = self.bot.get_guild(self.bot.guild_id)


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnPaymentEvent(bot))
