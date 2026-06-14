"""
Account v2 utilities.

Helper functions shared across v2 account routes.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def safe_redirect_target(next_url: Optional[str], fallback: str = "/") -> str:
    """Validate and return a safe redirect target URL.

    Prevents open redirect attacks by ensuring the target URL is relative
    (same-origin). Falls back to *fallback* if the URL is missing or
    points to an external host.

    Args:
        next_url: The candidate redirect URL (from ``request.args.get("next")``).
        fallback: Default URL if *next_url* is unsafe or missing.

    Returns:
        A safe redirect URL string.
    """
    if not next_url:
        return fallback

    # Reject absolute URLs pointing to external hosts
    if next_url.startswith("//") or "://" in next_url:
        logger.warning("Blocked open redirect attempt to: %s", next_url)
        return fallback

    # Only allow paths starting with /
    if not next_url.startswith("/"):
        return fallback

    return next_url


def format_flash_result(success: bool, message: str) -> Tuple[str, str]:
    """Convert a (success, message) service result into flash (message, category).

    Args:
        success: Whether the operation succeeded.
        message: Human-readable result message.

    Returns:
        (message, category) tuple suitable for ``flash(message, category)``.
    """
    category = "form-success" if success else "form-error"
    return message, category
