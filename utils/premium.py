"""Module for managing premium payments and wallet"""

import json
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright  # pylint: disable=import-error
from sqlalchemy.exc import IntegrityError

from datasources.queries import HandledPaymentQueries, MemberQueries

TIPPLY_API_URL = (
    "https://widgets.tipply.pl/LATEST_MESSAGES/"
    "c86c2291-6d68-4ce7-b54c-e13330f0f6c2/"
    "fb60faaf-197d-4dfb-9f2b-cce6edb00793"
)
logger = logging.getLogger(__name__)


@dataclass
class PaymentData:
    """Data class for payment information."""

    name: str
    amount: int
    paid_at: datetime
    payment_type: str
    converted_amount: Optional[int] = None


class PremiumManager:
    """Class for managing premium payments and wallet"""

    def __init__(self, bot):
        self.bot = bot
        self.guild = None  # Inicjalizujemy jako None, będzie ustawione później
        self.config = bot.config

    def set_guild(self, guild: discord.Guild):
        """Set the guild for the PremiumManager. Must be called before processing payments."""
        logger.info("Setting guild for PremiumManager: %s", guild.id if guild else None)
        self.guild = guild

    def extract_id(self, text: str) -> Optional[int]:
        """Extract ID from various formats"""
        match = re.search(r"\b\d{17,19}\b", text)
        return int(match.group()) if match else None

    async def get_banned_member(self, name_or_id: str) -> Optional[discord.User]:
        """Get banned Member by ID or exact name"""
        if not self.guild:
            logger.error("Guild is not set in get_banned_member. Skipping ban check.")
            return None

        user_id = self.extract_id(name_or_id)
        if user_id:
            try:
                user = discord.Object(id=user_id)
                ban_entry = await self.guild.fetch_ban(user)
                if ban_entry:
                    logger.info("User is banned by ID: %s", ban_entry.user.id)
                    return ban_entry.user
            except discord.NotFound:
                logger.info("User is not banned by ID: %s", user_id)
            except discord.Forbidden:
                logger.error("Bot doesn't have permission to fetch bans")
            except Exception as e:
                logger.error("Error checking ban by ID: %s", str(e))
            return None  # Jeśli nie znaleziono bana po ID, od razu zwracamy None

        # Próbujemy po nazwie tylko jeśli nie podano ID
        try:
            ban_list = [entry async for entry in self.guild.bans()]
            for ban_entry in ban_list:
                if name_or_id.lower() == ban_entry.user.name.lower():
                    logger.info(
                        "Banned user found by exact name: %s", ban_entry.user.id
                    )
                    return ban_entry.user
        except discord.Forbidden:
            logger.error("Bot doesn't have permission to fetch bans")
        except Exception as e:
            logger.error("Error fetching bans: %s", str(e))

        return None

    async def get_member(self, name_or_id: str) -> Optional[discord.Member]:
        """Get Member by ID or Username"""
        # Try to extract an ID
        user_id = self.extract_id(name_or_id)
        if user_id:
            logger.info("get_member_id: %s is digit", user_id)
            try:
                member = await self.guild.fetch_member(user_id)
                if member:
                    return member
            except discord.NotFound:
                logger.info("Member not found with ID: %s", user_id)

        # Try to get member by exact name or display name (case-insensitive)
        logger.info("get_member_id: %s from guild: %s", name_or_id, self.guild)
        name_or_id_lower = name_or_id.lower()
        for member in self.guild.members:
            if (
                (member.name and name_or_id_lower == member.name.lower())
                or (
                    member.display_name
                    and name_or_id_lower == member.display_name.lower()
                )
                or (
                    member.global_name
                    and name_or_id_lower == member.global_name.lower()
                )
            ):
                return member

        # Try to search for partial match in display name, username or global name
        # for member in self.guild.members:
        #     if ((member.name and name_or_id_lower in member.name.lower()) or
        #         (member.display_name and name_or_id_lower in member.display_name.lower()) or
        #         (member.global_name and name_or_id_lower in member.global_name.lower())):
        #         return member

        logger.warning(f"Member not found: {name_or_id}")
        return None

    @staticmethod
    def add_premium_roles_to_embed(ctx, embed, premium_roles):
        """Add premium roles to the provided embed."""
        for member_role, role in premium_roles:
            formatted_date = discord.utils.format_dt(member_role.expiration_date, "D")
            relative_date = discord.utils.format_dt(member_role.expiration_date, "R")
            embed.add_field(
                name=f"Rola premium: {role.name}",
                value=f"Do: {formatted_date} ({relative_date})",
                inline=False,
            )

    async def process_data(self, session, payment_data: PaymentData) -> None:
        """Process Payment"""
        if not self.guild:
            logger.error(
                "Guild is not set in process_data. Cannot process payment: %s",
                payment_data,
            )
            return

        logger.info("Processing payment: %s", payment_data)
        # First, try to find the banned member
        banned_member = await self.get_banned_member(payment_data.name)
        if banned_member:
            logger.info("unban: %s", banned_member)
            await self.guild.unban(banned_member)
            await self.notify_unban(banned_member)
            payment = await HandledPaymentQueries.add_payment(
                session,
                banned_member.id,
                payment_data.name,
                payment_data.amount,
                payment_data.paid_at,
                payment_data.payment_type,
            )
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

                # Najpierw sprawdź konwersję legacy i ustal finalną kwotę
                final_amount = payment_data.amount
                if self.bot.config.get("legacy_system", {}).get("enabled", False):
                    legacy_amounts = self.bot.config.get("legacy_system", {}).get(
                        "amounts", {}
                    )
                    if final_amount in legacy_amounts:
                        # Najpierw konwertuj na nową kwotę
                        final_amount = legacy_amounts[final_amount]
                        # Losowo dodaj +1 (50% szans)
                        add_one = random.choice([True, False])
                        if add_one:
                            final_amount += 1
                        payment_data.converted_amount = final_amount
                        logger.info(
                            f"Legacy amount converted: {payment_data.amount} -> {final_amount} (add_one={add_one})"
                        )

                # Sprawdź czy finalna kwota pasuje do jakiejś roli premium
                is_premium_payment = False
                for role_config in self.bot.config["premium_roles"]:
                    if final_amount in [role_config["price"], role_config["price"] + 1]:
                        is_premium_payment = True
                        logger.info(
                            f"Found premium role match for amount {final_amount}"
                        )
                        break

                # Dodaj do portfela tylko jeśli to nie jest płatność za rolę premium
                if not is_premium_payment:
                    logger.info(
                        f"No premium role match for amount {final_amount}, adding to wallet: {payment_data.amount}"
                    )
                    await MemberQueries.add_to_wallet_balance(
                        session, member.id, payment_data.amount
                    )
            else:
                logger.warning("Member not found for payment: %s", payment_data.name)
                payment = await HandledPaymentQueries.add_payment(
                    session,
                    None,
                    payment_data.name,
                    payment_data.amount,
                    payment_data.paid_at,
                    payment_data.payment_type,
                )
                await self.notify_member_not_found(payment_data.name)

        try:
            await session.flush()
        except IntegrityError as e:
            logger.error(f"IntegrityError during payment processing: {str(e)}")
            await session.rollback()
            # Handle the error appropriately, maybe retry or notify admin
        except Exception as e:
            logger.error(f"Unexpected error during payment processing: {str(e)}")
            await session.rollback()
            # Handle other exceptions

    async def notify_unban(self, member):
        """Send notification about unban"""
        channel_id = self.config["channels"]["donation"]
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
        channel_id = self.config["channels"]["donation"]
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

    async def get_data(self, session):
        """Retrieve data for the payment processor."""
        raise NotImplementedError()


