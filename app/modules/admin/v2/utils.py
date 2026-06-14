"""
Admin v2 utility helpers.

Shared helpers for the admin v2 module routes.
"""
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def format_admin_flash(success: bool, entity: str, action: str) -> Tuple[str, str]:
    """Build a consistent flash message + category for admin operations.

    Args:
        success: Whether the operation succeeded.
        entity: Human-readable entity name (e.g. "User", "Feature flag").
        action: Past-tense verb (e.g. "created", "deleted").

    Returns:
        (message, category) tuple suitable for ``flash(message, category)``.
    """
    if success:
        return f"{entity} {action} successfully.", "success"
    return f"Failed to {action.rstrip('ed')} {entity.lower()}. Please try again.", "error"


def safe_int_param(value: Any, default: int = 0, min_val: Optional[int] = None,
                   max_val: Optional[int] = None) -> int:
    """Safely parse an integer parameter with optional bounds.

    Args:
        value: Raw value (from request.args, JSON payload, etc.).
        default: Fallback if parsing fails.
        min_val: Optional lower bound (inclusive).
        max_val: Optional upper bound (inclusive).

    Returns:
        Parsed and clamped integer.
    """
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default

    if min_val is not None:
        result = max(result, min_val)
    if max_val is not None:
        result = min(result, max_val)
    return result


def mask_api_key(key: str, visible_prefix: int = 8, visible_suffix: int = 4) -> str:
    """Mask an API key for safe display.

    Args:
        key: The raw API key string.
        visible_prefix: Number of leading characters to keep visible.
        visible_suffix: Number of trailing characters to keep visible.

    Returns:
        Masked string like ``sk-proj-AB...wxyz``.
    """
    if not key:
        return ""
    if len(key) <= visible_prefix + visible_suffix:
        return "****"
    return key[:visible_prefix] + "..." + key[-visible_suffix:]


def paginate_query(query, page: int = 1, per_page: int = 10):
    """Apply pagination to a SQLAlchemy query with safe defaults.

    Args:
        query: SQLAlchemy BaseQuery.
        page: 1-indexed page number.
        per_page: Items per page.

    Returns:
        Pagination object.
    """
    page = safe_int_param(page, default=1, min_val=1)
    per_page = safe_int_param(per_page, default=10, min_val=1, max_val=100)
    return query.paginate(page=page, per_page=per_page, error_out=False)
