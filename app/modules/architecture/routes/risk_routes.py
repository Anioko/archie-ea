"""Risk REST API and UI routes — TPM-013 risk heat map."""
import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app import db  # dead-code-ok
from app.models.risk import Risk
from app.services import risk_service

logger = logging.getLogger(__name__)

risk_bp = Blueprint("risk", __name__)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@risk_bp.route("/api/risks", methods=["GET"])
@login_required
def list_risks():
    """GET /api/risks?solution_id=N — list risks, optionally filtered."""
    solution_id = request.args.get("solution_id", type=int)
    q = Risk.query
    if solution_id is not None:
        q = q.filter_by(solution_id=solution_id)
    risks = q.order_by(Risk.id).all()
    return jsonify([r.to_dict() for r in risks]), 200


@risk_bp.route("/api/risks", methods=["POST"])
@login_required
def create_risk():
    """POST /api/risks — create a risk. Returns 201."""
    data = request.get_json(force=True) or {}
    required = ("title", "likelihood", "impact")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
    try:
        risk = risk_service.create_risk(
            solution_id=data.get("solution_id"),
            title=data["title"],
            description=data.get("description"),
            likelihood=data["likelihood"],
            impact=data["impact"],
            owner=data.get("owner"),
            mitigation_plan=data.get("mitigation_plan"),
        )
    except (ValueError, KeyError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(risk.to_dict()), 201


@risk_bp.route("/api/risks/<int:risk_id>", methods=["PATCH"])
@login_required
def update_risk(risk_id):
    """PATCH /api/risks/<id> — update risk status."""
    data = request.get_json(force=True) or {}
    status = data.get("status")
    if not status:
        return jsonify({"error": "status is required"}), 400
    try:
        risk = risk_service.update_risk_status(risk_id, status)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(risk.to_dict()), 200


@risk_bp.route("/api/risks/heat-map", methods=["GET"])
@login_required
def risk_heat_map_data():
    """GET /api/risks/heat-map?solution_id=N — 5×5 grid data."""
    solution_id = request.args.get("solution_id", type=int)
    data = risk_service.get_heat_map_data(solution_id=solution_id)
    return jsonify(data), 200


# ---------------------------------------------------------------------------
# UI routes
# ---------------------------------------------------------------------------

@risk_bp.route("/risks/")
@login_required
def risk_register():
    """Standalone Risk Register page — shows all risks across the enterprise."""
    risks = Risk.query.order_by(Risk.id).all()
    heat_data = risk_service.get_heat_map_data(solution_id=None)
    return render_template(
        "governance/risk_register.html",
        risks=risks,
        grid=heat_data.get("grid", []),
        total=len(risks),
    )


@risk_bp.route("/solutions/<int:solution_id>/risks", methods=["GET"])
@login_required
def risk_heat_map_page(solution_id):
    """Render the risk heat map page for a solution."""
    data = risk_service.get_heat_map_data(solution_id=solution_id)
    return render_template(
        "solutions/risk_heat_map.html",
        solution_id=solution_id,
        grid=data["grid"],
        risks=data["risks"],
    )
