"""
BA-014: Phase B Business Architecture API Routes

Endpoints for Phase B data consumption by UX components.
All endpoints require authentication and are read-only (GET) or create workflow
instances (POST run-phase-b).
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

logger = logging.getLogger(__name__)

ba_phase_b_bp = Blueprint("ba_phase_b", __name__, url_prefix="/api/ea-workflows/ba")


@ba_phase_b_bp.route("/capability-heatmap", methods=["GET"])
@login_required
def capability_heatmap():
    """
    Return capability coverage heatmap for Phase B analysis.

    Response:
    {
        "heatmap": [
            {
                "capability_id": 1,
                "capability_name": "...",
                "coverage_score": 0.75,
                "status": "covered",
                "app_count": 3
            },
            ...
        ]
    }
    """
    try:
        # Import here to pick up the compute_capability_heatmap monkey-patch
        from app.services.capability_gap_service import CapabilityGapAnalysisService

        rows = CapabilityGapAnalysisService().compute_capability_heatmap(scope_app_ids=[])
        return jsonify({"heatmap": rows}), 200
    except Exception as e:
        logger.error("capability_heatmap error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": "Internal server error", "error_code": "INTERNAL_ERROR"}), 500


@ba_phase_b_bp.route("/business-services", methods=["GET"])
@login_required
def business_services():
    """
    Return inferred business service catalogue.

    Response:
    {
        "services": [
            {
                "service_name": "...",
                "components": [...],
                "confidence": 0.85
            },
            ...
        ]
    }
    """
    try:
        from app.services.business_service_catalogue_service import BusinessServiceCatalogueService

        catalogue = BusinessServiceCatalogueService().build_catalogue()
        return jsonify({"services": catalogue}), 200
    except Exception as e:
        logger.error("business_services error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": "Internal server error", "error_code": "INTERNAL_ERROR"}), 500


@ba_phase_b_bp.route("/motivation-model/<int:instance_id>", methods=["GET"])
@login_required
def motivation_model(instance_id):
    """
    Return the motivation model outputs for a Phase B workflow instance.

    Response 200:
    {
        "motivation_model": { ... }
    }

    Response 404:
    {
        "success": false,
        "error": "Instance not found",
        "error_code": "NOT_FOUND"
    }
    """
    from app.models.workflow_models import EAWorkflowInstance

    instance = db_get(EAWorkflowInstance, instance_id)
    if instance is None:
        return jsonify({"success": False, "error": "Instance not found", "error_code": "NOT_FOUND"}), 404

    # Verify this instance belongs to the Business Architecture Phase B workflow
    definition = instance.definition if instance.definition is not None else None
    if definition is None or definition.workflow_code != "BUSINESS_ARCHITECTURE_PHASE_B":
        return jsonify({"success": False, "error": "Instance not found", "error_code": "NOT_FOUND"}), 404

    context = instance.context or {}
    return jsonify({"motivation_model": context.get("motivation_model", {})}), 200


@ba_phase_b_bp.route("/run-phase-b", methods=["POST"])
@login_required
def run_phase_b():
    """
    Enqueue a new Business Architecture Phase B workflow instance.

    Request Body:
    {
        "transformation_brief": "...",
        "instance_name": "..."
    }

    Response 201:
    {
        "instance_id": 42,
        "status": "queued"
    }

    Response 400:
    {
        "success": false,
        "error": "...",
        "error_code": "MISSING_FIELDS"
    }
    """
    if not request.is_json:
        return jsonify({"success": False, "error": "Content-Type must be application/json", "error_code": "INVALID_CONTENT_TYPE"}), 400

    data = request.get_json() or {}
    transformation_brief = data.get("transformation_brief", "").strip()
    instance_name = data.get("instance_name", "").strip()

    if not transformation_brief or not instance_name:
        return jsonify({"success": False, "error": "transformation_brief and instance_name are required", "error_code": "MISSING_FIELDS"}), 400

    try:
        from app.services.ea_workflow_engine import EAWorkflowEngine

        engine = EAWorkflowEngine()
        instance = engine.start_workflow(
            workflow_code="BUSINESS_ARCHITECTURE_PHASE_B",
            context={
                "transformation_brief": transformation_brief,
                "instance_name": instance_name,
            },
            triggered_by="api",
            user_id=current_user.id if current_user.is_authenticated else None,
        )
        return jsonify({"instance_id": instance.id, "status": "queued"}), 201
    except ValueError as e:
        logger.warning("run_phase_b workflow not found: %s", e)
        return jsonify({"success": False, "error": str(e), "error_code": "WORKFLOW_NOT_FOUND"}), 400
    except Exception as e:
        logger.error("run_phase_b error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": "Internal server error", "error_code": "INTERNAL_ERROR"}), 500


def db_get(model, pk):
    """Thin wrapper around db.session.get for mockability in tests."""
    from app import db
    return db.session.get(model, pk)


@ba_phase_b_bp.route("/viewpoint", methods=["GET"])
@login_required
def get_phase_b_viewpoint():
    """Return live ArchiMate viewpoint for Phase B (Business Architecture).

    Response 200: {"phase": "B", "viewpoint": {elements_by_layer, relationships,
                   element_count, relationship_count, layer_summary}}
    """
    from app.services.phase_viewpoint_binding_service import PhaseViewpointBindingService
    from app.services.workflow_archimate_context_service import WorkflowArchiMateContextService
    from app.services.archimate_viewpoint_render_service import ArchimateViewpointRenderService
    phase_code = "ADM_PHASE_B_BUSINESS"
    elements = WorkflowArchiMateContextService().get_phase_elements(phase_code)
    element_ids = [e["id"] for e in elements]
    viewpoint = ArchimateViewpointRenderService().render_viewpoint(phase_code, element_ids)
    viewpoint["viewpoint_name"] = PhaseViewpointBindingService().get_viewpoint_name(phase_code)
    return jsonify({"phase": "B", "viewpoint": viewpoint}), 200
