"""
Standardised JSON API response helpers for PROD-019.

All API error responses should use api_error() to return a consistent envelope:
    {"error": "<message>", "code": "<MACHINE_CODE>", "status": <http_status>}
"""

from flask import jsonify


def api_error(message: str, code: str = "ERROR", status: int = 400, **extra):
    """Return a standardised JSON error response.

    Args:
        message: Human-readable error description.
        code:    Machine-readable error code (upper-snake-case convention).
        status:  HTTP status code (default 400).
        **extra: Optional additional fields merged into the response payload
                 (e.g. ``errors=validation_result["errors"]``).
    """
    payload = {"error": message, "code": code, "status": status}
    if extra:
        payload.update(extra)
    return jsonify(payload), status


def api_success(data=None, message: str = None, status: int = 200):
    """Return a standardised JSON success response.

    Args:
        data:    Optional payload to include under the ``"data"`` key.
        message: Optional human-readable success message.
        status:  HTTP status code (default 200).
    """
    payload: dict = {"status": status}
    if data is not None:
        payload["data"] = data
    if message:
        payload["message"] = message
    return jsonify(payload), status
