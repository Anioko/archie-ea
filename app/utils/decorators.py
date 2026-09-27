"""
Security decorators for route protection.
"""
from functools import wraps

from flask import abort
from flask_login import current_user


def admin_required(f):
    """
    Decorator to require admin role for accessing routes.
    Use after @login_required decorator.

    Usage:
        @app.route('/admin/dashboard')
        @login_required
        @admin_required
        def admin_dashboard():
            ...
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # Unauthorized

        # Check for admin role (supports multiple attribute names).
        #
        # `User.is_admin` is a METHOD (app/models/user.py:208), so the previous
        # `getattr(current_user, "is_admin", False)` returned the bound method -
        # always truthy - and this decorator therefore never denied anyone. Each
        # candidate is now resolved and *called* when callable, so a method, a
        # property and a plain attribute all evaluate to their real value.
        def _truthy(attr):
            value = getattr(current_user, attr, False)
            if callable(value):
                try:
                    return bool(value())
                except Exception:
                    return False
            return bool(value)

        is_admin = (
            _truthy("is_admin")
            or _truthy("is_superuser")
            or getattr(current_user, "role", None) == "admin"
        )

        if not is_admin:
            abort(403)  # Forbidden

        return f(*args, **kwargs)

    return decorated_function
