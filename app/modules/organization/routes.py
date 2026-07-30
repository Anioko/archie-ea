"""Routes for the Organization module: enterprise org chart + RACI matrix.

Blueprint: organization_bp, url_prefix="/organization".
Index endpoint (linked from the sidebar by the orchestrator post-merge):
    organization.index
"""

import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

# Destructive and mutating routes were guarded by @login_required only, so any
# authenticated user could delete another user's records. Matches the gating
# already used by app/modules/capabilities/routes/enterprise_crud_routes.py.
from app.decorators import require_roles

from app.models.organization_model import RACI_VALUES, STAKEHOLDER_TYPES
from app.utils.api_response import error_response, not_found_response, success_response

from . import service

logger = logging.getLogger(__name__)

organization_bp = Blueprint("organization", __name__, url_prefix="/organization")


@organization_bp.route("/")
@login_required
def index():
    """Landing page linking the org chart and the enterprise RACI matrix."""
    return render_template("organization/index.html")


# ---------------------------------------------------------------------------
# Org chart
# ---------------------------------------------------------------------------


@organization_bp.route("/chart")
@login_required
def chart():
    """Org chart page — D3 tree of BusinessActors linked by
    Composition/Aggregation relationships (or a flat fallback)."""
    return render_template("organization/chart.html")


@organization_bp.route("/chart/api/data")
@login_required
def chart_data():
    """JSON hierarchy data consumed by the D3 org chart."""
    tree = service.build_org_tree()
    return success_response(tree)


# ---------------------------------------------------------------------------
# Enterprise RACI matrix
# ---------------------------------------------------------------------------


@organization_bp.route("/raci")
@login_required
def raci():
    """RACI matrix page — capabilities × stakeholders grid."""
    return render_template("organization/raci.html")


@organization_bp.route("/raci/api/data")
@login_required
def raci_data():
    """JSON payload for the RACI matrix: capability columns + all saved
    assignments (which also implicitly enumerate the stakeholder rows)."""
    capabilities = [
        {"id": c.id, "name": c.name, "code": c.code, "level": c.level}
        for c in service.list_matrix_capabilities()
    ]
    assignments = [a.to_dict() for a in service.list_raci_assignments()]
    return success_response({"capabilities": capabilities, "assignments": assignments})


@organization_bp.route("/raci/api/cell", methods=["POST"])
@login_required
@require_roles("admin", "architect", "business_architect")
def raci_cell_save():
    """Upsert one RACI matrix cell.

    Payload: {
        "stakeholder_type": "actor" | "role" | "user",
        "stakeholder_id": int,
        "stakeholder_name": str,
        "capability_id": int,
        "raci": "R" | "A" | "C" | "I",
        "notes": str (optional)
    }
    """
    payload = request.get_json(silent=True) or {}
    stakeholder_type = payload.get("stakeholder_type")
    stakeholder_id = payload.get("stakeholder_id")
    stakeholder_name = payload.get("stakeholder_name")
    capability_id = payload.get("capability_id")
    raci_value = payload.get("raci")
    notes = payload.get("notes")

    try:
        assignment = service.upsert_raci_cell(
            stakeholder_type=stakeholder_type,
            stakeholder_id=stakeholder_id,
            stakeholder_name=stakeholder_name,
            capability_id=capability_id,
            raci=raci_value,
            notes=notes,
        )
    except ValueError as exc:
        return error_response(str(exc), code="VALIDATION_ERROR", status_code=400)

    return success_response(assignment.to_dict())


@organization_bp.route("/raci/api/cell", methods=["DELETE"])
@login_required
@require_roles("admin")
def raci_cell_delete():
    """Clear one RACI matrix cell.

    Payload: {"stakeholder_type": ..., "stakeholder_id": ..., "capability_id": ...}
    """
    payload = request.get_json(silent=True) or {}
    stakeholder_type = payload.get("stakeholder_type")
    stakeholder_id = payload.get("stakeholder_id")
    capability_id = payload.get("capability_id")

    if stakeholder_type not in STAKEHOLDER_TYPES or not stakeholder_id or not capability_id:
        return error_response("Invalid cell reference", code="VALIDATION_ERROR", status_code=400)

    deleted = service.delete_raci_cell(stakeholder_type, stakeholder_id, capability_id)
    if not deleted:
        return not_found_response("RACI assignment")

    return success_response({"deleted": True})


@organization_bp.route("/api/stakeholders/search")
@login_required
def stakeholder_search():
    """Live-search endpoint for the "add stakeholder" picker on the RACI
    matrix. Searches BusinessActor, BusinessRole and User by name/email."""
    q = request.args.get("q", "")
    results = service.search_stakeholders(q, limit=10)
    return jsonify({"results": results})


__all__ = ["organization_bp", "RACI_VALUES"]
