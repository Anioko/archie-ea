"""AG-005: Phase G — Implementation Governance API blueprint.

Endpoints:
  GET  /api/ea/phase-g/compliance-matrix
  GET  /api/ea/phase-g/derogations
  GET  /api/ea/phase-g/arb-status
  POST /api/ea/phase-g/compliance-check/<int:app_id>

All endpoints require login.  No raw SQL — ORM only.
"""
import logging

from flask import Blueprint, jsonify
from flask_login import login_required

logger = logging.getLogger(__name__)

phase_g_bp = Blueprint("phase_g", __name__)


# ---------------------------------------------------------------------------
# GET /api/ea/phase-g/compliance-matrix
# ---------------------------------------------------------------------------

@phase_g_bp.route("/api/ea/phase-g/compliance-matrix", methods=["GET"])
@login_required
def compliance_matrix():
    """Return the full compliance matrix computed across all applications."""
    from app.services.architecture_compliance_matrix_service import (
        ArchitectureComplianceMatrixService,
    )

    matrix = ArchitectureComplianceMatrixService().compute_compliance_matrix()

    compliant = sum(1 for r in matrix if r.get("overall_status") == "compliant")
    partial = sum(1 for r in matrix if r.get("overall_status") == "partial")
    non_compliant = sum(1 for r in matrix if r.get("overall_status") == "non_compliant")

    return jsonify(
        {
            "matrix": matrix,
            "summary": {
                "compliant": compliant,
                "partial": partial,
                "non_compliant": non_compliant,
            },
        }
    ), 200


# ---------------------------------------------------------------------------
# GET /api/ea/phase-g/derogations
# ---------------------------------------------------------------------------

@phase_g_bp.route("/api/ea/phase-g/derogations", methods=["GET"])
@login_required
def derogations():
    """Return all Derogation rows."""
    try:
        from app.models.architecture_review_board import Derogation

        rows = Derogation.query.all()
    except Exception as exc:
        logger.warning("phase_g derogations: %s", exc)
        rows = []

    data = []
    for d in rows:
        data.append(
            {
                "id": d.id,
                "name": getattr(d, "title", None),
                "status": d.status,
                "justification": getattr(d, "rationale", None),
                "expiry_date": (
                    d.expiry_date.isoformat() if d.expiry_date else None
                ),
            }
        )

    return jsonify({"derogations": data, "count": len(data)}), 200


# ---------------------------------------------------------------------------
# GET /api/ea/phase-g/arb-status
# ---------------------------------------------------------------------------

@phase_g_bp.route("/api/ea/phase-g/arb-status", methods=["GET"])
@login_required
def arb_status():
    """Return ARBReviewItem counts grouped by status."""
    from app.models.architecture_review_board import ARBReviewItem

    try:
        items = ARBReviewItem.query.all()
    except Exception as exc:
        logger.warning("phase_g arb_status: %s", exc)
        items = []

    by_status: dict = {}
    for item in items:
        s = item.status or "unknown"
        by_status[s] = by_status.get(s, 0) + 1

    return jsonify({"by_status": by_status, "total": len(items)}), 200


# ---------------------------------------------------------------------------
# POST /api/ea/phase-g/compliance-check/<int:app_id>
# ---------------------------------------------------------------------------

@phase_g_bp.route(
    "/api/ea/phase-g/compliance-check/<int:app_id>", methods=["POST"]
)
@login_required
def compliance_check(app_id: int):
    """Trigger compliance check for a specific application."""
    from app.services.architecture_compliance_matrix_service import (
        ArchitectureComplianceMatrixService,
    )

    matrix = ArchitectureComplianceMatrixService().compute_compliance_matrix()
    match = next((r for r in matrix if r.get("app_id") == app_id), None)

    if match is None:
        return jsonify({"error": f"Application {app_id} not found"}), 404

    return jsonify(match), 200


@phase_g_bp.route("/api/ea/phase-g/viewpoint", methods=["GET"])
@login_required
def get_phase_g_viewpoint():
    """Return live ArchiMate viewpoint for Phase G (Implementation Governance)."""
    from app.services.phase_viewpoint_binding_service import PhaseViewpointBindingService
    from app.services.workflow_archimate_context_service import WorkflowArchiMateContextService
    from app.services.archimate_viewpoint_render_service import ArchimateViewpointRenderService
    phase_code = "ADM_PHASE_G_GOVERNANCE"
    elements = WorkflowArchiMateContextService().get_phase_elements(phase_code)
    element_ids = [e["id"] for e in elements]
    viewpoint = ArchimateViewpointRenderService().render_viewpoint(phase_code, element_ids)
    viewpoint["viewpoint_name"] = PhaseViewpointBindingService().get_viewpoint_name(phase_code)
    return jsonify({"phase": "G", "viewpoint": viewpoint}), 200
