"""
Currency Service - Centralized currency formatting and management

This service provides a unified way to handle currency formatting,
symbol display, and currency conversion across the application.
"""

import locale
from typing import Optional, Union

from flask import current_app

from config import CurrencyConfig


class CurrencyService:
    """Service for handling currency formatting and management"""

    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the service with Flask app"""
        app.config.setdefault("CURRENCY_CONFIG", CurrencyConfig)
        app.config.setdefault("DEFAULT_CURRENCY", CurrencyConfig.DEFAULT_CURRENCY)

    def format_currency(
        self, amount: Union[int, float, str], currency_code: Optional[str] = None
    ) -> str:
        """
        Format amount with proper currency symbol and formatting

        Args:
            amount: The monetary amount to format
            currency_code: Currency code (defaults to app default)

        Returns:
            Formatted currency string with symbol

        Raises:
            ValueError: If currency_code is not supported
        """
        if currency_code is None:
            currency_code = current_app.config.get("DEFAULT_CURRENCY", "GBP")

        # Convert string to float if needed
        if isinstance(amount, str):
            try:
                amount = float(amount)
            except ValueError:
                raise ValueError(f"Invalid amount: {amount}")

        # Get currency configuration
        currency_config = CurrencyConfig.get_currency_config(currency_code)

        # Format the amount with proper decimal places
        formatted_amount = f"{amount:,.{currency_config['decimal_places']}f}"

        # Apply thousands separator if needed (replacing default comma)
        if currency_config["thousands_separator"] != ",":
            formatted_amount = formatted_amount.replace(",", currency_config["thousands_separator"])

        # Add symbol in correct position
        if currency_config["position"] == "prefix":
            return f"{currency_config['symbol']}{formatted_amount}"
        else:
            return f"{formatted_amount}{currency_config['symbol']}"

    def get_currency_symbol(self, currency_code: Optional[str] = None) -> str:
        """
        Get just the currency symbol

        Args:
            currency_code: Currency code (defaults to app default)

        Returns:
            Currency symbol string
        """
        if currency_code is None:
            currency_code = current_app.config.get("DEFAULT_CURRENCY", "GBP")

        currency_config = CurrencyConfig.get_currency_config(currency_code)
        return currency_config["symbol"]

    def get_currency_name(self, currency_code: Optional[str] = None) -> str:
        """
        Get the full currency name

        Args:
            currency_code: Currency code (defaults to app default)

        Returns:
            Currency name string
        """
        if currency_code is None:
            currency_code = current_app.config.get("DEFAULT_CURRENCY", "GBP")

        currency_config = CurrencyConfig.get_currency_config(currency_code)
        return currency_config["name"]

    def is_supported_currency(self, currency_code: str) -> bool:
        """
        Check if a currency code is supported

        Args:
            currency_code: Currency code to check

        Returns:
            True if supported, False otherwise
        """
        return CurrencyConfig.is_supported(currency_code)

    def get_supported_currencies(self) -> dict:
        """
        Get all supported currencies with their details

        Returns:
            Dictionary of supported currencies
        """
        return CurrencyConfig.SUPPORTED_CURRENCIES.copy()

    def get_supported_currency_codes(self) -> list:
        """
        Get list of all supported currency codes

        Returns:
            List of currency codes
        """
        return CurrencyConfig.get_all_supported_codes()

    def parse_amount_from_string(
        self, amount_string: str, currency_code: Optional[str] = None
    ) -> float:
        """
        Parse numeric amount from a formatted currency string

        Args:
            amount_string: Formatted currency string (e.g., "£1,234.56")
            currency_code: Currency code for parsing context

        Returns:
            Numeric amount as float

        Raises:
            ValueError: If amount cannot be parsed
        """
        if currency_code is None:
            currency_code = current_app.config.get("DEFAULT_CURRENCY", "GBP")

        currency_config = CurrencyConfig.get_currency_config(currency_code)

        # Remove currency symbol
        clean_string = amount_string.replace(currency_config["symbol"], "")

        # Remove thousands separator
        clean_string = clean_string.replace(currency_config["thousands_separator"], "")

        # Convert to float
        try:
            return float(clean_string)
        except ValueError:
            raise ValueError(f"Cannot parse amount from: {amount_string}")

    def format_for_api(
        self, amount: Union[int, float, str], currency_code: Optional[str] = None
    ) -> dict:
        """
        Format currency data for API responses

        Args:
            amount: The monetary amount
            currency_code: Currency code

        Returns:
            Dictionary with formatted currency data
        """
        if currency_code is None:
            currency_code = current_app.config.get("DEFAULT_CURRENCY", "GBP")

        # Convert to float for consistency
        if isinstance(amount, str):
            try:
                amount = float(amount)
            except ValueError:
                raise ValueError(f"Invalid amount: {amount}")

        return {
            "amount": amount,
            "currency_code": currency_code,
            "formatted_amount": self.format_currency(amount, currency_code),
            "symbol": self.get_currency_symbol(currency_code),
            "name": self.get_currency_name(currency_code),
        }

    def validate_currency_code(self, currency_code: str) -> bool:
        """
        Validate currency code format and support

        Args:
            currency_code: Currency code to validate

        Returns:
            True if valid and supported
        """
        if not isinstance(currency_code, str):
            return False

        if len(currency_code) != 3:
            return False

        return self.is_supported_currency(currency_code)


# Global service instance
currency_service = CurrencyService()
