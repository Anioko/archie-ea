"""DoD (Definition of Done) routes — TPM-010."""
import logging

from flask import Blueprint, jsonify, render_template, request

from app.services import dod_service
from flask_login import login_required

logger = logging.getLogger(__name__)

dod_api_bp = Blueprint("dod_api", __name__, url_prefix="/api/dod")
dod_ui_bp = Blueprint("dod_ui", __name__, url_prefix="/dod")


@dod_api_bp.route("/templates", methods=["GET"])
@login_required
def list_templates():
    """GET /api/dod/templates — list all DoD templates."""
    dod_service.seed_default_templates()
    templates = dod_service.list_templates()
    return jsonify([t.to_dict() for t in templates]), 200


@dod_api_bp.route("/checks", methods=["POST"])
@login_required
def create_check():
    """POST /api/dod/checks — create a DoD check for a requirement or sprint."""
    data = request.get_json(force=True) or {}
    template_id = data.get("template_id")
    requirement_id = data.get("requirement_id")
    sprint_id = data.get("sprint_id")

    if not template_id:
        return jsonify({"error": "template_id is required"}), 400
    if not requirement_id and not sprint_id:
        return jsonify({"error": "requirement_id or sprint_id is required"}), 400

    check = dod_service.create_dod_check(
        requirement_id=requirement_id,
        template_id=template_id,
        sprint_id=sprint_id,
    )
    return jsonify(check.to_dict()), 201


@dod_api_bp.route("/checks/<int:check_id>/criteria", methods=["PATCH"])
@login_required
def update_criterion(check_id: int):
    """PATCH /api/dod/checks/<id>/criteria — tick or untick a criterion."""
    data = request.get_json(force=True) or {}
    criterion_id = data.get("criterion_id")
    checked = data.get("checked")

    if criterion_id is None or checked is None:
        return jsonify({"error": "criterion_id and checked are required"}), 400

    result = dod_service.update_checks(check_id, criterion_id, bool(checked))
    return jsonify(result), 200


@dod_api_bp.route("/checks/<int:req_id>/can-done", methods=["GET"])
@login_required
def can_mark_done(req_id: int):
    """GET /api/dod/checks/<req_id>/can-done — gate check before marking story done."""
    result = dod_service.can_mark_done(req_id)
    return jsonify(result), 200


@dod_ui_bp.route("/templates", methods=["GET"])
@login_required
def templates_page():
    """GET /dod/templates — DoD template management page."""
    dod_service.seed_default_templates()
    templates = dod_service.list_templates()
    return render_template("dod/templates.html", templates=[t.to_dict() for t in templates])
