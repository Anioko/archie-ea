"""
Model Validators

Reusable validators for SQLAlchemy models.

Usage:
    from sqlalchemy.orm import validates
    from app.models.validators import (
        validate_email, validate_percentage, validate_url,
        validate_enum, validate_positive_int, validate_rating
    )

    class MyModel(db.Model):
        email = db.Column(db.String(255))
        coverage = db.Column(db.Integer)

        @validates('email')
        def validate_email_field(self, key, value):
            return validate_email(value, key)

        @validates('coverage')
        def validate_coverage_field(self, key, value):
            return validate_percentage(value, key)
"""

import re
from typing import List, Optional, Union

# =============================================================================
# Email Validation
# =============================================================================

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_email(value: Optional[str], field_name: str = "email") -> Optional[str]:
    """
    Validate email format.

    Args:
        value: Email string to validate
        field_name: Name of field for error messages

    Returns:
        Lowercase email if valid, None if value is None

    Raises:
        ValueError: If email format is invalid
    """
    if value is None:
        return None

    value = value.strip().lower()

    if not EMAIL_PATTERN.match(value):
        raise ValueError(f"Invalid {field_name} format: '{value}'")

    return value


# =============================================================================
# URL Validation
# =============================================================================

URL_PATTERN = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def validate_url(value: Optional[str], field_name: str = "url") -> Optional[str]:
    """
    Validate URL format (must start with http:// or https://).

    Args:
        value: URL string to validate
        field_name: Name of field for error messages

    Returns:
        Validated URL or None

    Raises:
        ValueError: If URL format is invalid
    """
    if value is None or value.strip() == "":
        return None

    value = value.strip()

    if not URL_PATTERN.match(value):
        raise ValueError(f"Invalid {field_name}: must start with http:// or https://")

    return value


# =============================================================================
# Numeric Validators
# =============================================================================


def validate_percentage(
    value: Optional[Union[int, float]], field_name: str = "percentage"
) -> Optional[Union[int, float]]:
    """
    Validate that a value is between 0 and 100.

    Args:
        value: Numeric value to validate
        field_name: Name of field for error messages

    Returns:
        Validated value or None

    Raises:
        ValueError: If value is outside 0 - 100 range
    """
    if value is None:
        return None

    if value < 0 or value > 100:
        raise ValueError(f"{field_name} must be between 0 and 100, got {value}")

    return value


def validate_positive_int(value: Optional[int], field_name: str = "value") -> Optional[int]:
    """
    Validate that a value is a positive integer.

    Args:
        value: Integer to validate
        field_name: Name of field for error messages

    Returns:
        Validated value or None

    Raises:
        ValueError: If value is negative
    """
    if value is None:
        return None

    if not isinstance(value, int):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be an integer")

    if value < 0:
        raise ValueError(f"{field_name} must be positive, got {value}")

    return value


def validate_rating(
    value: Optional[int], min_val: int = 1, max_val: int = 5, field_name: str = "rating"
) -> Optional[int]:
    """
    Validate a rating within a range (default 1 - 5).

    Args:
        value: Rating value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        field_name: Name of field for error messages

    Returns:
        Validated rating or None

    Raises:
        ValueError: If rating is outside the range
    """
    if value is None:
        return None

    if value < min_val or value > max_val:
        raise ValueError(f"{field_name} must be between {min_val} and {max_val}, got {value}")

    return value


def validate_monetary(
    value: Optional[Union[int, float]], field_name: str = "amount"
) -> Optional[float]:
    """
    Validate a monetary value (non-negative, rounded to 2 decimal places).

    Args:
        value: Monetary value to validate
        field_name: Name of field for error messages

    Returns:
        Validated value rounded to 2 decimal places, or None

    Raises:
        ValueError: If value is negative
    """
    if value is None:
        return None

    if value < 0:
        raise ValueError(f"{field_name} cannot be negative")

    return round(float(value), 2)


# =============================================================================
# Enum/Choice Validators
# =============================================================================


def validate_enum(
    value: Optional[str],
    allowed_values: List[str],
    field_name: str = "value",
    case_insensitive: bool = False,
) -> Optional[str]:
    """
    Validate that a value is in an allowed list.

    Args:
        value: Value to validate
        allowed_values: List of allowed values
        field_name: Name of field for error messages
        case_insensitive: If True, comparison is case-insensitive

    Returns:
        Validated value or None

    Raises:
        ValueError: If value is not in allowed list
    """
    if value is None:
        return None

    check_value = value.lower() if case_insensitive else value
    check_allowed = [v.lower() for v in allowed_values] if case_insensitive else allowed_values

    if check_value not in check_allowed:
        allowed_str = ", ".join(f"'{v}'" for v in allowed_values)
        raise ValueError(f"Invalid {field_name}: '{value}'. Must be one of: {allowed_str}")

    # Return the original case-matched value if case insensitive
    if case_insensitive:
        for av in allowed_values:
            if av.lower() == check_value:
                return av

    return value


