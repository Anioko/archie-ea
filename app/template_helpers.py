"""
Template helper functions for robust URL building and currency formatting
"""

from typing import Optional, Union

from flask import current_app, url_for
from werkzeug.routing import BuildError

from app.services.currency_service import CurrencyService


def safe_url_for(endpoint, **values):
    """Safely build URL with fallback for missing endpoints"""
    try:
        return url_for(endpoint, **values)
    except BuildError:
        # Return a fallback URL or # for missing endpoints
        return "#"


def safe_url_for_with_fallback(endpoint, fallback_url="#", **values):
    """Safely build URL with custom fallback"""
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return fallback_url


def register_template_filters(app):
    """Register all template filters with the Flask app"""

    @app.template_filter("currency")
    def currency_filter(amount: Union[int, float, str], currency_code: Optional[str] = None) -> str:
        """
        Format amount with proper currency symbol and formatting

        Usage in templates:
        {{ amount | currency }}
        {{ amount | currency('USD') }}
        """
        if currency_code == "":
            currency_code = None
        service = CurrencyService(app)
        return service.format_currency(amount, currency_code)

    @app.template_filter("currency_symbol")
    def currency_symbol_filter(currency_code: Optional[str] = None) -> str:
        """
        Get just the currency symbol

        Usage in templates:
        {{ '' | currency_symbol }}
        {{ '' | currency_symbol('USD') }}
        """
        if currency_code == "":
            currency_code = None
        service = CurrencyService(app)
        return service.get_currency_symbol(currency_code)

    @app.template_filter("currency_name")
    def currency_name_filter(currency_code: Optional[str] = None) -> str:
        """
        Get the full currency name

        Usage in templates:
        {{ '' | currency_name }}
        {{ '' | currency_name('USD') }}
        """
        if currency_code == "":
            currency_code = None
        service = CurrencyService(app)
        return service.get_currency_name(currency_code)

    @app.template_filter("currency_api")
    def currency_api_filter(
        amount: Union[int, float, str], currency_code: Optional[str] = None
    ) -> dict:
        """
        Format currency data for API responses

        Usage in templates:
        {{ amount | currency_api }}
        {{ amount | currency_api('USD') }}
        """
        if currency_code == "":
            currency_code = None
        service = CurrencyService(app)
        return service.format_for_api(amount, currency_code)

    @app.template_filter("currency_clean")
    def currency_clean_filter(amount_string: str, currency_code: Optional[str] = None) -> float:
        """
        Parse numeric amount from a formatted currency string

        Usage in templates:
        {{ "$1,234.56" | currency_clean('USD') }}
        """
        if currency_code == "":
            currency_code = None
        service = CurrencyService(app)
        return service.parse_amount_from_string(amount_string, currency_code)

    @app.template_filter("number_format")
    def number_format_filter(number: Union[int, float], decimal_places: int = 2) -> str:
        """
        Format number with thousands separator and decimal places

        Usage in templates:
        {{ number | number_format }}
        {{ number | number_format(3) }}
        """
        try:
            if isinstance(number, str):
                number = float(number)
            return f"{number:,.{decimal_places}f}"
        except (ValueError, TypeError):
            return str(number)

    @app.template_filter("percent")
    def percent_filter(number: Union[int, float], decimal_places: int = 1) -> str:
        """
        Format number as percentage

        Usage in templates:
        {{ 0.1234 | percent }}
        {{ 0.1234 | percent(2) }}
        """
        try:
            if isinstance(number, str):
                number = float(number)
            return f"{number * 100:.{decimal_places}f}%"
        except (ValueError, TypeError):
            return str(number)

    @app.template_filter("ordinal")
    def ordinal_filter(number: Union[int, str]) -> str:
        """
        Convert number to ordinal (1st, 2nd, 3rd, etc.)

        Usage in templates:
        {{ 1 | ordinal }}  # -> "1st"
        {{ 2 | ordinal }}  # -> "2nd"
        {{ 3 | ordinal }}  # -> "3rd"
        """
        try:
            if isinstance(number, str):
                number = int(number)

            if 10 <= number % 100 <= 20:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")

            return f"{number}{suffix}"
        except (ValueError, TypeError):
            return str(number)

    @app.template_filter("file_size")
    def file_size_filter(size_bytes: Union[int, float]) -> str:
        """
        Format bytes in human readable file size

        Usage in templates:
        {{ 1024 | file_size }}  # -> "1.0 KB"
        {{ 1048576 | file_size }}  # -> "1.0 MB"
        """
        try:
            if isinstance(size_bytes, str):
                size_bytes = float(size_bytes)

            if size_bytes == 0:
                return "0 B"

            size_names = ["B", "KB", "MB", "GB", "TB"]
            i = 0
            while size_bytes >= 1024.0 and i < len(size_names) - 1:
                size_bytes /= 1024.0
                i += 1

            return f"{size_bytes:.1f} {size_names[i]}"
        except (ValueError, TypeError):
            return str(size_bytes)

    @app.template_filter("truncate_words")
    def truncate_words_filter(text: str, num_words: int = 50, suffix: str = "...") -> str:
        """
        Truncate text to specified number of words

        Usage in templates:
        {{ long_text | truncate_words(20) }}
        {{ long_text | truncate_words(20, " [more]") }}
        """
        if not text:
            return text

        words = text.split()
        if len(words) <= num_words:
            return text

        return " ".join(words[:num_words]) + suffix

    @app.template_filter("slugify")
    def slugify_filter(text: str) -> str:
        """
        Convert text to URL-friendly slug

        Usage in templates:
        {{ "Hello World!" | slugify }}  # -> "hello-world"
        """
        import re

        # Convert to lowercase and replace spaces with hyphens
        slug = re.sub(r"[^\w\s-]", "", text.lower())
        slug = re.sub(r"[\s-]+", "-", slug)
        return slug.strip("-")

    # Global template functions
    @app.context_processor
    def currency_context():
        """Make currency functions available globally in templates"""
        service = CurrencyService(app)

        return {
            "currency_service": service,
            "get_currency_symbol": service.get_currency_symbol,
            "get_currency_name": service.get_currency_name,
            "get_supported_currencies": service.get_supported_currencies,
            "get_supported_currency_codes": service.get_supported_currency_codes,
            "is_supported_currency": service.is_supported_currency,
            "default_currency": current_app.config.get("DEFAULT_CURRENCY", "GBP"),
        }


# Alias for backward compatibility
register_currency_filters = register_template_filters
