"""
Authentication and Authorization Decorators for Architecture Assistant
Sprint 1.1: Authentication & Authorization

USAGE:
    from app.auth.decorators import login_required, requires_permission

    @bp.route('/api/architecture-assistant/design-solution', methods=['POST'])
    @login_required
    @requires_permission('architecture.create')
    def design_solution():
        tenant_id = current_user.tenant_id
        user_id = current_user.id
        # ... your code
"""

from functools import wraps

from flask import g, jsonify
from flask_login import current_user
from flask_login import login_required as flask_login_required


def login_required(f):
    """Wrapper around Flask-Login with custom JSON error handling"""

    @wraps(f)
    @flask_login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return (
                jsonify(
                    {
                        "error": "Authentication required",
                        "message": "You must be logged in to access this resource",
                    }
                ),
                401,
            )
        return f(*args, **kwargs)

    return decorated_function


def requires_permission(permission_name):
    """Check if current user has a specific permission"""

    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.has_permission(permission_name):
                return (
                    jsonify(
                        {
                            "error": "Insufficient permissions",
                            "message": f'You need "{permission_name}" permission',
                            "required_permission": permission_name,
                        }
                    ),
                    403,
                )
            return f(*args, **kwargs)

        return decorated_function

    return decorator
