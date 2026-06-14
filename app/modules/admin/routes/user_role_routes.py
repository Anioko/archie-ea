"""
User Role Management Routes

Allows platform admins to assign enterprise roles to users.
Part of North Star Persona MVP.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import db
from app.models.user import User

# Use the existing admin blueprint - this will be imported by admin_routes
user_role_bp = Blueprint("user_role", __name__)

VALID_ENTERPRISE_ROLES = [
    "solution_architect",
    "enterprise_architect",
    "arb_member",
    "portfolio_manager",
    "cto",
    "application_manager",
    "procurement",
    "platform_admin",
]


@user_role_bp.route("/user/<int:user_id>/role", methods=["GET"])
@login_required
@admin_required
def edit_user_role(user_id):
    """Edit a user's enterprise role."""
    user = User.query.get_or_404(user_id)
    return render_template("admin/user_role_edit.html", user=user)


@user_role_bp.route("/user/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def update_user_role(user_id):
    """Update a user's enterprise role."""
    user = User.query.get_or_404(user_id)

    new_role = request.form.get("enterprise_role")

    if new_role not in VALID_ENTERPRISE_ROLES:
        flash(f"Invalid role: {new_role}", "error")
        return redirect(url_for("user_role.edit_user_role", user_id=user_id))

    old_role = user.enterprise_role
    user.enterprise_role = new_role
    db.session.commit()

    flash(f"Role updated: {old_role or 'None'} → {new_role}", "success")
    return redirect(url_for("admin.user_info", user_id=user_id))
