"""
RBACService — org-scoped role-based access control (COM-007).

Role hierarchy: org_admin (2) > architect (1) > viewer (0).

Usage:
    from app.services.rbac_service import rbac_service

    @rbac_service.require_role('org_admin')
    def my_view():
        ...
"""

import functools

from flask import abort
from flask_login import current_user

ROLE_HIERARCHY = {
    "org_admin": 2,
    "architect": 1,
    "viewer": 0,
}


class RBACService:
    """Service for evaluating org-scoped RBAC permissions."""

    def get_user_role(self, org_id, user_id):
        """Return the user's role in the org. Defaults to 'viewer' if no row exists."""
        from app.models.org_role import OrgRole

        role = OrgRole.get_role(org_id, user_id)
        return role if role else "viewer"

    def is_org_admin(self, org_id, user_id):
        """True if the user is an org_admin in the given org.

        Checks both the OrgRole table (team/invitation grants) and
        user.is_admin() (Permission.ADMINISTER, the system of record).
        The two must agree; this accessor returns True if either says yes
        so that every consumer shares one authority.

        The user.is_admin() fallback is scoped to the user's own
        organisation: a user who holds the Administrator role in org A
        is NOT treated as org-admin of org B.
        """
        if self.get_user_role(org_id, user_id) == "org_admin":
            return True
        from app import db
        from app.models.user import User

        user = db.session.get(User, user_id)  # tenant-scoping-ok: primary-key lookup, not a list
        if user is not None and user.is_admin() and user.organization_id == org_id:
            return True
        return False

    def can_edit(self, org_id, user_id):
        """True if role is org_admin or architect (hierarchy level >= 1)."""
        role = self.get_user_role(org_id, user_id)
        return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY["architect"]

    def can_view(self, org_id, user_id):
        """True for all authenticated users — viewer is the minimum role."""
        return True

    def require_role(self, min_role):
        """
        Flask decorator factory that enforces a minimum org role.

        Returns 403 if current_user is not authenticated or their role is below min_role.

        Example:
            @app.route('/admin/settings')
            @login_required
            @rbac_service.require_role('org_admin')
            def admin_settings():
                ...
        """

        def decorator(f):
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                if not current_user.is_authenticated:
                    abort(403)
                org_id = getattr(current_user, "organization_id", None)
                if org_id is None:
                    abort(403)
                actual_role = self.get_user_role(org_id, current_user.id)
                min_level = ROLE_HIERARCHY.get(min_role, 0)
                actual_level = ROLE_HIERARCHY.get(actual_role, 0)
                if actual_level < min_level:
                    abort(403)
                return f(*args, **kwargs)

            return wrapper

        return decorator


rbac_service = RBACService()
