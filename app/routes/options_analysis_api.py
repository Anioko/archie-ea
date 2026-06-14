"""
DEPRECATED: This file is migrated to app/modules/vendors/.
Registration is now centralized via app.modules.vendors.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

Options Analysis API Routes

Provides REST API endpoints for explainable options analysis with provenance tracking,
scenario simulation, and confidence-scored recommendations.

Endpoints:
- POST /api/options-analysis/analyze - Run options analysis
- GET /api/options-analysis/<analysis_id> - Get analysis results
- GET /api/options-analysis/<analysis_id>/provenance - Get provenance data
- GET /api/options-analysis/<analysis_id>/scenarios - Get scenario simulations
- POST /api/options-analysis/<analysis_id>/sensitivity - Run sensitivity analysis
- GET /api/options-analysis/<analysis_id>/export - Export analysis
"""

import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.decorators import audit_log
from app import db

logger = logging.getLogger(__name__)

options_analysis_bp = Blueprint("options_analysis", __name__, url_prefix="/api/options-analysis")


@options_analysis_bp.route("/analyze", methods=["POST"])
@login_required
@audit_log("options_analyze")
def analyze_options():
    """
    Run comprehensive options analysis with explainable scoring.

    Request Body:
    {
        "name": "Analysis Name",
        "capability_id": 123,
        "vendor_org_ids": [1,2,3],
        "criteria_weights": {...},
        "analysis_type": "standard"
    }

    Returns:
        Analysis results with provenance and confidence scores
    """
    try:
        from app.services.vendor_analysis.options_analysis_service import OptionsAnalysisService

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        name = data.get("name")
        capability_id = data.get("capability_id")
        if not name or not capability_id:
            return jsonify({"success": False, "error": "name and capability_id are required"}), 400

        service = OptionsAnalysisService()
        analysis = service.create_analysis(
            name=name,
            capability_id=capability_id,
            vendor_org_ids=data.get("vendor_org_ids"),
            vendor_product_ids=data.get("vendor_product_ids"),
            vendor_ids=data.get("vendor_ids"),
            created_by=current_user,
            criteria_weights=data.get("criteria_weights"),
            description=data.get("description"),
            analysis_type=data.get("analysis_type", "comprehensive"),
            tco_years=data.get("tco_years", 5),
            budget_constraint=data.get("budget_constraint"),
            organization_size=data.get("organization_size"),
            industry_vertical=data.get("industry_vertical"),
        )

        analysis = service.run_analysis(
            analysis_id=analysis.id,
            deep_research=data.get("deep_research", False),
            required_capabilities=data.get("required_capabilities"),
        )

        matrix = service.get_comparison_matrix(analysis.id)

        return jsonify(
            {
                "success": True,
                "data": {
                    "analysis_id": analysis.id,
                    "status": analysis.status,
                    "results": matrix,
                },
            }
        )
    except ValueError as e:
        logger.warning("Validation error in analyze_options: %s", e)
        return jsonify({"success": False, "error": "Invalid request parameters"}), 400
    except Exception as e:
        logger.error("Error in analyze_options: %s", e, exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@options_analysis_bp.route("/<int:analysis_id>", methods=["GET"])
@login_required
def get_analysis(analysis_id):
    """
    Get analysis results with full provenance.

    Returns:
        Complete analysis data including results, scenarios, and provenance
    """
    try:
        from app.services.vendor_analysis.options_analysis_service import OptionsAnalysisService

        service = OptionsAnalysisService()
        report = service.get_analysis_report(analysis_id)
        return jsonify({"success": True, "data": report})
    except Exception as e:
        logger.error("Error getting analysis %s: %s", analysis_id, e, exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@options_analysis_bp.route("/<int:analysis_id>/provenance", methods=["GET"])
@login_required
def get_analysis_provenance(analysis_id):
    """
    Get detailed provenance data for analysis.

    Returns:
        Provenance chain including sources, models used, reasoning traces
    """
    try:
        from app.models.vendor_analysis import OptionsAnalysis

        analysis = db.session.get(OptionsAnalysis, analysis_id)
        if not analysis:
            return jsonify({"success": False, "error": "Analysis not found"}), 404

        provenance_data = {
            "analysis_id": analysis.id,
            "name": analysis.name,
            "status": analysis.status,
            "analysis_type": analysis.analysis_type,
            "timestamp": analysis.completed_at.isoformat() if analysis.completed_at else None,
            "execution_duration_seconds": analysis.execution_duration_seconds,
            "models_used": [],
            "data_sources": [],
            "reasoning_trace": [],
            "confidence_factors": {
                "recommendation_confidence": float(analysis.recommendation_confidence or 0),
            },
        }

        for vo in analysis.vendor_options:
            if vo.ai_research_sources:
                try:
                    sources = json.loads(vo.ai_research_sources)
                    provenance_data["data_sources"].extend(sources)
                except (json.JSONDecodeError, TypeError):
                    pass
            if vo.ai_confidence is not None:
                provenance_data["confidence_factors"][vo.vendor_name] = float(vo.ai_confidence)

        for rec in analysis.recommendations:
            if rec.llm_model_used:
                provenance_data["models_used"].append(
                    {
                        "model": rec.llm_model_used,
                        "tokens_used": rec.llm_tokens_used,
                        "cost": float(rec.llm_cost or 0),
                    }
                )
            if rec.confidence_explanation:
                provenance_data["reasoning_trace"].append(rec.confidence_explanation)

        return jsonify({"success": True, "data": provenance_data})
    except Exception as e:
        logger.error("Error getting provenance for %s: %s", analysis_id, e, exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@options_analysis_bp.route("/<int:analysis_id>/scenarios", methods=["GET"])
@login_required
def get_analysis_scenarios(analysis_id):
    """
    Get scenario simulation results.

    Returns:
        What-if analysis scenarios with results
    """
    try:
        from app.models.vendor_analysis import OptionsAnalysis

        analysis = db.session.get(OptionsAnalysis, analysis_id)
        if not analysis:
            return jsonify({"success": False, "error": "Analysis not found"}), 404

        scenarios_data = []
        for scenario in analysis.scenarios:
            scenarios_data.append(
                {
                    "id": scenario.id,
                    "scenario_name": scenario.scenario_name,
                    "description": scenario.description,
                    "is_baseline": scenario.is_baseline,
                    "criteria_weights": scenario.get_criteria_weights(),
                    "vendor_rankings": scenario.get_vendor_rankings(),
                    "recommended_vendor_id": scenario.recommended_vendor_id,
                    "winner_score": float(scenario.scenario_winner_score)
                    if scenario.scenario_winner_score
                    else None,
                    "cost_delta": float(scenario.cost_delta) if scenario.cost_delta else None,
                }
            )

        return jsonify({"success": True, "data": scenarios_data})
    except Exception as e:
        logger.error("Error getting scenarios for %s: %s", analysis_id, e, exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@options_analysis_bp.route("/<int:analysis_id>/sensitivity", methods=["POST"])
@login_required
@audit_log("options_sensitivity_analyze")
def run_sensitivity_analysis(analysis_id):
    """
    Run sensitivity analysis on criteria weights.

    Request Body:
    {
        "weight_variations": {"cost": [0.2, 0.3], "risk": [0.15, 0.25]},
        "iterations": 100
    }

    Returns:
        Sensitivity analysis results showing how rankings change per criteria
    """
    try:
        from app.services.vendor_comparison_service import VendorComparisonService

        data = request.get_json() or {}
        weight_variations = data.get("weight_variations", {})

        if not weight_variations:
            return jsonify({"success": False, "error": "weight_variations is required"}), 400

        service = VendorComparisonService()
        results = []
        for criteria, variation_values in weight_variations.items():
            variation_range = (
                (max(variation_values) - min(variation_values)) / 2
                if variation_values and len(variation_values) >= 2
                else 0.1
            )
            result = service.sensitivity_analysis(
                analysis_id=analysis_id,
                criteria=criteria,
                variation_range=variation_range,
            )
            results.append({"criteria": criteria, "result": result})

        return jsonify({"success": True, "data": results})
    except Exception as e:
        logger.error("Error in sensitivity analysis for %s: %s", analysis_id, e, exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@options_analysis_bp.route("/<int:analysis_id>/export", methods=["GET"])
@login_required
def export_analysis(analysis_id):
    """
    Export analysis results.

    Query Parameters:
        format: json|pdf|csv
        include_provenance: true|false

    Returns:
        Exported analysis data
    """
    try:
        from app.services.vendor_analysis.options_analysis_service import OptionsAnalysisService

        export_format = request.args.get("format", "json")
        service = OptionsAnalysisService()
        report = service.get_analysis_report(analysis_id)

        return jsonify(
            {
                "success": True,
                "data": {
                    "analysis_id": analysis_id,
                    "export_format": export_format,
                    "export_timestamp": datetime.utcnow().isoformat(),
                    "results": report,
                },
            }
        )
    except Exception as e:
        logger.error("Error exporting analysis %s: %s", analysis_id, e, exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
