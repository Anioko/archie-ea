"""
Pagination utilities for consistent pagination across all endpoints.
Provides validation and bounds checking for pagination parameters.
"""
from typing import Tuple

from flask import request


def get_pagination_params(
    default_per_page: int = 20, max_per_page: int = 100, min_per_page: int = 1
) -> Tuple[int, int]:
    """
    Get and validate pagination parameters from request.

    Ensures consistent pagination limits across all endpoints to prevent
    performance issues from excessive page sizes.

    Args:
        default_per_page: Default items per page if not specified
        max_per_page: Maximum allowed items per page (prevents abuse)
        min_per_page: Minimum allowed items per page

    Returns:
        Tuple of (page, per_page) with validated values

    Example:
        page, per_page = get_pagination_params(default_per_page=20, max_per_page=100)
        pagination = Model.query.paginate(page=page, per_page=per_page, error_out=False)
    """
    try:
        # Get page number (must be >= 1)
        page = safe_int_arg('page', 1, minimum=1)
        page = max(1, page)  # Ensure page is at least 1

        # Get per_page with bounds checking
        per_page = int(request.args.get("per_page", default_per_page))
        per_page = max(min_per_page, min(per_page, max_per_page))  # Clamp between min and max

        return page, per_page

    except (ValueError, TypeError):
        # Invalid parameters - return defaults
        return 1, default_per_page


def get_pagination_dict(page: int, per_page: int, total: int, pages: int) -> dict:
    """
    Create standardized pagination response dictionary.

    Args:
        page: Current page number
        per_page: Items per page
        total: Total number of items
        pages: Total number of pages

    Returns:
        Dictionary with pagination metadata
    """
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }


# Hard ceiling for any page-size parameter parsed by ``safe_int_arg``.
#
# Rationale: the largest default page size in the codebase is 1000 (bulk
# export endpoints), and a single page above a few hundred rows is already a
# latency problem rather than a useful response. 500 sits above every
# interactive default in the app while still bounding the worst case a hostile
# caller can ask for. Call sites whose own default exceeds this pass an
# explicit, higher ``maximum`` so the cap never silently shrinks an existing
# contract.
MAX_PAGE_SIZE = 500


def safe_int_arg(name, default, minimum=None, maximum=None, args=None):
    """Read an integer query-string parameter without ever raising.

    Hostile or malformed input (``?page=abc``, ``?limit=``, ``?limit=-1``,
    a repeated or absurdly large value) must produce an honest, in-range
    number, not a 500. Anything that does not parse as an integer falls back
    to ``default``; anything that parses is then clamped into
    ``[minimum, maximum]``.

    Args:
        name: query-string parameter name.
        default: value used when the parameter is absent or unparseable.
        minimum: inclusive lower bound (e.g. 1 for ``page``, 0 for ``offset``).
        maximum: inclusive upper bound (e.g. ``MAX_PAGE_SIZE`` for page sizes).
        args: mapping to read from; defaults to ``flask.request.args``.

    Returns:
        int: a value guaranteed to satisfy the supplied bounds.
    """
    source = args if args is not None else getattr(request, "args", None)
    raw = None
    if source is not None:
        try:
            raw = source.get(name)
        except Exception:  # pragma: no cover - defensive, non-mapping source
            raw = None

    if raw is None or str(raw).strip() == "":
        value = default
    else:
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            value = default

    if value is None:
        # The call site's own default was None (meaning "unset"); preserve that
        # rather than inventing a number it never asked for.
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None

    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value
