from flask import Blueprint, jsonify
from flask_login import current_user, login_required
from app.services.gdpr_service import GDPRService
from app.models.gdpr_request import GDPRRequest
from app.extensions import db
from app.middleware.tenant_decorators import platform_admin_required
from datetime import datetime


gdpr_bp = Blueprint("gdpr_bp", __name__)


def _forbid_unless_self_or_platform_admin(user_id):
    """A data-subject request may be actioned by a platform_admin (any user_id)
    or by the subject themselves (their own user_id only). Returns a Flask
    response to short-circuit with, or None if the caller is authorized."""
    if current_user.id == user_id:
        return None
    if not getattr(current_user, "is_platform_admin", False):
        return jsonify({"error": "Platform admin access required"}), 403
    return None


@gdpr_bp.route("/api/gdpr/export/<int:user_id>", methods=["GET"])
@login_required
def export_user_data(user_id):
    denied = _forbid_unless_self_or_platform_admin(user_id)
    if denied:
        return denied
    # Log GDPR export request
    req = GDPRRequest(user_id=user_id, request_type="export", status="pending", requested_at=datetime.utcnow())
    db.session.add(req)
    db.session.commit()
    data = GDPRService.export_user_data(user_id)
    if data is None:
        req.status = "failed"
        req.completed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": "User not found"}), 404
    req.status = "completed"
    req.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify(data)

@gdpr_bp.route("/api/gdpr/delete/<int:user_id>", methods=["POST"])
@platform_admin_required
def delete_user_data(user_id):
    # Cross-user permanent deletion: platform_admin only, no self-service —
    # deliberately not allowed for user_id == current_user.id either, since an
    # unconfirmed self-delete is its own hazard.
    requester_id = current_user.id
    req = GDPRRequest(user_id=user_id, request_type="delete", status="pending", requested_at=datetime.utcnow())
    db.session.add(req)
    db.session.commit()
    ok = GDPRService.delete_user_data(user_id, requester_id)
    if not ok:
        req.status = "failed"
        req.completed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"error": "User not found"}), 404
    req.status = "completed"
    req.completed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "deleted"})

@gdpr_bp.route("/api/gdpr/status/<int:user_id>", methods=["GET"])
@login_required
def gdpr_status(user_id):
    denied = _forbid_unless_self_or_platform_admin(user_id)
    if denied:
        return denied
    status = GDPRService.get_request_status(user_id)
    return jsonify(status)
