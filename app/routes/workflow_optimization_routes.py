"""
Workflow Optimization API Routes
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.decorators import audit_log
from app.services.workflow_optimization_engine import get_optimization_engine

logger = logging.getLogger(__name__)

# Create blueprint
workflow_optimization_bp = Blueprint(
    "workflow_optimization", __name__, url_prefix="/api/workflow-optimization"
)


@workflow_optimization_bp.route("/recommendations", methods=["GET"])
@login_required
def get_recommendations():
    """
    Get workflow optimization recommendations
    ---
    tags:
      - Workflow Optimization
    summary: Get AI-driven workflow recommendations
    parameters:
      - in: query
        name: workflow_type
        type: string
        description: Filter by workflow type (applications, vendors, capabilities)
    responses:
      200:
        description: Optimization recommendations
    """
    try:
        workflow_type = request.args.get("workflow_type")
        engine = get_optimization_engine()

        if workflow_type == "applications":
            recommendations = engine.get_application_workflow_recommendations()
        elif workflow_type == "vendors":
            recommendations = engine.get_vendor_workflow_recommendations()
        elif workflow_type == "capabilities":
            recommendations = engine.get_capability_workflow_recommendations()
        else:
            # Return all recommendations
            recommendations = (
                engine.get_application_workflow_recommendations()
                + engine.get_vendor_workflow_recommendations()
                + engine.get_capability_workflow_recommendations()
            )

        return jsonify(
            {"success": True, "recommendations": recommendations, "count": len(recommendations)}
        )

    except Exception as e:
        logger.error(f"Error getting recommendations: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@workflow_optimization_bp.route("/bottlenecks", methods=["GET"])
@login_required
def get_bottlenecks():
    """
    Get process bottlenecks
    ---
    tags:
      - Workflow Optimization
    summary: Identify workflow bottlenecks
    responses:
      200:
        description: Process bottlenecks
    """
    try:
        engine = get_optimization_engine()
        bottlenecks = engine.get_process_bottlenecks()

        return jsonify({"success": True, "bottlenecks": bottlenecks, "count": len(bottlenecks)})

    except Exception as e:
        logger.error(f"Error getting bottlenecks: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@workflow_optimization_bp.route("/automation-opportunities", methods=["GET"])
@login_required
def get_automation_opportunities():
    """
    Get automation opportunities
    ---
    tags:
      - Workflow Optimization
    summary: Identify automation opportunities
    responses:
      200:
        description: Automation opportunities
    """
    try:
        engine = get_optimization_engine()
        opportunities = engine.get_automation_opportunities()

        return jsonify(
            {"success": True, "opportunities": opportunities, "count": len(opportunities)}
        )

    except Exception as e:
        logger.error(f"Error getting automation opportunities: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@workflow_optimization_bp.route("/performance-metrics", methods=["GET"])
@login_required
def get_performance_metrics():
    """
    Get workflow performance metrics
    ---
    tags:
      - Workflow Optimization
    summary: Get overall workflow performance
    responses:
      200:
        description: Performance metrics
    """
    try:
        engine = get_optimization_engine()
        metrics = engine.get_performance_metrics()

        return jsonify({"success": True, "metrics": metrics})

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@workflow_optimization_bp.route("/optimization-report", methods=["GET"])
@login_required
def get_optimization_report():
    """
    Generate comprehensive optimization report
    ---
    tags:
      - Workflow Optimization
    summary: Get complete optimization analysis
    responses:
      200:
        description: Optimization report
    """
    try:
        engine = get_optimization_engine()
        report = engine.generate_optimization_report()

        return jsonify({"success": True, "report": report})

    except Exception as e:
        logger.error(f"Error generating optimization report: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@workflow_optimization_bp.route("/analyze-workflow", methods=["POST"])
@login_required
@audit_log("workflow_analyze")
def analyze_workflow():
    """
    Analyze specific workflow
    ---
    tags:
      - Workflow Optimization
    summary: Analyze workflow metrics and get recommendations
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            workflow_type:
              type: string
            metrics:
              type: object
    responses:
      200:
        description: Workflow analysis
    """
    try:
        data = request.get_json()

        if not data or "workflow_type" not in data:
            return jsonify({"success": False, "error": "workflow_type is required"}), 400

        engine = get_optimization_engine()
        analysis = engine.analyze_workflow(
            workflow_type=data["workflow_type"], metrics=data.get("metrics", {})
        )

        return jsonify({"success": True, "analysis": analysis})

    except Exception as e:
        logger.error(f"Error analyzing workflow: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
