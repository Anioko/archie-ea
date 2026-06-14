"""
Core validation package.

Provides declarative validation for request payloads and query parameters
used by new modular architecture endpoints.

Modules:
- schemas: Declarative field-level validation (required, type, range, regex)
- query: Query parameter extraction and validation

Usage::

    from app.core.validation import validate_payload, validate_query
    from app.core.validation.schemas import Schema, StringField, IntField
"""

from .query import validate_query
from .schemas import Schema, validate_payload

__all__ = [
    "Schema",
    "validate_payload",
    "validate_query",
]
