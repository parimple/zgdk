"""Refund calculation utilities."""
from datetime import datetime, timezone


def calculate_refund(expiration_date: datetime, role_price: int) -> int:
    """Calculate refund amount for a role based on remaining time."""
    now = datetime.now(timezone.utc)
    if expiration_date <= now:
        return 0

    remaining_days = (expiration_date - now).days
    daily_price = role_price / 30  # Assuming monthly price
    refund = int(remaining_days * daily_price)
    return max(0, refund)
