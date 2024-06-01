from datetime import datetime, timezone


def calculate_refund(expiration_date: datetime, price: int) -> int:
    """
    Calculate the refund amount for a role based on the remaining time.

    :param expiration_date: The expiration date of the role.
    :param price: The price of the role.
    :return: The refund amount.
    """
    now = datetime.now(timezone.utc)
    if expiration_date.tzinfo is None:
        expiration_date = expiration_date.replace(tzinfo=timezone.utc)
    remaining_days = (expiration_date - now).days
    if remaining_days <= 0:
        return 0

    total_months = remaining_days // 30
    extra_days = remaining_days % 30

    refund_amount_for_months = price * total_months / 2
    refund_amount_for_days = price * extra_days / 30 / 2

    total_refund = int(refund_amount_for_months + refund_amount_for_days)
    return total_refund
