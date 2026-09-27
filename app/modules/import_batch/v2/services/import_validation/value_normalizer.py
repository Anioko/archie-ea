"""
Value normalizer for import validation.

Normalizes raw cell values to their canonical form based on the field schema,
including enum alias resolution and type coercion.
"""

from typing import Any, Optional, Tuple

from .validation_schemas_v2 import (
    FieldSchema,
    FieldType,
    NULL_VALUE_PATTERNS,
    get_alias_mapping,
)


class ValueNormalizer:
    """Normalizes field values according to schema definitions."""

    @staticmethod
    def is_null_value(value: Any) -> bool:
        """Check if a value represents 'no data'."""
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in [p.lower() for p in NULL_VALUE_PATTERNS]
        return False

    def normalize_value(
        self, value: Any, field_name: str, schema: FieldSchema
    ) -> Tuple[Any, Optional[str]]:
        """
        Normalize a single field value.

        Args:
            value: Raw value from the import row.
            field_name: The field name being normalized.
            schema: The FieldSchema definition for this field.

        Returns:
            Tuple of (normalized_value, warning_or_None).
        """
        # Handle null values
        if self.is_null_value(value):
            return schema.default_value, None

        if schema.field_type == FieldType.ENUM:
            return self._normalize_enum(value, field_name, schema)
        elif schema.field_type == FieldType.STRING:
            return self._normalize_string(value, schema)
        elif schema.field_type == FieldType.INTEGER:
            return self._normalize_integer(value, field_name, schema)
        elif schema.field_type == FieldType.FLOAT:
            return self._normalize_float(value, field_name, schema)
        elif schema.field_type == FieldType.BOOLEAN:
            return self._normalize_boolean(value)
        else:
            # Pass through for unhandled types
            return str(value).strip() if isinstance(value, str) else value, None

    def _normalize_enum(
        self, value: Any, field_name: str, schema: FieldSchema
    ) -> Tuple[Any, Optional[str]]:
        """Normalize an enum value using aliases."""
        str_val = str(value).strip()
        aliases = get_alias_mapping(field_name)

        # Check exact match first
        if schema.allowed_values:
            for allowed in schema.allowed_values:
                if str_val.lower() == allowed.lower():
                    return allowed, None

        # Check alias mapping
        if str_val.lower() in aliases:
            return aliases[str_val.lower()], None

        # Try partial match
        if schema.allowed_values:
            for allowed in schema.allowed_values:
                if str_val.lower() in allowed.lower() or allowed.lower() in str_val.lower():
                    return allowed, f"Matched '{str_val}' to '{allowed}' via partial match"

        # No match found
        return None, f"Unknown value '{str_val}' for field '{field_name}'"

    def _normalize_string(
        self, value: Any, schema: FieldSchema
    ) -> Tuple[Optional[str], Optional[str]]:
        """Normalize a string value."""
        str_val = str(value).strip()
        if schema.max_length and len(str_val) > schema.max_length:
            return str_val[: schema.max_length], (
                f"Value truncated from {len(str_val)} to {schema.max_length} characters"
            )
        return str_val, None

    def _normalize_integer(
        self, value: Any, field_name: str, schema: FieldSchema
    ) -> Tuple[Optional[int], Optional[str]]:
        """Normalize an integer value."""
        try:
            int_val = int(str(value).strip().replace(",", ""))
            return int_val, None
        except (ValueError, TypeError):
            return None, f"Could not parse integer from '{value}'"

    def _normalize_float(
        self, value: Any, field_name: str, schema: FieldSchema
    ) -> Tuple[Optional[float], Optional[str]]:
        """Normalize a float value."""
        try:
            float_val = float(str(value).strip().replace(",", ""))
            return float_val, None
        except (ValueError, TypeError):
            return None, f"Could not parse float from '{value}'"

    def _normalize_boolean(
        self, value: Any,
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Normalize a boolean value."""
        if isinstance(value, bool):
            return value, None
        str_val = str(value).strip().lower()
        if str_val in ("true", "yes", "1", "y", "on"):
            return True, None
        if str_val in ("false", "no", "0", "n", "off"):
            return False, None
        return None, f"Could not parse boolean from '{value}'"