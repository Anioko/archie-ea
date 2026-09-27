"""Owner writer routes for the Applications module.

Provides:
- Person picker: debounced live-search for users in the caller's organisation
- Add an owner (POST, JSON)
- Change an owner's type (PUT, JSON)
- Remove an owner (DELETE, JSON)

All routes are scoped to the caller's organisation and refuse cross-org
assignment. The owner text columns on ApplicationComponent are read-only
in the edit form — ownership is recorded only through this module.
"""

from __future__ import annotations

import logging

from flask import g, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.decorators import audit_log
from app.models.application_owner import ApplicationOwner
from app.models.application_portfolio import ApplicationComponent
from app.models.user import User
from app.utils.tenant_users import user_in_org

from . import unified_applications_bp

logger = logging.getLogger(__name__)


# Shared ILIKE escape — backslash, percent and underscore stand for themselves.
def _search_clause(search: str):
    """Return a SQL expression that matches user name/email literally.
    
    The search text is escaped so that ``%`` and ``_`` stand for themselves
    rather than acting as pattern characters.  Compare
    ``my_applications/services.py``'s ``_search_clause``.
    """
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    term = f"%{escaped}%"
    return db.or_(
        User.first_name.ilike(term, escape="\\"),
        User.last_name.ilike(term, escape="\\"),
        User.email.ilike(term, escape="\\"),
    )


def _verify_app_in_org(app_id: int, org_id: int) -> ApplicationComponent | None:
    """Return the application iff it exists and belongs to *org_id*."""
    return ApplicationComponent.query.filter_by(
        id=app_id, organization_id=org_id
    ).first()


@unified_applications_bp.route("/<int:app_id>/owners/search")
@login_required
def owner_picker_search(app_id: int):
    """Debounced live-search for users in the caller's organisation.

    Called by the person-picker widget with a 300 ms debounce. Returns up to
    20 matching users by name or email, scoped to the caller's organisation.
    The search text is matched literally (``%`` and ``_`` are escaped).
    """
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"results": []})

    org_id = g.current_org_id
    users = (
        User.query.filter(
            User.organization_id == org_id,
            _search_clause(q),
        )
        .order_by(User.first_name, User.last_name)
        .limit(20)
        .all()
    )

    return jsonify({
        "results": [
            {
                "id": u.id,
                "label": f"{u.first_name} {u.last_name}" if u.first_name else u.email,
                "email": u.email,
            }
            for u in users
        ]
    })


@unified_applications_bp.route("/<int:app_id>/owners", methods=["POST"])
@login_required
@audit_log("application_owner_add")
def add_owner(app_id: int):
    """Add an owner to an application (JSON only).

    Body: {"user_id": int, "ownership_type": "primary"|"backup"|"technical"|"business"}
    Refuses assignment of a user from another organisation.  Also refuses
    writing to an application that does not belong to the caller.
    """
    org_id = g.current_org_id

    # Verify the application belongs to the caller's organisation
    app = _verify_app_in_org(app_id, org_id)
    if app is None:
        return jsonify({"success": False, "error": "Application not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Request body must be JSON"}), 400

    user_id = data.get("user_id")
    ownership_type = (data.get("ownership_type") or "primary").strip().lower()

    if ownership_type not in ApplicationOwner.OWNERSHIP_TYPES:
        return jsonify({
            "success": False,
            "error": f"ownership_type must be one of {ApplicationOwner.OWNERSHIP_TYPES}",
        }), 400

    user = user_in_org(user_id, org_id)
    if user is None:
        return jsonify({
            "success": False,
            "error": "User not found in your organisation",
        }), 404

    # Check for duplicate (same user + same type)
    existing = ApplicationOwner.query.filter(
        ApplicationOwner.application_id == app_id,
        ApplicationOwner.user_id == user.id,
        ApplicationOwner.ownership_type == ownership_type,
        ApplicationOwner.organization_id == org_id,
    ).first()
    if existing is not None:
        return jsonify({
            "success": False,
            "error": f"User already assigned as {ownership_type} owner",
        }), 409

    owner = ApplicationOwner(
        application_id=app_id,
        user_id=user.id,
        assigned_by=current_user.id,
        organization_id=org_id,
        ownership_type=ownership_type,
    )
    db.session.add(owner)
    db.session.commit()

    return jsonify({
        "success": True,
        "owner": owner.to_dict(),
    }), 201


@unified_applications_bp.route("/<int:app_id>/owners/<int:owner_id>", methods=["PUT"])
@login_required
@audit_log("application_owner_change_type")
def change_owner_type(app_id: int, owner_id: int):
    """Change an owner's type (JSON only)."""
    org_id = g.current_org_id

    # Verify the application belongs to the caller's organisation
    app = _verify_app_in_org(app_id, org_id)
    if app is None:
        return jsonify({"success": False, "error": "Application not found"}), 404

    owner = ApplicationOwner.query.filter(
        ApplicationOwner.id == owner_id,
        ApplicationOwner.application_id == app_id,
        ApplicationOwner.organization_id == org_id,
    ).first()
    if owner is None:
        return jsonify({"success": False, "error": "Owner record not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Request body must be JSON"}), 400

    new_type = (data.get("ownership_type") or "").strip().lower()
    if new_type not in ApplicationOwner.OWNERSHIP_TYPES:
        return jsonify({
            "success": False,
            "error": f"ownership_type must be one of {ApplicationOwner.OWNERSHIP_TYPES}",
        }), 400

    owner.ownership_type = new_type
    db.session.commit()

    return jsonify({
        "success": True,
        "owner": owner.to_dict(),
    })


@unified_applications_bp.route("/<int:app_id>/owners/<int:owner_id>", methods=["DELETE"])
@login_required
@audit_log("application_owner_remove")
def remove_owner(app_id: int, owner_id: int):
    """Remove an owner from an application."""
    org_id = g.current_org_id

    # Verify the application belongs to the caller's organisation
    app = _verify_app_in_org(app_id, org_id)
    if app is None:
        return jsonify({"success": False, "error": "Application not found"}), 404

    owner = ApplicationOwner.query.filter(
        ApplicationOwner.id == owner_id,
        ApplicationOwner.application_id == app_id,
        ApplicationOwner.organization_id == org_id,
    ).first()
    if owner is None:
        return jsonify({"success": False, "error": "Owner record not found"}), 404

    db.session.delete(owner)
    db.session.commit()

    return jsonify({"success": True}), 200


@unified_applications_bp.route("/<int:app_id>/owners", methods=["GET"])
@login_required
def list_owners(app_id: int):
    """List all owners for an application, with user details."""
    # Verify the application exists and is in the caller's organisation
    app = _verify_app_in_org(app_id, g.current_org_id)
    if app is None:
        return jsonify({"success": False, "error": "Application not found"}), 404

    org_id = g.current_org_id
    owners = ApplicationOwner.get_owners_for_application(app_id, org_id)

    result = []
    for o in owners:
        user = user_in_org(o.user_id, org_id)
        result.append({
            "id": o.id,
            "user_id": o.user_id,
            "user_name": f"{user.first_name} {user.last_name}" if user else "Unknown",
            "user_email": user.email if user else None,
            "ownership_type": o.ownership_type,
            "assigned_at": o.assigned_at.isoformat() if o.assigned_at else None,
            "assigned_by": o.assigned_by,
        })

    return jsonify({"owners": result})