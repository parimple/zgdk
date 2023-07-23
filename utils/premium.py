"""Module for managing premium payments and wallet"""
import json
import logging
import os
from collections import namedtuple
from datetime import datetime, timedelta
from typing import Optional

import discord
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright # type: ignore

from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries

TIPO_API_URL = "https://tipo.live/api/v2/payments?token="
TIPPLY_API_URL = "https://widgets.tipply.pl/LATEST_MESSAGES/c86c2291-6d68-4ce7-b54c-e13330f0f6c2/fb60faaf-197d-4dfb-9f2b-cce6edb00793"
TOKEN = os.environ.get("TIPO_API_TOKEN")

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
        self.role_price_map = {
            900: "$2",
            1900: "$4",
            2900: "$6",
            3900: "$8",
            7900: "$16",
            15900: "$32",
            31900: "$64",
        }

    async def get_member_id(self, name: str) -> Optional[int]:
        """Get Member ID"""
        member_id = None
        if name.isdigit():
            logger.info("get_member_id: %s is digit", name)
            member_id = int(name)
            member = self.guild.get_member(member_id)
            if member is None:
                logger.info("Member not found by id: %s", name)
            else:
                return member_id
        logger.info("get_member_id: %s from guild: %s", name, self.guild)
        member = self.guild.get_member_named(name)
        if member:
            member_id = member.id
        return member_id

    async def _determine_remaining_amount(self, amount, role_name):
        """Determine the remaining amount after subtracting the role price"""
        if role_name:
            for price, name in self.role_price_map.items():
                if name == role_name:
                    return amount - price
        return amount

    async def _assign_role_to_db(self, session, member_id, role_name):
        """Assign role to the member in the database"""
        role_id = None
        if role_name:
            role = await RoleQueries.get_role_by_name(session, role_name)
            if role:
                role_id = role.id
                premium_role = await RoleQueries.get_premium_role(session, member_id)
                if premium_role and premium_role.role.role_type == "premium":
                    role_value = await self._get_role_value(role_name)
                    premium_role_value = await self._get_role_value(premium_role.role.name)
                    if (premium_role.expiration_date - datetime.now()).days <= 1:
                        # Add to wallet instead of assigning the role
                        logger.info(
                            "Added to wallet of member %s (multiple pqyments in 1 day)", member_id
                        )
                        return None
                    if role_value > premium_role_value:
                        # Delete old role and assign new role
                        session.delete(premium_role)
                        logger.info(
                            "Deleted old role and assigned new role to member %s", member_id
                        )
                        session.add(
                            RoleQueries.add_role_to_member(session, member_id, role_id, 30, "days")
                        )
                        return role_id
        return None

    async def _determine_role(self, amount):
        """Determine the role based on the payment amount"""
        sorted_role_prices = sorted(self.role_price_map.keys(), reverse=True)
        for price in sorted_role_prices:
            if amount >= price:
                return self.role_price_map[price]
        return None

    async def _get_role_value(self, role_name):
        """Get the value of the role"""
        for price, name in self.role_price_map.items():
            if name == role_name:
                return price
        return 0

    async def _assign_role_to_discord(self, member_id, role_id):
        """Assign role to the member on Discord server"""
        discord_member = self.guild.get_member(member_id)
        if discord_member and role_id:
            discord_role = discord.utils.get(self.guild.roles, id=role_id)
            if discord_role:
                # Uncomment the line below when you're ready to use this in production
                # await discord_member.add_roles(discord_role)
                logger.info("Added role %s to member %s on Discord", discord_role.name, member_id)

    async def _remove_role_from_discord(self, member_id, role_id):
        """Remove role from the member on Discord server"""
        discord_member = self.guild.get_member(member_id)
        if discord_member and role_id:
            discord_role = discord.utils.get(self.guild.roles, id=role_id)
            if discord_role:
                # Uncomment the line below when you're ready to use this in production
                # await discord_member.remove_roles(discord_role)
                logger.info(
                    "Removed role %s from member %s on Discord", discord_role.name, member_id
                )

    async def process_data(self, payment_data: PaymentData) -> None:
        """Process Payment"""
        logger.info("process payment: %s", payment_data)
        try:
            member_id = await self.get_member_id(payment_data.name)
            logger.info("member id: %s", member_id)

            async with self.session() as session:
                payment = await HandledPaymentQueries.add_payment(
                    session,
                    member_id,
                    payment_data.name,
                    payment_data.amount,
                    payment_data.paid_at,
                    payment_data.payment_type,
                )
                logger.info("payment: %s", payment)

                if member_id:
                    await MemberQueries.get_or_add_member(session, member_id)
                    await MemberQueries.add_to_wallet_balance(
                        session, member_id, payment_data.amount
                    )

                await session.commit()

            if not member_id:
                logger.info("Member not found: %s", payment_data.name)
        except Exception as err:  # pylint: disable=broad-except
            logger.error("An error occurred: %s", err)
        else:
            logger.info("Transaction committed")


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
                amount = int(float(amount_str) * 100)
                payment_time = datetime.now()

                payment_data = PaymentData(name, amount, payment_time, self.payment_type)
                payments.append(payment_data)

            await browser.close()

        return payments

    async def get_data(self):
        # Fetch all payments from the Tipply widget
        all_payments = await self.fetch_payments()

        # Get the 10 last handled payments of type "tipply"
        last_handled_payments = await HandledPaymentQueries.get_last_payments(
            self.db_session, 10, self.payment_type
        )
        logger.info("last_handled_payments: %s", last_handled_payments)

        # Transform both lists to contain only (name, amount) tuples
        all_payments = [(payment.name, payment.amount) for payment in all_payments]
        last_handled_payments = [
            (payment.name, payment.amount) for payment in last_handled_payments
        ]
        logger.info("all_payments: %s", all_payments)

        # Iterate over the fetched payments from newest to oldest
        for i in range(len(all_payments) - 10, -1, -1):
            if all_payments[i : i + 10] == last_handled_payments:
                new_payments = all_payments[:i]
                break
        else:
            # If no matching payment is found, all fetched payments are new
            new_payments = all_payments

        # Transform back to PaymentData
        current_time = datetime.now()
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
