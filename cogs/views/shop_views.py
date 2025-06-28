"""Import all shop views from the modular structure.

This module re-exports all shop views to maintain backward compatibility.
"""

# Re-export all views from the modular structure
from .shop import (
    PaymentsView,
    RoleShopView,
    BuyRoleButton,
    RoleDescriptionView,
    ConfirmView,
    LowerRoleChoiceView
)

# Re-export constants for backward compatibility
from .shop.constants import MONTHLY_DURATION, YEARLY_DURATION, YEARLY_MONTHS

__all__ = [
    "PaymentsView",
    "RoleShopView", 
    "BuyRoleButton",
    "RoleDescriptionView",
    "ConfirmView",
    "LowerRoleChoiceView",
    "MONTHLY_DURATION",
    "YEARLY_DURATION",
    "YEARLY_MONTHS"
]