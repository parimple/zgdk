"""Currency conversion utilities"""

import math

CURRENCY_UNIT = "G"
PLN_TO_G_RATIO = 1  # 1 PLN = 1G


def g_to_pln(amount_g: int) -> int:
    """
    Convert G to PLN with special rounding rules:
    - Values ending with .99 are rounded up
    - All other values have decimal part truncated

    Examples:
    - 998.99G -> 999 PLN
    - 999G -> 999 PLN
    - 999.70G -> 999 PLN
    - 998.98G -> 998 PLN
    """
    # Convert to PLN
    amount_pln = amount_g / PLN_TO_G_RATIO

    # Get integer and decimal parts
    int_part = int(amount_pln)
    decimal_part = round((amount_pln - int_part) * 100) / 100  # Round to 2 decimal places

    # Check if decimal part is exactly .99
    if decimal_part == 0.99:
        return int_part + 1

    # For all other values, truncate
    return int_part


def pln_to_g(amount_pln: float) -> int:
    """Convert PLN to G"""
    return int(amount_pln * PLN_TO_G_RATIO)
