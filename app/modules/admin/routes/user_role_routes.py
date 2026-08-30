"""
User Role Management Routes

Allows platform admins to assign enterprise roles to users.
Part of North Star Persona MVP.
"""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from flask_login import login_required

from app.decorators import admin_required
from app.extensions import db
from app.models.user import VALID_ROLES, User

# Use the existing admin blueprint - this will be imported by admin_routes
user_role_bp = Blueprint("user_role", __name__)

# Derived from the model rather than restated. This list previously omitted
# business_architect, which VALID_ROLES has always contained -- so the one role
# the picker could not offer was one the product actively assigns, and an admin
# had no way to grant it. Importing the source of truth means a role added to
# the model is assignable immediately instead of silently missing here.
VALID_ENTERPRISE_ROLES = list(VALID_ROLES)


@user_role_bp.route("/user/<int:user_id>/role", methods=["GET"])
@login_required
@admin_required
def edit_user_role(user_id):
    """Edit a user's enterprise role."""
    # admin_required is org-scoped admin, not platform_admin — restrict to the
    # current org (tenant-scoping-ok: fixes cross-org role-escalation IDOR).
    user = User.query.filter_by(id=user_id, organization_id=g.current_org_id).first_or_404()
    return render_template("admin/user_role_edit.html", user=user)


@user_role_bp.route("/user/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def update_user_role(user_id):
    """Update a user's enterprise role."""
    # admin_required is org-scoped admin, not platform_admin — restrict to the
    # current org (tenant-scoping-ok: fixes cross-org role-escalation IDOR).
    user = User.query.filter_by(id=user_id, organization_id=g.current_org_id).first_or_404()

    new_role = request.form.get("enterprise_role")

    if new_role not in VALID_ENTERPRISE_ROLES:
        flash(f"Invalid role: {new_role}", "error")
        return redirect(url_for("user_role.edit_user_role", user_id=user_id))

    old_role = user.enterprise_role
    user.enterprise_role = new_role
    db.session.commit()

    flash(f"Role updated: {old_role or 'None'} → {new_role}", "success")
    return redirect(url_for("admin.user_info", user_id=user_id))
