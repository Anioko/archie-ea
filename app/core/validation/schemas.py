"""
Declarative validation schemas for request payloads.

Lightweight, framework-free validation that does NOT depend on WTForms or
marshmallow — keeps ``app/core`` dependency-light.  New modules use these
schemas; legacy modules keep their existing validation.

Usage::

    from app.core.validation.schemas import Schema, StringField, IntField, BoolField

    class CreateCapabilitySchema(Schema):
        name = StringField(required=True, min_length=1, max_length=255)
        level = IntField(required=False, min_val=0, max_val=10, default=0)
        active = BoolField(required=False, default=True)

    # In a route:
    data, errors = CreateCapabilitySchema.validate(request.get_json())
    if errors:
        return api_error("Validation failed", 400, errors=errors)
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Type


class Field:
    """Base field descriptor."""

    def __init__(
        self,
        required: bool = False,
        default: Any = None,
        description: str = "",
    ):
        self.required = required
        self.default = default
        self.description = description

    def validate(self, value: Any, field_name: str) -> Tuple[Any, Optional[str]]:
        """Validate and coerce *value*.  Return (clean_value, error_or_None)."""
        if value is None:
            if self.required:
                return None, f"'{field_name}' is required"
            return self.default, None
        return value, None


class StringField(Field):
    """String field with length and regex constraints."""

    def __init__(
        self,
        min_length: int = 0,
        max_length: int = 10_000,
        pattern: Optional[str] = None,
        strip: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        self.strip = strip

    def validate(self, value: Any, field_name: str) -> Tuple[Any, Optional[str]]:
        value, err = super().validate(value, field_name)
        if err or value is None:
            return value, err

        if not isinstance(value, str):
            return None, f"'{field_name}' must be a string"

        if self.strip:
            value = value.strip()

        if len(value) < self.min_length:
            return None, f"'{field_name}' must be at least {self.min_length} characters"
        if len(value) > self.max_length:
            return None, f"'{field_name}' must be at most {self.max_length} characters"
        if self.pattern and not re.match(self.pattern, value):
            return None, f"'{field_name}' does not match required pattern"

        return value, None


class IntField(Field):
    """Integer field with range constraints."""

    def __init__(
        self,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, value: Any, field_name: str) -> Tuple[Any, Optional[str]]:
        value, err = super().validate(value, field_name)
        if err or value is None:
            return value, err

        if isinstance(value, bool):
            return None, f"'{field_name}' must be an integer"

        try:
            value = int(value)
        except (TypeError, ValueError):
            return None, f"'{field_name}' must be an integer"

        if self.min_val is not None and value < self.min_val:
            return None, f"'{field_name}' must be >= {self.min_val}"
        if self.max_val is not None and value > self.max_val:
            return None, f"'{field_name}' must be <= {self.max_val}"

        return value, None


class FloatField(Field):
    """Float field with range constraints."""

    def __init__(
        self,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.min_val = min_val
        self.max_val = max_val

    def validate(self, value: Any, field_name: str) -> Tuple[Any, Optional[str]]:
        value, err = super().validate(value, field_name)
        if err or value is None:
            return value, err

        try:
            value = float(value)
        except (TypeError, ValueError):
            return None, f"'{field_name}' must be a number"

        if self.min_val is not None and value < self.min_val:
            return None, f"'{field_name}' must be >= {self.min_val}"
        if self.max_val is not None and value > self.max_val:
            return None, f"'{field_name}' must be <= {self.max_val}"

        return value, None


class BoolField(Field):
    """Boolean field — accepts bool, 0/1, "true"/"false"."""

    def validate(self, value: Any, field_name: str) -> Tuple[Any, Optional[str]]:
        value, err = super().validate(value, field_name)
        if err or value is None:
            return value, err

        if isinstance(value, bool):
            return value, None
        if isinstance(value, int) and value in (0, 1):
            return bool(value), None
        if isinstance(value, str) and value.lower() in ("true", "false", "1", "0"):
            return value.lower() in ("true", "1"), None

        return None, f"'{field_name}' must be a boolean"


class ListField(Field):
    """List field with optional item-type validation."""

    def __init__(
        self,
        item_type: Optional[Type] = None,
        min_items: int = 0,
        max_items: int = 10_000,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.item_type = item_type
        self.min_items = min_items
        self.max_items = max_items

    def validate(self, value: Any, field_name: str) -> Tuple[Any, Optional[str]]:
        value, err = super().validate(value, field_name)
        if err or value is None:
            return value, err

        if not isinstance(value, list):
            return None, f"'{field_name}' must be a list"

        if len(value) < self.min_items:
            return None, f"'{field_name}' must have at least {self.min_items} items"
        if len(value) > self.max_items:
            return None, f"'{field_name}' must have at most {self.max_items} items"

        if self.item_type:
            for i, item in enumerate(value):
                if not isinstance(item, self.item_type):
                    return None, f"'{field_name}[{i}]' must be {self.item_type.__name__}"

        return value, None


class EnumField(Field):
    """Field restricted to a set of allowed values."""

    def __init__(self, choices: List[Any], **kwargs):
        super().__init__(**kwargs)
        self.choices = choices

    def validate(self, value: Any, field_name: str) -> Tuple[Any, Optional[str]]:
        value, err = super().validate(value, field_name)
        if err or value is None:
            return value, err

        if value not in self.choices:
            choices_str = ", ".join(repr(c) for c in self.choices[:10])
            return None, f"'{field_name}' must be one of: {choices_str}"

        return value, None


class SchemaMeta(type):
    """Metaclass that collects Field descriptors into ``_fields``."""

    def __new__(mcs, name, bases, namespace):
        fields = {}
        for key, val in namespace.items():
            if isinstance(val, Field):
                fields[key] = val
        for base in bases:
            if hasattr(base, "_fields"):
                for k, v in base._fields.items():
                    fields.setdefault(k, v)
        namespace["_fields"] = fields
        return super().__new__(mcs, name, bases, namespace)


class Schema(metaclass=SchemaMeta):
    """Declarative validation schema.

    Subclass and define fields as class attributes.  Then call
    ``Schema.validate(data)`` to get ``(clean_data, errors)``.
    """

    _fields: Dict[str, Field] = {}

    @classmethod
    def validate(cls, data: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """Validate *data* against the schema.

        Returns:
            (clean_data, errors) — errors is empty dict on success.
        """
        if data is None:
            data = {}

        clean = {}
        errors = {}

        for field_name, field in cls._fields.items():
            raw = data.get(field_name)
            value, error = field.validate(raw, field_name)
            if error:
                errors[field_name] = error
            else:
                clean[field_name] = value

        return clean, errors

    @classmethod
    def field_names(cls) -> List[str]:
        """Return list of declared field names."""
        return list(cls._fields.keys())


def validate_payload(schema_cls: Type[Schema], data: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Convenience function — validate *data* with the given *schema_cls*."""
    return schema_cls.validate(data)
