"""Refund calculation utilities."""
from datetime import datetime, timezone

# Configuration constants
MONTHLY_DURATION = 30  # Base duration for monthly subscription


def calculate_refund(expiration_date: datetime, role_price: int) -> int:
    """
    Calculate refund amount for a role based on remaining time.
    Returns half of the remaining value, rounded down to nearest integer.
    """
    now = datetime.now(timezone.utc)
    if expiration_date <= now:
        return 0

    remaining_days = (expiration_date - now).days
    # First calculate full value
    full_value = (remaining_days * role_price) // MONTHLY_DURATION  # Full value for remaining days
    # Then take half of it
    refund = full_value // 2  # Half of the value, rounded down
    return max(0, refund)
