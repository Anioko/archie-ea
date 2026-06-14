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

        # Check for admin role (supports multiple attribute names)
        is_admin = (
            getattr(current_user, "is_admin", False)
            or getattr(current_user, "is_superuser", False)
            or (hasattr(current_user, "role") and current_user.role == "admin")
        )

        if not is_admin:
            abort(403)  # Forbidden

        return f(*args, **kwargs)

    return decorated_function
