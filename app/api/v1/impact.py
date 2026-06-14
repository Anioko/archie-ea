"""
API v1 Impact Analysis Endpoints

Canonical shared route for running impact analysis on an application or ArchiMate element.
All UI components (strategic dashboard, application detail, composer, chat, ARB) should
call POST /api/v1/impact/analyze instead of calling impact services directly.

See docs/impact_analysis_api_contract.md for the full request/response contract.
"""

import logging

from flask import Blueprint, request
from flask_login import login_required

from app.utils.api_response import error_response, success_response

impact_bp = Blueprint("impact_v1", __name__)
logger = logging.getLogger(__name__)

VALID_SCENARIOS = {"modification", "retirement", "upgrade", "cloud_migration", "vendor_switch", "custom"}


@impact_bp.route("/analyze", methods=["POST"])
@login_required
def analyze_impact():
    """
    Run impact analysis for an application or ArchiMate element.

    Request body (JSON):
        app_id (int, optional): ApplicationComponent ID. Required if element_id is omitted.
        element_id (int, optional): ArchiMate element ID. Required if app_id is omitted.
        scenario (str, required): Change scenario. One of: modification, retirement,
            upgrade, cloud_migration, vendor_switch, custom.

    Returns:
        200: {risk_level, total_score, breakdown, affected_elements, summary}
        400: Validation error
        404: app/element not found
    """
    data = request.get_json(silent=True) or {}
    app_id = data.get("app_id")
    element_id = data.get("element_id")
    scenario = data.get("scenario")

    # Validate mutually exclusive identifier fields
    if not app_id and not element_id:
        return error_response("Exactly one of app_id or element_id is required", status_code=400)
    if app_id and element_id:
        return error_response("Provide only one of app_id or element_id, not both", status_code=400)
    if not scenario:
        return error_response("scenario is required", status_code=400)
    if scenario not in VALID_SCENARIOS:
        return error_response(
            f"scenario must be one of: {', '.join(sorted(VALID_SCENARIOS))}",
            status_code=400,
        )

    try:
        app_id = int(app_id) if app_id is not None else None
        element_id = int(element_id) if element_id is not None else None
    except (ValueError, TypeError):
        return error_response("app_id and element_id must be integers", status_code=400)

    try:
        from app.modules.ai_chat.services.ai_impact_analysis_service import AIImpactAnalysisService

        svc = AIImpactAnalysisService()

        if app_id is not None:
            result = svc.analyze_application_impact(
                app_id=app_id,
                scenario=scenario,
            )
        else:
            # Element-level analysis: delegate to canonical v2 service
            from app.modules.solutions_strategic.v2.services.impact_analysis_service import (
                ImpactAnalysisService,
            )

            change_type = _scenario_to_change_type(scenario)
            raw = ImpactAnalysisService.analyze_change_impact(
                element_id=element_id,
                change_type=change_type,
                scenario=scenario,
            )
            result = _normalise_element_result(raw)

        if not result:
            return error_response("Impact analysis returned no result", status_code=404)

        return success_response(_to_contract_shape(result))

    except Exception as exc:
        logger.error("impact/analyze error app_id=%s element_id=%s: %s", app_id, element_id, exc, exc_info=True)
        return error_response("Impact analysis failed", status_code=500)


def _scenario_to_change_type(scenario: str) -> str:
    """Map API scenario names to internal ImpactAnalysisService change_type strings."""
    mapping = {
        "modification": "MODIFY",
        "retirement": "RETIRE",
        "upgrade": "MODIFY",
        "cloud_migration": "REPLACE",
        "vendor_switch": "REPLACE",
        "custom": "MODIFY",
    }
    return mapping.get(scenario, "MODIFY")


def _normalise_element_result(raw: dict) -> dict:
    """Convert element-level ImpactAnalysisService output to contract shape."""
    all_deps = list(raw.get("direct_dependencies") or []) + list(raw.get("indirect_dependencies") or [])
    return {
        "risk_level": raw.get("risk_level", "LOW"),
        "total_score": raw.get("total_affected", 0),
        "breakdown": {
            "direct_dependencies": len(raw.get("direct_dependencies") or []),
            "indirect_dependencies": len(raw.get("indirect_dependencies") or []),
            "weighted_score": raw.get("weighted_score"),
            "estimated_financial_risk": raw.get("estimated_financial_risk"),
        },
        "affected_elements": [
            {"id": d.get("id"), "name": d.get("name"), "type": d.get("type"), "level": d.get("level")}
            for d in all_deps
        ],
        "summary": (
            f"{raw.get('change_type', 'Change')} to element {raw.get('element_id')} "
            f"affects {raw.get('total_affected', 0)} elements. "
            f"Risk: {raw.get('risk_level', 'LOW')}."
        ),
        "analysis_id": raw.get("analysis_id"),
    }


def _to_contract_shape(result: dict) -> dict:
    """Ensure the result matches the API contract regardless of which service produced it."""
    return {
        "risk_level": (result.get("risk_level") or result.get("overall_risk_level") or "LOW").upper(),
        "total_score": result.get("total_score") or result.get("total_affected") or 0,
        "breakdown": result.get("breakdown") or result.get("impact_breakdown") or {},
        "affected_elements": result.get("affected_elements") or result.get("affected_applications") or [],
        "diagram": result.get("diagram") or result.get("graph_visualization"),
        "summary": result.get("summary") or result.get("executive_summary"),
        "analysis_id": result.get("analysis_id") or result.get("id"),
    }
