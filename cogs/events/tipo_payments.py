"""Tipo Payments Cog"""

import logging
import os
from datetime import datetime

import httpx
from discord.ext import commands, tasks

from datasources.queries import HandledPaymentQueries

logger = logging.getLogger(__name__)


TIPO_API_URL = "https://tipo.live/api/v2/payments?token="
TOKEN = os.environ.get("TIPO_API_TOKEN")


class TipoPayments(commands.Cog):
    """Class for the Tipo Payments Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.api_url = f"{TIPO_API_URL}{TOKEN}"
        self.check_payments.start()  # pylint: disable=no-member

    async def cog_unload(self):
        """Cog Unload"""
        self.check_payments.cancel()  # pylint: disable=no-member

    async def fetch_payments(self):
        """Fetch Payments"""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.api_url)
            data = response.json()
            payments = data.get("payments", [])
        return payments

    async def get_member_id(self, name):
        """Get Member ID"""
        member_id = None
        if name.isdigit():
            member_id = int(name)
        if not member_id:
            member = self.bot.guild.get_member_named(name)
            if member:
                member_id = member.id
        return member_id

    async def process_payment(self, payment):
        """Process Payment"""
        payment_id = payment["id"]
        name = payment["name"]
        amount = payment["amount"]
        paid_at = datetime.fromisoformat(payment["paid_at"].rstrip("Z"))

        if payment_id and name and amount and paid_at:
            member_id = await self.get_member_id(name)
            if member_id:
                async with self.bot.async_session.begin() as session:
                    payment_exists = await HandledPaymentQueries.get_payment_by_id(
                        session, payment_id
                    )
                    if not payment_exists:
                        await HandledPaymentQueries.add_payment(
                            session, payment_id, member_id, name, amount, paid_at
                        )
                        await session.commit()

    @tasks.loop(minutes=1)
    async def check_payments(self):
        """Check Payments"""
        payments = await self.fetch_payments()
        for payment in payments:
            await self.process_payment(payment)

    @check_payments.before_loop
    async def before_check_payments(self):
        """Before Check Payments"""
        await self.bot.wait_until_ready()


def setup(bot: commands.Bot):
    """Setup Function"""
    bot.add_cog(TipoPayments(bot))
