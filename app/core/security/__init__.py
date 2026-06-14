"""
Core security package.

Consolidates security utilities from ``app/utils/`` into a single namespace:

- **rate_limiter** — Unified base class + re-exports of ADM, AI, Import limiters
- **csrf** — CSRF helper utilities (require_csrf decorator)
- **input_validator** — Input validation (string, JSON, XSS prevention)
- **file_validator** — File upload MIME-type validation
- **error_sanitizer** — Safe error messages for user-facing responses
- **content_safety** — Content safety filtering (placeholder for AI guardrails)

Usage::

    from app.core.security import ErrorSanitizer, require_csrf
    from app.core.security.input_validator import validate_string
    from app.core.security.rate_limiter import RateLimiterBase
"""

from .csrf import require_csrf
from .error_sanitizer import ErrorSanitizer
from .input_validator import ValidationError, validate_string

__all__ = [
    "require_csrf",
    "ErrorSanitizer",
    "ValidationError",
    "validate_string",
]
