"""
Team management routes — org member listing and role management (COM-007).

Blueprint: team_bp  |  URL prefix: /admin  |  All routes: org_admin only
"""

import logging

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models.user import User
from app.models.org_role import OrgRole, VALID_ORG_ROLES
from app.services.rbac_service import rbac_service

logger = logging.getLogger(__name__)

team_bp = Blueprint("team", __name__)


def _require_org_id():
    """Return current user's org_id or abort 403."""
    org_id = getattr(current_user, "organization_id", None)
    if org_id is None:
        abort(403)
    return org_id


@team_bp.route("/team")
@login_required
@rbac_service.require_role("org_admin")
def team():
    """List org members with their roles."""
    org_id = _require_org_id()
    members = User.query.filter_by(organization_id=org_id).all()
    role_map = {
        m.id: rbac_service.get_user_role(org_id, m.id) for m in members
    }
    return render_template(
        "admin/team.html",
        members=members,
        role_map=role_map,
        valid_roles=VALID_ORG_ROLES,
    )


@team_bp.route("/team/invite", methods=["POST"])
@login_required
@rbac_service.require_role("org_admin")
def team_invite():
    """Add an existing user to the org with a given role (stub invite email)."""
    org_id = _require_org_id()
    email = (request.form.get("email") or "").strip().lower()
    role = request.form.get("role", "viewer")

    if not email:
        return jsonify({"error": "email required"}), 400
    if role not in VALID_ORG_ROLES:
        return jsonify({"error": f"invalid role '{role}'"}), 400

    user = User.find_by_email(email)
    if user is None:
        return jsonify({"error": f"No user found with email {email}"}), 404

    OrgRole.set_role(org_id, user.id, role, granted_by_id=current_user.id)
    db.session.commit()

    # Stub: send invite email — wire to real email service in COM-008+
    logger.info(
        "STUB invite email to %s with role %s in org %s", email, role, org_id
    )

    return redirect(url_for("team.team"))


@team_bp.route("/team/role", methods=["POST"])
@login_required
@rbac_service.require_role("org_admin")
def team_change_role():
    """Change a member's role within the org."""
    org_id = _require_org_id()
    user_id = request.form.get("user_id", type=int)
    role = request.form.get("role", "")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    if role not in VALID_ORG_ROLES:
        return jsonify({"error": f"invalid role '{role}'"}), 400

    user = db.session.get(User, user_id)
    if user is None or user.organization_id != org_id:
        abort(404)

    OrgRole.set_role(org_id, user_id, role, granted_by_id=current_user.id)
    db.session.commit()
    return redirect(url_for("team.team"))


@team_bp.route("/team/member/<int:user_id>", methods=["DELETE"])
@login_required
@rbac_service.require_role("org_admin")
def team_remove_member(user_id):
    """Remove a user's org role (does not delete the user account)."""
    org_id = _require_org_id()

    # Prevent org_admin from removing themselves
    if user_id == current_user.id:
        return jsonify({"error": "Cannot remove yourself from the org"}), 400

    record = OrgRole.query.filter_by(
        organization_id=org_id, user_id=user_id
    ).first()
    if record:
        db.session.delete(record)
        db.session.commit()
    return jsonify({"status": "removed"})
