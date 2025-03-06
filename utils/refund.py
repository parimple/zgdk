"""Refund calculation utilities."""
from datetime import datetime, timezone

# Configuration constants
MONTHLY_DURATION = 30  # Base duration for monthly subscription


def calculate_refund(expiration_date: datetime, role_price: int, role_name: str = None) -> int:
    """
    Calculate refund amount for a role based on remaining time.

    :param expiration_date: The expiration date of the role
    :type expiration_date: datetime
    :param role_price: The original price of the role
    :type role_price: int
    :param role_name: The name of the role (unused, kept for backward compatibility)
    :type role_name: str
    :return: The refund amount based on remaining time
    :rtype: int

    The refund is calculated as half of the role price, proportional to the remaining days:
    - 30 days remaining = 50% of role price
    - 15 days remaining = 25% of role price
    - 23 days remaining = ~38% of role price
    """
    now = datetime.now(timezone.utc)
    if expiration_date <= now:
        return 0

    # Calculate remaining days
    remaining_days = (expiration_date - now).days

    # Calculate half of the role price
    half_price = role_price / 2

    # Calculate refund based on remaining days (proportional to half price)
    refund = int((remaining_days / MONTHLY_DURATION) * half_price)

    return max(0, refund)  # Ensure we don't return negative values
