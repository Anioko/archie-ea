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
        page = int(request.args.get("page", 1))
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
