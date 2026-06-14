"""
Core error handling package.

Re-exports the exception hierarchy from ``app/exceptions.py`` and error
handlers from ``app/utils/error_handlers.py`` so new code can import from
``app.core.errors``.

Usage::

    from app.core.errors import FlaskShadcnException, ValidationError
    from app.core.errors.handlers import register_error_handlers, safe_route
    from app.core.errors.exception_handlers import register_guardrail_error_handlers
"""

from app.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    FlaskShadcnException,
    MissingRequiredFieldError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

from .exception_handlers import register_guardrail_error_handlers

__all__ = [
    "FlaskShadcnException",
    "ValidationError",
    "MissingRequiredFieldError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ConflictError",
    "BusinessRuleError",
    "RateLimitError",
    "register_guardrail_error_handlers",
]