class CommandDataProvider(DataProvider):
    """Data provider for command-based inputs."""

    def __init__(self, command_data):
        self.command_data = command_data

    async def get_data(self, session):
        # Here you can convert command data into the correct format
        return self.command_data


class TipplyDataProvider(DataProvider):
    """Data provider for Tipply-based inputs."""

    def __init__(self, get_db):
        self.get_db = get_db
        self.widget_url = TIPPLY_API_URL
        self.payment_type = "tipply"

    async def fetch_payments(self) -> list[PaymentData]:
        """Fetch Payments from the Tipply widget"""
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch()
                page = await browser.new_page()
                await page.goto(self.widget_url)
                await page.wait_for_selector(".ListItemWrapper-sc-1ode8mk-0")
                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")
                payments = []
                for div in soup.find_all(
                    "div",
                    {"class": "ListItemWrapper-sc-1ode8mk-0 eYIAvf single-element"},
                ):
                    name = div.find("span", {"data-element": "nickname"}).text
                    amount_str = div.find(
                        "span", {"data-element": "price"}
                    ).text.replace(",", ".")
                    amount_str = amount_str.replace(" zł", "")
                    # Konwertujemy na grosze, zaokrąglamy w górę jeśli >= 99 groszy, w dół jeśli mniej
                    amount_groszy = round(float(amount_str) * 100)
                    amount = (
                        (amount_groszy + 99) // 100
                        if amount_groszy % 100 >= 99
                        else amount_groszy // 100
                    )
                    payment_time = datetime.now(timezone.utc)
                    payment_data = PaymentData(
                        name, amount, payment_time, self.payment_type
                    )
                    payments.append(payment_data)
                await browser.close()
            return payments
        except Exception as e:
            logger.error(f"Error fetching payments: {str(e)}")
            return []

    async def get_data(self, session):
        try:
            # Fetch all payments from the Tipply widget
            all_payments = await self.fetch_payments()
            if not all_payments:
                return []

            # Get the 10 last handled payments of type "tipply"
            async with self.get_db() as session:
                last_handled_payments = await HandledPaymentQueries.get_last_payments(
                    session, offset=0, limit=10, payment_type=self.payment_type
                )
            logger.debug("last_handled_payments: %s", last_handled_payments[:3])

            # Transform both lists to contain only (name, amount) tuples
            all_payments = [(payment.name, payment.amount) for payment in all_payments]
            last_handled_payments = [
                (payment.name, payment.amount) for payment in last_handled_payments
            ]
            logger.debug("all_payments: %s", all_payments[:3])

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
                payment_data_list.append(
                    PaymentData(name, amount, payment_time, self.payment_type)
                )

            if payment_data_list:
                logger.info("Found %d new payments", len(payment_data_list))

            return payment_data_list
        except Exception as e:
            logger.error(f"Error in get_data: {str(e)}")
            return []


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

    async def get_data(self, session):
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


class PremiumRole:
    def __init__(self, config: dict):
        self.name = config["name"]
        self.price = config["price"]
        self.features = config.get("features", [])
        self.team_size = config.get("team_size", 0)
        self.moderator_count = config.get("moderator_count", 0)
        self.points_multiplier = config.get("points_multiplier", 0)
        self.emojis_access = config.get("emojis_access", False)

    def get_description(self) -> str:
        description = "\n".join([f"• {feature}" for feature in self.features])
        if self.team_size > 0:
            description += f"\n\nRozmiar drużyny: {self.team_size} osób"
        if self.moderator_count > 0:
            description += f"\nLiczba moderatorów: {self.moderator_count}"
        if self.points_multiplier > 0:
            description += f"\nPremia do punktów: +{self.points_multiplier}%"
        return description
