"""Refund calculation utilities."""
from datetime import datetime, timezone

# Configuration constants
MONTHLY_DURATION = 30  # Base duration for monthly subscription


def calculate_refund(expiration_date: datetime, role_price: int) -> int:
    """
    Calculate refund amount for a role based on remaining time.

    :param expiration_date: The expiration date of the role
    :type expiration_date: datetime
    :param role_price: The original price of the role
    :type role_price: int
    :return: The refund amount based on remaining time (full month = full price, proportional for less time)
    :rtype: int

    Examples:
        - 30 days remaining = full price
        - 15 days remaining = half price
        - Less than 15 days = proportional to remaining days
    """
    now = datetime.now(timezone.utc)
    if expiration_date <= now:
        return 0

    # Calculate remaining days
    remaining_days = (expiration_date - now).days

    # Calculate refund based on remaining days
    refund = int((remaining_days / MONTHLY_DURATION) * role_price)

    return max(0, refund)  # Ensure we don't return negative values
