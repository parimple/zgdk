"""Interfaces for currency conversion and management."""

from abc import ABC, abstractmethod


class ICurrencyService(ABC):
    """Interface for currency conversion operations."""

    @abstractmethod
    def get_currency_unit(self) -> str:
        """Get the currency unit symbol."""

    @abstractmethod
    def get_pln_to_g_ratio(self) -> float:
        """Get the PLN to G conversion ratio."""

    @abstractmethod
    def g_to_pln(self, amount_g: int) -> int:
        """
        Convert G to PLN with special rounding rules.

        Args:
            amount_g: Amount in G currency

        Returns:
            Amount in PLN with proper rounding
        """

    @abstractmethod
    def pln_to_g(self, amount_pln: float) -> int:
        """
        Convert PLN to G currency.

        Args:
            amount_pln: Amount in PLN

        Returns:
            Amount in G currency
        """

    @abstractmethod
    def format_currency(self, amount: int, show_unit: bool = True) -> str:
        """
        Format currency amount for display.

        Args:
            amount: Amount to format
            show_unit: Whether to include currency unit

        Returns:
            Formatted currency string
        """

    @abstractmethod
    def validate_amount(self, amount: int) -> bool:
        """
        Validate if currency amount is valid.

        Args:
            amount: Amount to validate

        Returns:
            True if amount is valid
        """
