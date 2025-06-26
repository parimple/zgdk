"""Currency service for handling currency conversions and formatting."""

import logging

from core.interfaces.currency_interfaces import ICurrencyService
from core.services.base_service import BaseService


class CurrencyService(BaseService, ICurrencyService):
    """Service for currency conversion operations."""

    # Currency constants
    CURRENCY_UNIT = "G"
    PLN_TO_G_RATIO = 1  # 1 PLN = 1G

    def __init__(self, **kwargs):
        # Currency service doesn't need unit_of_work for its operations
        super().__init__(unit_of_work=None, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate currency operation."""
        return True

    def get_currency_unit(self) -> str:
        """Get the currency unit symbol."""
        return self.CURRENCY_UNIT

    def get_pln_to_g_ratio(self) -> float:
        """Get the PLN to G conversion ratio."""
        return self.PLN_TO_G_RATIO

    def g_to_pln(self, amount_g: int) -> int:
        """
        Convert G to PLN with special rounding rules:
        - Values ending with .99 are rounded up
        - All other values have decimal part truncated

        Examples:
        - 998.99G -> 999 PLN
        - 999G -> 999 PLN
        - 999.70G -> 999 PLN
        - 998.98G -> 998 PLN
        
        Args:
            amount_g: Amount in G currency
            
        Returns:
            Amount in PLN with proper rounding
        """
        try:
            # Convert to PLN
            amount_pln = amount_g / self.PLN_TO_G_RATIO

            # Get integer and decimal parts
            int_part = int(amount_pln)
            decimal_part = round((amount_pln - int_part) * 100) / 100  # Round to 2 decimal places

            # Check if decimal part is exactly .99
            if decimal_part == 0.99:
                result = int_part + 1
            else:
                # For all other values, truncate
                result = int_part

            self._log_operation(
                "g_to_pln",
                amount_g=amount_g,
                amount_pln=amount_pln,
                result=result,
                decimal_part=decimal_part,
            )
            return result

        except Exception as e:
            self._log_error("g_to_pln", e, amount_g=amount_g)
            return 0

    def pln_to_g(self, amount_pln: float) -> int:
        """
        Convert PLN to G currency.
        
        Args:
            amount_pln: Amount in PLN
            
        Returns:
            Amount in G currency
        """
        try:
            result = int(amount_pln * self.PLN_TO_G_RATIO)
            self._log_operation(
                "pln_to_g",
                amount_pln=amount_pln,
                result=result,
            )
            return result

        except Exception as e:
            self._log_error("pln_to_g", e, amount_pln=amount_pln)
            return 0

    def format_currency(self, amount: int, show_unit: bool = True) -> str:
        """
        Format currency amount for display.
        
        Args:
            amount: Amount to format
            show_unit: Whether to include currency unit
            
        Returns:
            Formatted currency string
        """
        try:
            if show_unit:
                return f"{amount:,}{self.CURRENCY_UNIT}"
            else:
                return f"{amount:,}"

        except Exception as e:
            self._log_error("format_currency", e, amount=amount, show_unit=show_unit)
            return str(amount)

    def validate_amount(self, amount: int) -> bool:
        """
        Validate if currency amount is valid.
        
        Args:
            amount: Amount to validate
            
        Returns:
            True if amount is valid
        """
        try:
            # Check if amount is a non-negative integer
            is_valid = isinstance(amount, int) and amount >= 0
            
            self._log_operation(
                "validate_amount",
                amount=amount,
                is_valid=is_valid,
            )
            return is_valid

        except Exception as e:
            self._log_error("validate_amount", e, amount=amount)
            return False