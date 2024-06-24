"""Currency conversion utilities"""

CURRENCY_UNIT = "G"
PLN_TO_G_RATIO = 100  # 1 PLN = 100G


def g_to_pln(amount_g: int) -> float:
    """Convert G to PLN"""
    return amount_g / PLN_TO_G_RATIO


def pln_to_g(amount_pln: float) -> int:
    """Convert PLN to G"""
    return int(amount_pln * PLN_TO_G_RATIO)