# =============================================================================
# String Validators
# =============================================================================


def validate_not_empty(value: Optional[str], field_name: str = "value") -> Optional[str]:
    """
    Validate that a string is not empty or whitespace-only.

    Args:
        value: String to validate
        field_name: Name of field for error messages

    Returns:
        Trimmed string or None

    Raises:
        ValueError: If string is empty or whitespace-only
    """
    if value is None:
        return None

    value = value.strip()

    if not value:
        raise ValueError(f"{field_name} cannot be empty")

    return value


def validate_max_length(
    value: Optional[str], max_length: int, field_name: str = "value"
) -> Optional[str]:
    """
    Validate that a string doesn't exceed a maximum length.

    Args:
        value: String to validate
        max_length: Maximum allowed length
        field_name: Name of field for error messages

    Returns:
        Validated string or None

    Raises:
        ValueError: If string exceeds max_length
    """
    if value is None:
        return None

    if len(value) > max_length:
        raise ValueError(f"{field_name} exceeds maximum length of {max_length} characters")

    return value


def validate_slug(value: Optional[str], field_name: str = "slug") -> Optional[str]:
    """
    Validate a URL-safe slug (lowercase, alphanumeric, hyphens).

    Args:
        value: Slug to validate
        field_name: Name of field for error messages

    Returns:
        Lowercase validated slug or None

    Raises:
        ValueError: If slug contains invalid characters
    """
    if value is None:
        return None

    value = value.lower().strip()

    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", value):
        raise ValueError(
            f"Invalid {field_name}: must contain only lowercase letters, "
            f"numbers, and hyphens (no leading/trailing/consecutive hyphens)"
        )

    return value


# =============================================================================
# Date Validators
# =============================================================================

from datetime import date, datetime


def validate_date_range(
    start_date: Optional[date],
    end_date: Optional[date],
    start_field: str = "start_date",
    end_field: str = "end_date",
) -> bool:
    """
    Validate that start date is before or equal to end date.

    Args:
        start_date: Start date
        end_date: End date
        start_field: Name of start field for error messages
        end_field: Name of end field for error messages

    Returns:
        True if valid

    Raises:
        ValueError: If end date is before start date
    """
    if start_date is None or end_date is None:
        return True

    if end_date < start_date:
        raise ValueError(f"{end_field} ({end_date}) cannot be before {start_field} ({start_date})")

    return True


def validate_future_date(value: Optional[date], field_name: str = "date") -> Optional[date]:
    """
    Validate that a date is in the future.

    Args:
        value: Date to validate
        field_name: Name of field for error messages

    Returns:
        Validated date or None

    Raises:
        ValueError: If date is not in the future
    """
    if value is None:
        return None

    today = (
        date.today()
        if isinstance(value, date) and not isinstance(value, datetime)
        else datetime.now().date()
    )

    if value <= today:
        raise ValueError(f"{field_name} must be in the future")

    return value


# =============================================================================
# Composite Validators
# =============================================================================


def validate_code(
    value: Optional[str], prefix: Optional[str] = None, field_name: str = "code"
) -> Optional[str]:
    """
    Validate a code format (uppercase alphanumeric with optional prefix).

    Examples: 'CAP - 001', 'APP - 123', 'TECH - 456'

    Args:
        value: Code to validate
        prefix: Required prefix (e.g., 'CAP', 'APP')
        field_name: Name of field for error messages

    Returns:
        Uppercase validated code or None

    Raises:
        ValueError: If code format is invalid
    """
    if value is None:
        return None

    value = value.upper().strip()

    if prefix:
        if not value.startswith(f"{prefix}-"):
            raise ValueError(f"{field_name} must start with '{prefix}-'")

    # Validate format: PREFIX-NUMBERS or just alphanumeric
    if not re.match(r"^[A-Z0-9]+-\d+$|^[A-Z0-9]+$", value):
        raise ValueError(
            f"Invalid {field_name} format: '{value}'. "
            f"Expected format like 'PREFIX - 123' or alphanumeric"
        )

    return value
