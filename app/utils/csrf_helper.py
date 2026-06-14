"""
CSRF Helper Utilities

This module provides utilities to ensure CSRF protection is properly implemented
across all forms and AJAX requests in the application.
"""

from functools import wraps

from flask import current_app, request
from flask_wtf.csrf import CSRFError, validate_csrf


def require_csrf(f):
    """
    Decorator to explicitly require CSRF token validation for a route.
    Use this when you want to ensure CSRF is validated even if the route
    is exempted elsewhere.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Check for CSRF token in form data or headers
            token = None
            if request.is_json:
                token = request.headers.get("X-CSRFToken")
            else:
                token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")

            if not token:
                return {"error": "CSRF token missing"}, 400

            validate_csrf(token)
        except CSRFError as e:
            current_app.logger.warning(f"CSRF validation failed: {e}")
            return {"error": f"CSRF validation failed: {str(e)}"}, 403

        return f(*args, **kwargs)

    return decorated_function


def get_csrf_token():
    """
    Get the current CSRF token for use in templates or JavaScript.
    """
    from flask_wtf.csrf import generate_csrf

    return generate_csrf()


def csrf_token_required():
    """
    Check if CSRF token is present and valid in the current request.
    Returns (is_valid, error_message)
    """
    try:
        token = None
        if request.is_json:
            token = request.headers.get("X-CSRFToken")
        else:
            token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")

        if not token:
            return False, "CSRF token missing"

        validate_csrf(token)
        return True, None
    except CSRFError as e:
        return False, str(e)
