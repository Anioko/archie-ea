from flask import Blueprint, jsonify, request
from app.services.gdpr_service import GDPRService
from app.models.gdpr_request import GDPRRequest
from app.extensions import db
from datetime import datetime


gdpr_bp = Blueprint("gdpr_bp", __name__)

@gdpr_bp.route("/api/gdpr/export/<int:user_id>", methods=["GET"])
def export_user_data(user_id):
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
def delete_user_data(user_id):
    requester_id = request.json.get("requester_id")
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
def gdpr_status(user_id):
    status = GDPRService.get_request_status(user_id)
    return jsonify(status)
