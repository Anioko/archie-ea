"""
API Response Standardization Utilities

Provides standardized response formats for all API endpoints
following PRD - 003: API Response Standardization requirements.
"""

import uuid
from datetime import datetime

from flask import jsonify


def success_response(data, status_code=200, meta=None):
    """
    Create a standardized success response.

    Args:
        data: The response data payload
        status_code: HTTP status code (default: 200)
        meta: Additional metadata to include in response

    Returns:
        tuple: (jsonified_response, status_code)
    """
    response = {
        "success": True,
        "data": data,
        "meta": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1.0",
            "request_id": str(uuid.uuid4()),
            **(meta or {}),
        },
    }
    return jsonify(response), status_code


def error_response(message, code="ERROR", details=None, status_code=400):
    """
    Create a standardized error response.

    Args:
        message: User-friendly error message
        code: Error code string (default: "ERROR")
        details: Additional error details object
        status_code: HTTP status code (default: 400)

    Returns:
        tuple: (jsonified_response, status_code)
    """
    response = {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
        "meta": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1.0",
            "request_id": str(uuid.uuid4()),
        },
    }
    return jsonify(response), status_code


def validation_error_response(errors, message="Validation failed"):
    """
    Create a standardized validation error response.

    Args:
        errors: Dict or list of validation errors
        message: Error message (default: "Validation failed")

    Returns:
        tuple: (jsonified_response, 400)
    """
    return error_response(message=message, code="VALIDATION_ERROR", details=errors, status_code=400)


def not_found_response(resource="Resource"):
    """
    Create a standardized not found error response.

    Args:
        resource: Name of the resource that was not found

    Returns:
        tuple: (jsonified_response, 404)
    """
    return error_response(message=f"{resource} not found", code="NOT_FOUND", status_code=404)


def unauthorized_response(message="Authentication required"):
    """
    Create a standardized unauthorized error response.

    Args:
        message: Error message (default: "Authentication required")

    Returns:
        tuple: (jsonified_response, 401)
    """
    return error_response(message=message, code="UNAUTHORIZED", status_code=401)


def forbidden_response(message="Access denied"):
    """
    Create a standardized forbidden error response.

    Args:
        message: Error message (default: "Access denied")

    Returns:
        tuple: (jsonified_response, 403)
    """
    return error_response(message=message, code="FORBIDDEN", status_code=403)


def server_error_response(message="Internal server error", details=None):
    """
    Create a standardized server error response.

    Args:
        message: Error message (default: "Internal server error")
        details: Additional error details

    Returns:
        tuple: (jsonified_response, 500)
    """
    return error_response(
        message=message, code="INTERNAL_SERVER_ERROR", details=details, status_code=500
    )


def deprecated_response(new_endpoint, message=None):
    """
    Create a standardized deprecation response.

    Args:
        new_endpoint: The new endpoint to use instead
        message: Custom deprecation message

    Returns:
        tuple: (jsonified_response, 301)
    """
    if message is None:
        message = f"This endpoint is deprecated. Please use {new_endpoint} instead."

    return error_response(
        message=message, code="DEPRECATED", details={"new_endpoint": new_endpoint}, status_code=200
    )
