"""
SYS-009: Standardized JSON response envelope helpers.

Provides `api_success` and `api_error` for consistent
{success, data/error} envelopes across all API routes.
"""

from flask import jsonify


def api_success(data=None, message=None, status_code=200):
    """Return a standardized success envelope."""
    resp = {"success": True}
    if data is not None:
        resp["data"] = data
    if message:
        resp["message"] = message
    return jsonify(resp), status_code


def api_error(error, status_code=400):
    """Return a standardized error envelope."""
    return jsonify({"success": False, "error": str(error)}), status_code
