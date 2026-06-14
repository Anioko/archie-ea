"""
VA-004: Phase A (Architecture Vision) API Routes

Endpoints exposing Phase A data: architecture principles, strategic drivers
coverage, and vision summary aggregation.
"""

import logging

from flask import Blueprint, jsonify
from flask_login import login_required

logger = logging.getLogger(__name__)

phase_a_bp = Blueprint("phase_a", __name__, url_prefix="/api/ea/phase-a")


@phase_a_bp.route("/principles", methods=["GET"])
@login_required
def get_principles():
    """Return all architecture principles.

    Response 200:
    {
        "principles": [{"id": int, "name": str, "description": str,
                         "enforcement_status": str, "adm_phase": str}],
        "count": int
    }
    """
    from app.models.motivation_extended import Principle

    rows = Principle.query.all()
    principles = [
        {
            "id": p.id,
            "name": p.name,
            "description": getattr(p, "statement", None),
            "enforcement_status": getattr(p, "enforcement_status", None),
            "adm_phase": getattr(p, "adm_phase", None),
        }
        for p in rows
    ]
    return jsonify({"principles": principles, "count": len(principles)}), 200


@phase_a_bp.route("/drivers-coverage", methods=["GET"])
@login_required
def get_drivers_coverage():
    """Return strategic drivers with their capability/application coverage.

    Response 200:
    {
        "drivers": [...],
        "coverage_summary": {"total_drivers": int, "avg_coverage_score": float}
    }
    """
    try:
        from app.services.strategic_drivers_service import StrategicDriversService

        drivers = StrategicDriversService().infer_driver_coverage()
        avg_score = (
            round(sum(d.get("coverage_score", 0.0) for d in drivers) / len(drivers), 4)
            if drivers
            else 0.0
        )
        coverage_summary = {
            "total_drivers": len(drivers),
            "avg_coverage_score": avg_score,
        }
        return jsonify({"drivers": drivers, "coverage_summary": coverage_summary}), 200
    except Exception as exc:
        logger.error("drivers_coverage error: %s", exc, exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Internal server error",
                    "error_code": "INTERNAL_ERROR",
                }
            ),
            500,
        )


@phase_a_bp.route("/vision-summary", methods=["GET"])
@login_required
def get_vision_summary():
    """Return aggregated counts for the Phase A vision summary.

    Response 200:
    {
        "principle_count": int,
        "driver_count": int,
        "stakeholder_count": int
    }
    """
    from app.models.motivation_extended import Principle
    from app.models.archimate_core import ArchiMateElement

    principle_count = Principle.query.count()
    driver_count = ArchiMateElement.query.filter(
        ArchiMateElement.type == "Driver",
        ArchiMateElement.name.isnot(None),
        ArchiMateElement.name != "",
    ).count()
    stakeholder_count = ArchiMateElement.query.filter(
        ArchiMateElement.type == "Stakeholder",
        ArchiMateElement.name.isnot(None),
        ArchiMateElement.name != "",
    ).count()
    return (
        jsonify(
            {
                "principle_count": principle_count,
                "driver_count": driver_count,
                "stakeholder_count": stakeholder_count,
            }
        ),
        200,
    )


@phase_a_bp.route("/viewpoint", methods=["GET"])
@login_required
def get_phase_a_viewpoint():
    """Return live ArchiMate viewpoint for Phase A (Architecture Vision).

    Response 200: {"phase": "A", "viewpoint": {elements_by_layer, relationships,
                   element_count, relationship_count, layer_summary}}
    """
    from app.services.phase_viewpoint_binding_service import PhaseViewpointBindingService
    from app.services.workflow_archimate_context_service import WorkflowArchiMateContextService
    from app.services.archimate_viewpoint_render_service import ArchimateViewpointRenderService
    phase_code = "ADM_PHASE_A_VISION"
    elements = WorkflowArchiMateContextService().get_phase_elements(phase_code)
    element_ids = [e["id"] for e in elements]
    viewpoint = ArchimateViewpointRenderService().render_viewpoint(phase_code, element_ids)
    viewpoint["viewpoint_name"] = PhaseViewpointBindingService().get_viewpoint_name(phase_code)
    return jsonify({"phase": "A", "viewpoint": viewpoint}), 200
