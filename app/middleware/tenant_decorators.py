"""
Tenant-aware authorization decorators.

@org_admin_required — user must be authenticated + is_org_admin for their org
@platform_admin_required — user must be authenticated + is_platform_admin
"""

from functools import wraps

from flask import abort, jsonify, request
from flask_login import current_user, login_required


def _wants_json():
    return (
        "/api/" in request.path
        or request.content_type == "application/json"
        or request.accept_mimetypes.best == "application/json"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )


def org_admin_required(f):
    """Require authenticated user who is an org admin."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not getattr(current_user, "is_org_admin", False):
            if _wants_json():
                return jsonify({"error": "Organization admin access required"}), 403
            abort(403)
        return f(*args, **kwargs)
    return decorated


def platform_admin_required(f):
    """Require authenticated user who is a platform admin (cross-org access)."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not getattr(current_user, "is_platform_admin", False):
            if _wants_json():
                return jsonify({"error": "Platform admin access required"}), 403
            abort(403)
        return f(*args, **kwargs)
    return decorated
