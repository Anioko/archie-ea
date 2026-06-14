"""
Legacy compatibility layer for the guardrail framework.

Provides utilities that allow legacy modules to coexist with the new guardrail
architecture without requiring immediate migration.  All functions are safe
no-ops when the new framework is disabled.

Key principles:
- Legacy modules NEVER break — their behavior is preserved as-is.
- New modules opt in to guardrails via ``@guarded_route`` or explicit calls.
- ``is_new_module()`` detects whether the current request is from a new module.
- ``legacy_safe()`` wraps a function so it falls back to legacy behavior on error.

Usage::

    from app.core.compat import is_new_module, legacy_safe, bridge_response

    if is_new_module():
        return api_success(data)
    else:
        return jsonify(data)  # legacy format

    @legacy_safe(fallback=lambda: jsonify({"error": "fallback"}), 500)
    def my_service_call():
        ...
"""

import functools
import logging
import os
from typing import Any, Callable, Optional, Tuple

from flask import jsonify, request

logger = logging.getLogger(__name__)

_NEW_MODULE_PREFIXES = ("/m/",)
_GUARDRAILS_ENABLED = os.environ.get("USE_GUARDRAILS", "true").lower() != "false"


def is_new_module() -> bool:
    """Return True if the current request targets a new-architecture module.

    Detection rules (checked in order):
    1. ``X-Module-Version: 2`` header
    2. Request path starts with ``/m/``
    3. Blueprint has ``_guardrail_enabled`` attribute
    """
    if not _GUARDRAILS_ENABLED:
        return False
    try:
        if request.headers.get("X-Module-Version") == "2":
            return True
        for prefix in _NEW_MODULE_PREFIXES:
            if request.path.startswith(prefix):
                return True
        if getattr(request, "_guardrail_enabled", False):
            return True
    except RuntimeError:
        pass
    return False


def bridge_response(data: Any, status_code: int = 200) -> Tuple:
    """Return a response in the appropriate format for the current module.

    New modules get the standardized ``{success, data, ...}`` envelope.
    Legacy modules get raw ``jsonify(data)``.
    """
    if is_new_module():
        from app.core.api import api_success

        return api_success(data, status_code=status_code)
    return jsonify(data), status_code


def bridge_error(message: str, status_code: int = 400, errors: Optional[dict] = None) -> Tuple:
    """Return an error response in the appropriate format."""
    if is_new_module():
        from app.core.api import api_error

        return api_error(message, status_code, errors=errors)
    body = {"error": message}
    if errors:
        body["errors"] = errors
    return jsonify(body), status_code


def legacy_safe(fallback_value: Any = None, log_error: bool = True) -> Callable:
    """Decorator that catches exceptions and returns a safe fallback for legacy callers.

    Use this when wiring new guardrail-aware services into legacy routes.
    The decorated function returns *fallback_value* on any exception instead
    of propagating (which could break legacy error handling).

    Args:
        fallback_value: Value to return on exception (default None).
        log_error: Whether to log the caught exception.

    Usage::

        @legacy_safe(fallback_value=[])
        def get_capabilities():
            return capability_service.list_all()
    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as exc:
                if log_error:
                    logger.warning(
                        "legacy_safe caught exception in %s: %s",
                        f.__name__,
                        str(exc),
                        exc_info=True,
                    )
                return fallback_value

        return wrapper

    return decorator


def mark_blueprint_guardrailed(bp) -> None:
    """Mark a Flask Blueprint as guardrail-enabled.

    Call this during blueprint registration for new modules so that
    ``is_new_module()`` detects requests to this blueprint.

    Usage::

        from app.core.compat import mark_blueprint_guardrailed

        bp = Blueprint("capabilities_v2", __name__, url_prefix="/m/capabilities")
        mark_blueprint_guardrailed(bp)
    """
    # Check if already marked (idempotent - safe to call multiple times)
    if hasattr(bp, '_guardrail_marked'):
        return
    
    bp._guardrail_marked = True

    @bp.before_request
    def _set_guardrail_flag():
        request._guardrail_enabled = True  # type: ignore[attr-defined]
