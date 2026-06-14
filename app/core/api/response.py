"""
Standardized API response helpers.

All API endpoints should use these functions to ensure consistent
response format across the application.

Response format:
{
    "success": true/false,
    "data": {...} or [...],
    "error": "message" (only on failure),
    "meta": {"page": 1, "per_page": 25, "total": 100} (only on paginated)
}
"""
from typing import Any, Optional

from flask import g, jsonify, request


def _get_request_id() -> Optional[str]:
    """Return the current request ID if set by observability hooks, else None."""
    try:
        return getattr(g, "request_id", None)
    except RuntimeError:
        return None


def api_success(data: Any = None, message: Optional[str] = None, status_code: int = 200):
    """Return a successful API response.

    Args:
        data: Response payload (dict, list, or None).
        message: Optional success message.
        status_code: HTTP status code (default 200).

    Returns:
        Flask JSON response tuple.
    """
    response = {"success": True}
    if data is not None:
        response["data"] = data
    if message:
        response["message"] = message
    req_id = _get_request_id()
    if req_id:
        response["request_id"] = req_id
    return jsonify(response), status_code


def api_error(message: str, status_code: int = 400, errors: Optional[dict] = None):
    """Return an error API response.

    Args:
        message: Human-readable error message.
        status_code: HTTP status code (default 400).
        errors: Optional dict of field-level errors.

    Returns:
        Flask JSON response tuple.
    """
    response = {"success": False, "error": message}
    if errors:
        response["errors"] = errors
    req_id = _get_request_id()
    if req_id:
        response["request_id"] = req_id
    return jsonify(response), status_code


def api_paginated(
    items: list,
    total: int,
    page: int,
    per_page: int,
    status_code: int = 200,
):
    """Return a paginated API response.

    Args:
        items: List of serialized items for current page.
        total: Total number of items across all pages.
        page: Current page number.
        per_page: Items per page.
        status_code: HTTP status code (default 200).

    Returns:
        Flask JSON response tuple.
    """
    body = {
        "success": True,
        "data": items,
        "meta": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        },
    }
    req_id = _get_request_id()
    if req_id:
        body["request_id"] = req_id
    return jsonify(body), status_code
