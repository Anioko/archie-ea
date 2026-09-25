"""
Team management routes — org member listing and role management (COM-007).

Blueprint: team_bp  |  URL prefix: /admin  |  All routes: org_admin or platform admin

``rbac_service.require_role("org_admin")`` reads only the per-org OrgRole
table (see app/services/rbac_service.py), a vocabulary separate from
platform-wide admin status (``current_user.is_platform_admin`` combined
with ``Permission.ADMINISTER`` — the same pair app/middleware/
tenant_decorators.py's ``platform_admin_required`` checks). A platform
admin with no OrgRole row for their org defaults to "viewer" there and was
refused every route below. ``_is_org_or_platform_admin`` admits either, so
neither vocabulary is weakened and a platform admin is no longer locked out
of an administration surface they are entitled to.
"""

import logging

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Permission
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


def _require_org_or_platform_admin(org_id):
    """Abort 403 unless the current user is this org's admin or a platform admin."""
    is_platform_admin = bool(
        getattr(current_user, "is_platform_admin", False)
        and current_user.can(Permission.ADMINISTER)
    )
    if is_platform_admin:
        return
    if rbac_service.is_org_admin(org_id, current_user.id):
        return
    abort(403)


@team_bp.route("/team")
@login_required
def team():
    """List org members with their roles."""
    org_id = _require_org_id()
    _require_org_or_platform_admin(org_id)
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
def team_invite():
    """Create a pending invitation for an existing user to join the org.

    The user must accept before a role or membership is granted.  Duplicate
    pending invitations for the same org+user are refused.
    """
    org_id = _require_org_id()
    _require_org_or_platform_admin(org_id)
    email = (request.form.get("email") or "").strip().lower()
    role = request.form.get("role", "viewer")

    if not email:
        return jsonify({"error": "email required"}), 400
    if role not in VALID_ORG_ROLES:
        return jsonify({"error": f"invalid role '{role}'"}), 400

    user = User.find_by_email(email)
    if user is None:
        return jsonify({"error": f"No user found with email {email}"}), 404

    if OrgRole.get_role(org_id, user.id) is not None:
        return jsonify({"error": "This user is already a member of the organisation"}), 409

    from app.models.pending_invitation import PendingInvitation

    _, created = PendingInvitation.create_for(
        org_id, user.id, role, invited_by_id=current_user.id
    )
    if not created:
        return jsonify({"error": "An invitation for this user already exists"}), 409
    db.session.commit()

    logger.info(
        "STUB invite email to %s with role %s in org %s", email, role, org_id
    )

    return redirect(url_for("team.team"))


@team_bp.route("/team/role", methods=["POST"])
@login_required
def team_change_role():
    """Change a member's role within the org."""
    org_id = _require_org_id()
    _require_org_or_platform_admin(org_id)
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
def team_remove_member(user_id):
    """Remove a user's org role (does not delete the user account)."""
    org_id = _require_org_id()
    _require_org_or_platform_admin(org_id)

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
