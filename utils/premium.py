"""Module for managing premium payments and wallet"""
import json
import logging
import re
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright  # pylint: disable=import-error

from datasources.queries import HandledPaymentQueries, MemberQueries

TIPPLY_API_URL = (
    "https://widgets.tipply.pl/LATEST_MESSAGES/"
    "c86c2291-6d68-4ce7-b54c-e13330f0f6c2/"
    "fb60faaf-197d-4dfb-9f2b-cce6edb00793"
)
logger = logging.getLogger(__name__)

PaymentData = namedtuple(
    "PaymentData",
    ["name", "amount", "paid_at", "payment_type"],
)


class PremiumManager:
    """Class for managing premium payments and wallet"""

    def __init__(self, session, guild):
        self.session = session
        self.guild = guild

    def extract_id(self, text: str) -> Optional[int]:
        """Extract ID from various formats"""
        match = re.search(r"\b\d{17,19}\b", text)
        return int(match.group()) if match else None

    async def get_banned_member(self, name_or_id: str) -> Optional[discord.User]:
        """Get banned Member by ID or exact name"""
        user_id = self.extract_id(name_or_id)
        if user_id:
            try:
                ban_entry = await self.guild.fetch_ban(discord.Object(id=user_id))
                if ban_entry:
                    logger.info("User is banned by ID: %s", ban_entry.user.id)
                    return ban_entry.user
            except discord.NotFound:
                logger.info("User is not banned by ID: %s", user_id)
        else:
            async for ban_entry in self.guild.bans(limit=None):
                if name_or_id.lower() == ban_entry.user.name.lower():
                    logger.info("Banned user found by exact name: %s", ban_entry.user.id)
                    return ban_entry.user

        return None

    async def get_member(self, name_or_id: str) -> Optional[discord.Member]:
        """Get Member by ID or Username"""
        # Try to extract an ID
        user_id = self.extract_id(name_or_id)
        if user_id:
            logger.info("get_member_id: %s is digit", user_id)
            member = self.guild.get_member(user_id)
            if member:
                return member

        # Try to get member by exact name or display name
        logger.info("get_member_id: %s from guild: %s", name_or_id, self.guild)
        member = self.guild.get_member_named(name_or_id)
        if member:
            return member

        # Try to search for partial match in display name or username
        for m in self.guild.members:
            if name_or_id.lower() in m.display_name.lower() or name_or_id.lower() in m.name.lower():
                return m

        return None

    @staticmethod
    def add_premium_roles_to_embed(ctx, embed, premium_roles):
        """Add premium roles to the provided embed."""
        role_ids = [role.role_id for role in premium_roles]
        expiration_dates = [
            (
                discord.utils.format_dt(role.expiration_date, "D"),
                discord.utils.format_dt(role.expiration_date, "R"),
            )
            for role in premium_roles
        ]
        for role_id, (formatted_date, relative_date) in zip(role_ids, expiration_dates):
            role_name = ctx.guild.get_role(role_id).name
            embed.add_field(
                name=f"Aktualna rola: {role_name}",
                value=f"Do: {formatted_date} ({relative_date})",
                inline=False,
            )

    async def process_data(self, payment_data: PaymentData) -> None:
        """Process Payment"""
        logger.info("process payment: %s", payment_data)
        async with self.session() as session:
            # First, try to find the banned member
            banned_member = await self.get_banned_member(payment_data.name)
            if banned_member:
                logger.info("unban: %s", banned_member)
                await self.guild.unban(banned_member)
                await self.notify_unban(banned_member)
            else:
                # If not banned, find the member in the guild
                member = await self.get_member(payment_data.name)
                if member:
                    logger.info("member id: %s", member)
                    payment = await HandledPaymentQueries.add_payment(
                        session,
                        member.id,
                        payment_data.name,
                        payment_data.amount,
                        payment_data.paid_at,
                        payment_data.payment_type,
                    )
                    logger.info("payment: %s", payment)
                    await MemberQueries.get_or_add_member(session, member.id)
                    await MemberQueries.add_to_wallet_balance(
                        session, member.id, payment_data.amount
                    )
                    logger.info("add_to_wallet_balance: %s", payment_data.amount)
                else:
                    logger.warning("Member not found for payment: %s", payment_data.name)
                    await self.notify_member_not_found(payment_data.name)
            logger.info("commit session")
            await session.commit()

    async def notify_unban(self, member):
        """Send notification about unban"""
        channel_id = self.guild.config["channels"]["donation"]
        channel = self.guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="Użytkownik odbanowany",
                description=f"Użytkownik {member.mention} został odbanowany.",
                color=discord.Color.green(),
            )
            await channel.send(embed=embed)

    async def notify_member_not_found(self, name: str):
        """Send notification about member not found"""
        channel_id = self.guild.config["channels"]["donation"]
        channel = self.guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="Użytkownik nie znaleziony",
                description=f"Nie znaleziono użytkownika o nazwie: {name}",
                color=discord.Color.red(),
            )
            await channel.send(embed=embed)


