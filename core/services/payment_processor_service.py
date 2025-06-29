"""Payment processor service for handling external payment integrations."""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

from core.interfaces.premium_interfaces import IPaymentProcessor, PaymentData
from core.repositories.premium_repository import PaymentRepository
from core.services.base_service import BaseService

logger = logging.getLogger(__name__)


class PaymentProcessorService(BaseService, IPaymentProcessor):
    """Service for processing payments from external providers."""

    TIPPLY_API_URL = (
        "https://widgets.tipply.pl/LATEST_MESSAGES/"
        "c86c2291-6d68-4ce7-b54c-e13330f0f6c2/"
        "fb60faaf-197d-4dfb-9f2b-cce6edb00793"
    )

    def __init__(self, payment_repository: PaymentRepository, **kwargs):
        super().__init__(**kwargs)
        self.payment_repository = payment_repository
        self.premium_service = None  # Will be set externally to avoid circular dependency

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate payment processing operations."""
        return True

    async def fetch_recent_payments(self) -> list[PaymentData]:
        """Fetch recent payments from Tipply API."""
        try:
            self._log_operation("fetch_recent_payments_start")

            # First try HTTP API
            payments = await self._fetch_payments_via_http()
            if payments:
                self._log_operation("fetch_recent_payments_http", count=len(payments))
                return payments

            # Fallback to browser scraping if HTTP fails
            payments = await self._fetch_payments_via_browser()
            self._log_operation("fetch_recent_payments_browser", count=len(payments))
            return payments

        except Exception as e:
            self._log_error("fetch_recent_payments", e)
            return []

    async def _fetch_payments_via_http(self) -> list[PaymentData]:
        """Fetch payments using HTTP client."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.TIPPLY_API_URL)
                response.raise_for_status()

                # Parse HTML response
                soup = BeautifulSoup(response.text, "html.parser")
                return self._parse_payments_from_html(soup)

        except Exception as e:
            self._log_error("fetch_payments_via_http", e)
            return []

    async def _fetch_payments_via_browser(self) -> list[PaymentData]:
        """Fetch payments using browser automation (fallback)."""
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.warning("Playwright not available, browser automation disabled")
            return []
            
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-web-security",
                        "--disable-features=VizDisplayCompositor",
                    ],
                )

                try:
                    page = await browser.new_page()
                    await page.goto(self.TIPPLY_API_URL, wait_until="networkidle")

                    # Wait for content to load
                    await asyncio.sleep(2)

                    # Get page content and parse
                    content = await page.content()
                    soup = BeautifulSoup(content, "html.parser")

                    return self._parse_payments_from_html(soup)

                finally:
                    await browser.close()

        except Exception as e:
            self._log_error("fetch_payments_via_browser", e)
            return []

    def _parse_payments_from_html(self, soup: BeautifulSoup) -> list[PaymentData]:
        """Parse payment data from HTML soup."""
        payments = []

        try:
            # Look for payment elements (adjust selectors based on actual HTML structure)
            payment_elements = soup.find_all("div", class_="payment-item")  # Example selector

            for element in payment_elements:
                try:
                    payment = self._extract_payment_data(element)
                    if payment:
                        payments.append(payment)
                except Exception as e:
                    self._log_error("parse_payment_element", e)
                    continue

        except Exception as e:
            self._log_error("parse_payments_from_html", e)

        return payments

    def _extract_payment_data(self, element) -> Optional[PaymentData]:
        """Extract payment data from HTML element."""
        try:
            # Extract payment information (adjust based on actual HTML structure)
            name_elem = element.find("span", class_="payment-name")
            amount_elem = element.find("span", class_="payment-amount")
            date_elem = element.find("span", class_="payment-date")

            if not all([name_elem, amount_elem, date_elem]):
                return None

            name = name_elem.get_text(strip=True)
            amount_text = amount_elem.get_text(strip=True)
            date_text = date_elem.get_text(strip=True)

            # Parse amount (remove currency symbols, convert to int)
            amount_match = re.search(r"(\d+(?:\.\d+)?)", amount_text)
            if not amount_match:
                return None
            amount = int(float(amount_match.group(1)))

            # Parse date
            paid_at = self._parse_payment_date(date_text)
            if not paid_at:
                return None

            return PaymentData(
                name=name,
                amount=amount,
                paid_at=paid_at,
                payment_type="tipply",
                converted_amount=amount,
            )

        except Exception as e:
            self._log_error("extract_payment_data", e)
            return None

    def _parse_payment_date(self, date_text: str) -> Optional[datetime]:
        """Parse payment date from text."""
        try:
            # Handle different date formats
            date_formats = [
                "%Y-%m-%d %H:%M:%S",
                "%d.%m.%Y %H:%M",
                "%d/%m/%Y %H:%M",
                "%Y-%m-%d",
            ]

            for fmt in date_formats:
                try:
                    return datetime.strptime(date_text.strip(), fmt)
                except ValueError:
                    continue

            return None

        except Exception as e:
            self._log_error("parse_payment_date", e, date_text=date_text)
            return None

    def set_premium_service(self, premium_service) -> None:
        """Set premium service to avoid circular dependency."""
        self.premium_service = premium_service

    async def process_payment(self, payment: PaymentData) -> tuple[bool, str]:
        """Process a single payment and assign premium benefits."""
        try:
            if not self.premium_service:
                return False, "Premium service not initialized"

            # Check if already handled
            if await self.is_payment_handled(payment):
                return True, "Płatność już została przetworzona"

            # Process through premium service
            (
                success,
                message,
                member,
            ) = await self.premium_service.handle_premium_payment(payment)

            # Mark as handled regardless of success/failure
            await self.mark_payment_as_handled(payment, processing_result="success" if success else "failed")

            member_id = member.id if member else None
            self._log_operation(
                "process_payment",
                payment_name=payment.name,
                amount=payment.amount,
                success=success,
                member_id=member_id,
            )

            return success, message

        except Exception as e:
            self._log_error("process_payment", e, payment_name=payment.name)
            # Still mark as handled to prevent reprocessing
            await self.mark_payment_as_handled(payment, processing_result="error")
            return False, f"Błąd przetwarzania płatności: {str(e)}"

    async def is_payment_handled(self, payment: PaymentData) -> bool:
        """Check if payment has already been processed."""
        try:
            return await self.payment_repository.is_payment_handled(payment.name, payment.amount, payment.paid_at)
        except Exception as e:
            self._log_error("is_payment_handled", e, payment_name=payment.name)
            return False

    async def mark_payment_as_handled(self, payment: PaymentData, processing_result: str = "success") -> bool:
        """Mark payment as processed."""
        try:
            member_id = self.extract_member_id(payment.name)

            return await self.payment_repository.mark_payment_as_handled(
                payment_name=payment.name,
                amount=payment.amount,
                paid_at=payment.paid_at,
                member_id=member_id,
                processing_result=processing_result,
            )
        except Exception as e:
            self._log_error("mark_payment_as_handled", e, payment_name=payment.name)
            return False

    def extract_member_id(self, payment_name: str) -> Optional[int]:
        """Extract Discord member ID from payment name."""
        try:
            # Look for Discord ID pattern (17-19 digits)
            match = re.search(r"\b(\d{17,19})\b", payment_name)
            if match:
                member_id = int(match.group(1))
                self._log_operation("extract_member_id", payment_name=payment_name, member_id=member_id)
                return member_id

            self._log_operation("extract_member_id_failed", payment_name=payment_name)
            return None

        except Exception as e:
            self._log_error("extract_member_id", e, payment_name=payment_name)
            return None

    def calculate_premium_benefits(self, amount: int) -> Optional[tuple[str, int]]:
        """Calculate premium role and duration from payment amount."""
        try:
            # Standard premium role pricing
            premium_mappings = {
                50: ("zG50", 30),
                100: ("zG100", 30),
                500: ("zG500", 30),
                1000: ("zG1000", 30),
            }

            # Check for exact matches first
            if amount in premium_mappings:
                role, days = premium_mappings[amount]
                self._log_operation("calculate_premium_benefits", amount=amount, role=role, days=days)
                return role, days

            # Check for partial payments or custom amounts
            # This could be extended based on business logic
            closest_amount = min(premium_mappings.keys(), key=lambda x: abs(x - amount))
            if abs(closest_amount - amount) <= 5:  # Allow 5 unit tolerance
                role, days = premium_mappings[closest_amount]
                # Adjust days based on actual amount
                adjusted_days = int(days * (amount / closest_amount))
                self._log_operation(
                    "calculate_premium_benefits_adjusted",
                    amount=amount,
                    role=role,
                    days=adjusted_days,
                )
                return role, adjusted_days

            self._log_operation("calculate_premium_benefits_failed", amount=amount)
            return None

        except Exception as e:
            self._log_error("calculate_premium_benefits", e, amount=amount)
            return None

    async def process_batch_payments(self, max_payments: int = 50) -> dict[str, int]:
        """Process a batch of recent payments."""
        try:
            payments = await self.fetch_recent_payments()
            if not payments:
                return {"fetched": 0, "processed": 0, "successful": 0, "failed": 0}

            # Limit to max_payments to prevent overwhelming
            payments = payments[:max_payments]

            processed = 0
            successful = 0
            failed = 0

            for payment in payments:
                try:
                    success, message = await self.process_payment(payment)
                    processed += 1
                    if success:
                        successful += 1
                    else:
                        failed += 1

                    # Small delay to prevent rate limiting
                    await asyncio.sleep(0.1)

                except Exception as e:
                    self._log_error("process_payment_in_batch", e, payment_name=payment.name)
                    failed += 1

            result = {
                "fetched": len(payments),
                "processed": processed,
                "successful": successful,
                "failed": failed,
            }

            self._log_operation("process_batch_payments", **result)
            return result

        except Exception as e:
            self._log_error("process_batch_payments", e)
            return {"error": 1}
