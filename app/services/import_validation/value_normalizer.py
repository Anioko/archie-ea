"""
Value normalization for import data.
Maps common variations to canonical values and handles null patterns.
"""

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

from .validation_schemas import (
    APPLICATION_COMPONENT_SCHEMA,
    NULL_VALUE_PATTERNS,
    FieldSchema,
    FieldType,
    get_alias_mapping,
)


class ValueNormalizer:
    """Normalizes raw import values to canonical forms"""

    @staticmethod
    def is_null_value(value: Any) -> bool:
        """Check if value represents a null/empty value"""
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in NULL_VALUE_PATTERNS
        return False

    @staticmethod
    def normalize_value(
        value: Any, field_name: str, schema: Optional[FieldSchema] = None
    ) -> Tuple[Any, Optional[str]]:
        """
        Normalize a single value based on field schema.

        Args:
            value: Raw value from import
            field_name: Name of the field
            schema: Optional field schema (looked up if not provided)

        Returns:
            Tuple of (normalized_value, warning_message)
            warning_message is None if no normalization was needed
        """
        if schema is None:
            schema = APPLICATION_COMPONENT_SCHEMA.get(field_name)

        # Handle None/empty values
        if value is None:
            return None, None

        # Convert to string for pattern matching
        str_value = str(value).strip()

        # Check for null patterns
        if str_value.lower() in NULL_VALUE_PATTERNS:
            return None, None

        # Empty string after strip
        if not str_value:
            return None, None

        # No schema - just return cleaned string
        if schema is None:
            return str_value, None

        # Type-specific normalization
        if schema.field_type == FieldType.ENUM:
            return ValueNormalizer._normalize_enum(str_value, field_name, schema)
        elif schema.field_type == FieldType.STRING:
            return ValueNormalizer._normalize_string(str_value, schema)
        elif schema.field_type == FieldType.INTEGER:
            return ValueNormalizer._normalize_integer(str_value, schema)
        elif schema.field_type == FieldType.FLOAT:
            return ValueNormalizer._normalize_float(str_value, schema)
        elif schema.field_type == FieldType.BOOLEAN:
            return ValueNormalizer._normalize_boolean(str_value)
        elif schema.field_type == FieldType.DATE:
            return ValueNormalizer._normalize_date(str_value)
        elif schema.field_type == FieldType.URL:
            return ValueNormalizer._normalize_url(str_value, schema)
        elif schema.field_type == FieldType.EMAIL:
            return ValueNormalizer._normalize_email(str_value)

        return str_value, None

    @staticmethod
    def _normalize_enum(
        value: str, field_name: str, schema: FieldSchema
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Normalize enum value with smart mapping.

        Returns:
            (normalized_value, warning) - warning explains if mapping was applied
        """
        value_lower = value.lower().strip()
        allowed_values = schema.allowed_values or []

        # Direct match (case-insensitive)
        for allowed in allowed_values:
            if allowed.lower() == value_lower:
                return allowed, None

        # Check aliases
        aliases = get_alias_mapping(field_name)
        if value_lower in aliases:
            mapped_value = aliases[value_lower]
            return mapped_value, f"Mapped '{value}' to '{mapped_value}'"

        # Fuzzy match - check if value contains a valid option or vice versa
        for allowed in allowed_values:
            allowed_lower = allowed.lower()
            # Check for substring matches (but avoid too short matches)
            if len(allowed_lower) >= 4:
                if allowed_lower in value_lower or value_lower in allowed_lower:
                    return allowed, f"Fuzzy matched '{value}' to '{allowed}'"

        # No match found - return None with error indication
        valid_str = ", ".join(f"'{v}'" for v in allowed_values[:5])
        if len(allowed_values) > 5:
            valid_str += f" ... ({len(allowed_values)} total)"
        return None, f"Invalid value '{value}' for {field_name}. Valid values: {valid_str}"

    @staticmethod
    def _normalize_string(value: str, schema: FieldSchema) -> Tuple[str, Optional[str]]:
        """Normalize string value with length truncation"""
        warning = None

        if schema.max_length and len(value) > schema.max_length:
            truncated = value[: schema.max_length - 3] + "..."
            warning = f"Truncated from {len(value)} to {schema.max_length} chars"
            return truncated, warning

        return value, None

    @staticmethod
    def _normalize_integer(value: str, schema: FieldSchema) -> Tuple[Optional[int], Optional[str]]:
        """Normalize to integer"""
        try:
            # Remove commas, whitespace, and currency symbols
            cleaned = re.sub(r"[,$\s€£¥]", "", value)
            # Handle decimal strings by truncating
            if "." in cleaned:
                cleaned = cleaned.split(".")[0]
            # Handle empty result
            if not cleaned or cleaned == "-":
                return None, None
            int_val = int(cleaned)
            return int_val, None
        except (ValueError, TypeError):
            logger.warning("Dropped value '%s' during integer conversion", value)
            return None, f"Cannot convert '{value}' to integer"

    @staticmethod
    def _normalize_float(value: str, schema: FieldSchema) -> Tuple[Optional[float], Optional[str]]:
        """Normalize to float"""
        try:
            # Remove commas, whitespace, and currency symbols
            cleaned = re.sub(r"[,$\s€£¥]", "", value)
            # Handle empty result
            if not cleaned or cleaned == "-":
                return None, None
            float_val = float(cleaned)
            return float_val, None
        except (ValueError, TypeError):
            logger.warning("Dropped value '%s' during float conversion", value)
            return None, f"Cannot convert '{value}' to number"

    @staticmethod
    def _normalize_boolean(value: str) -> Tuple[Optional[bool], Optional[str]]:
        """Normalize to boolean"""
        true_values = {"true", "yes", "1", "y", "on", "enabled", "active", "x", "checked"}
        false_values = {"false", "no", "0", "n", "off", "disabled", "inactive", "", "unchecked"}

        value_lower = value.lower().strip()

        if value_lower in true_values:
            return True, None
        elif value_lower in false_values:
            return False, None
        else:
            return None, f"Cannot convert '{value}' to boolean"

    @staticmethod
    def _normalize_date(value: str) -> Tuple[Optional[date], Optional[str]]:
        """Normalize to date with multiple format support"""
        formats = [
            "%Y-%m-%d",  # ISO format
            "%d/%m/%Y",  # UK format
            "%m/%d/%Y",  # US format
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%Y.%m.%d",
            "%d.%m.%Y",
            "%B %d, %Y",  # Month name
            "%d %B %Y",
            "%b %d, %Y",  # Short month name
            "%d %b %Y",
        ]

        value_clean = value.strip()

        # Year-only values (e.g. "2024") are ambiguous — could be a version,
        # ID, or count.  Skip instead of silently converting to Jan 1.
        if value_clean.isdigit() and len(value_clean) == 4:
            logger.warning(
                "Dropped ambiguous year-only value '%s' during date conversion",
                value_clean,
            )
            return None, f"Ambiguous year-only value '{value_clean}' — use a full date format (e.g. 2024-01-01)"

        for fmt in formats:
            try:
                parsed = datetime.strptime(value_clean, fmt)
                return parsed.date(), None
            except ValueError:
                continue

        # Try dateutil as fallback
        try:
            from dateutil import parser

            parsed = parser.parse(value_clean, dayfirst=True)
            return parsed.date(), None
        except (ImportError, ValueError, TypeError):
            logger.warning(
                "Dropped value '%s' during date conversion — no format matched",
                value_clean,
            )

        return None, f"Cannot parse date '{value}'"

    @staticmethod
    def _normalize_url(value: str, schema: FieldSchema) -> Tuple[Optional[str], Optional[str]]:
        """Normalize URL"""
        value = value.strip()
        warning = None

        # Add https if missing protocol
        if value and not value.startswith(("http://", "https://")):
            if "." in value:  # Looks like a domain
                value = "https://" + value
                warning = "Added https:// prefix"

        # Basic URL validation
        url_pattern = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)

        if url_pattern.match(value):
            if schema.max_length and len(value) > schema.max_length:
                return value[: schema.max_length], f"URL truncated to {schema.max_length} chars"
            return value, warning

        return None, f"Invalid URL format: '{value}'"

    @staticmethod
    def _normalize_email(value: str) -> Tuple[Optional[str], Optional[str]]:
        """Normalize email"""
        value = value.strip().lower()

        email_pattern = re.compile(r"^[a-zA-Z0 - 9._%+-]+@[a-zA-Z0 - 9.-]+\.[a-zA-Z]{2,}$")

        if email_pattern.match(value):
            return value, None

        return None, f"Invalid email format: '{value}'"