class DataProvider:
    """Base class for all data providers."""

    async def get_data(self):
        """Retrieve data for the payment processor."""
        raise NotImplementedError()


class CommandDataProvider(DataProvider):
    """Data provider for command-based inputs."""

    def __init__(self, command_data):
        self.command_data = command_data

    async def get_data(self):
        # Here you can convert command data into the correct format
        return self.command_data


class TipplyDataProvider(DataProvider):
    """Data provider for Tipply-based inputs."""

    def __init__(self, db_session):
        self.db_session = db_session
        self.widget_url = TIPPLY_API_URL
        self.payment_type = "tipply"

    async def fetch_payments(self) -> list[PaymentData]:
        """Fetch Payments from the Tipply widget"""
        logger.info("fetch_payments")

        # Fetch the widget content
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            logger.info("Browser launched")
            page = await browser.new_page()
            logger.info("New page created")
            await page.goto(self.widget_url)
            logger.info("Page loaded")

            # Wait for the specific selector to be loaded on the page
            await page.wait_for_selector(".ListItemWrapper-sc-1ode8mk-0")

            content = await page.content()
            logger.info("Content fetched")
            soup = BeautifulSoup(content, "html.parser")

            payments = []
            for div in soup.find_all(
                "div", {"class": "ListItemWrapper-sc-1ode8mk-0 eYIAvf single-element"}
            ):
                name = div.find("span", {"data-element": "nickname"}).text
                amount_str = div.find("span", {"data-element": "price"}).text.replace(",", ".")
                amount_str = amount_str.replace(" zł", "")
                amount = int(round(float(amount_str), 2) * 100)
                payment_time = datetime.now(timezone.utc)

                payment_data = PaymentData(name, amount, payment_time, self.payment_type)
                payments.append(payment_data)

            await browser.close()

        return payments

    async def get_data(self):
        # Fetch all payments from the Tipply widget
        all_payments = await self.fetch_payments()

        # Get the 10 last handled payments of type "tipply"
        last_handled_payments = await HandledPaymentQueries.get_last_payments(
            self.db_session, offset=0, limit=10, payment_type=self.payment_type
        )
        logger.info("last_handled_payments: %s", last_handled_payments[:3])

        # Transform both lists to contain only (name, amount) tuples
        all_payments = [(payment.name, payment.amount) for payment in all_payments]
        last_handled_payments = [
            (payment.name, payment.amount) for payment in last_handled_payments
        ]
        logger.info("all_payments: %s", all_payments[:3])

        # Iterate over the fetched payments from newest to oldest
        for i in range(len(all_payments) - 10, -1, -1):
            if all_payments[i : i + 10] == last_handled_payments:
                new_payments = all_payments[:i]
                break
        else:
            # If no matching payment is found, all fetched payments are new
            new_payments = all_payments

        # Transform back to PaymentData
        current_time = datetime.now(timezone.utc)
        payment_data_list = []
        for i, (name, amount) in enumerate(new_payments[::-1]):
            payment_time = current_time + timedelta(seconds=i)
            payment_data_list.append(PaymentData(name, amount, payment_time, self.payment_type))

        return payment_data_list


class TipoDataProvider(DataProvider):
    """Data provider for API-based inputs."""

    def __init__(self, api_url):
        self.api_url = api_url
        self.payment_type = "tipo"

    async def fetch_payments(self):
        """Fetch Payments from the API"""
        logger.info("Fetching payments")
        try:
            timeout = httpx.Timeout(timeout=20.0, read=20.0)
            params = {
                "sort_order": "desc",
            }
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(self.api_url, params=params)
                # raises an exception if the HTTP request returned an error status
                response.raise_for_status()
                data = response.json()
                payments = data.get("data", [])
        except httpx.HTTPError as http_err:
            logger.error("HTTP error occurred: %s", http_err)
            return []
        except json.JSONDecodeError as json_err:
            logger.error("JSON decoding error occurred: %s", json_err)
            return []
        except Exception as err:  # pylint: disable=broad-except
            logger.error("An error occurred: %s", err)
            return []
        return payments

    async def get_data(self):
        payments = await self.fetch_payments()
        processed_payments = []

        for payment in payments:
            name = payment.get("name")
            amount = payment.get("amount")
            paid_at = datetime.fromisoformat(payment["paid_at"].rstrip("Z"))

            # Create a PaymentData instance and append to the list
            payment_data = PaymentData(name, amount, paid_at, self.payment_type)
            processed_payments.append(payment_data)

        return processed_payments
