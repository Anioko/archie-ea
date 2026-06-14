"""
APQC Hierarchy Browser API Routes

Provides REST API endpoints for APQC PCF hierarchy browsing,
intelligent mapping, and process management for enterprise architecture.
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app import db
from app.decorators import audit_log
from app.services.apqc_hierarchy_service import APQCHierarchyService

logger = logging.getLogger(__name__)

# Create blueprint
apqc_hierarchy_bp = Blueprint("apqc_hierarchy", __name__, url_prefix="/api/apqc")

# Initialize service
apqc_service = APQCHierarchyService()


# REMOVED: /hierarchy route — conflicts with apqc_bp.get_hierarchy() in apqc_routes.py
# (apqc_bp is registered later at __init__.py:1691 and wins; also has @login_required)

# REMOVED: /search route — conflicts with apqc_bp.search_apqc_processes() in apqc_routes.py
# (apqc_bp is registered later at __init__.py:1691 and wins; also has @login_required)


@apqc_hierarchy_bp.route("/process/<int:process_id>/hierarchy", methods=["GET"])
@login_required
def get_process_hierarchy(process_id: int):
    """
    Get full hierarchy path for a specific APQC process.

    Path Parameters:
        process_id: APQC process ID

    Query Parameters:
        industry (str): Optional industry for variant-specific paths

    Returns:
        JSON with complete hierarchy path from Level 1 to the process
    """
    try:
        from app.models.apqc_process import APQCProcess

        process = APQCProcess.query.get(process_id)
        if not process:
            return jsonify({"success": False, "error": "Process not found"}), 404

        industry = request.args.get("industry")
        hierarchy_path = apqc_service.get_hierarchy_path(process.process_code, industry)
        parent_ids = apqc_service.get_parent_processes(process.process_code)

        return jsonify(
            {
                "success": True,
                "process": {
                    "id": process.id,
                    "code": process.process_code,
                    "name": process.process_name,
                    "level": process.apqc_level,
                },
                "hierarchy_path": hierarchy_path,
                "parent_ids": parent_ids,
                "industry": industry,
            }
        )

    except Exception as e:
        logger.error(f"Error getting process hierarchy: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@apqc_hierarchy_bp.route("/process/<int:process_id>/metrics", methods=["GET"])
@login_required
def get_process_metrics(process_id: int):
    """
    Get comprehensive metrics and benchmarking data for a process.

    Path Parameters:
        process_id: APQC process ID

    Returns:
        JSON with process metrics, benchmarks, and KPIs
    """
    try:
        metrics = apqc_service.get_process_metrics(process_id)

        if "error" in metrics:
            return jsonify({"success": False, "error": metrics["error"]}), 404

        return jsonify({"success": True, "metrics": metrics})

    except Exception as e:
        logger.error(f"Error getting process metrics: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@apqc_hierarchy_bp.route("/auto-link-parents", methods=["POST"])
@login_required
@audit_log("apqc_auto_link_parents")
def auto_link_parent_processes():
    """
    Automatically create parent process mappings when mapping to child process.

    Request Body:
        {
            "application_id": int,
            "process_id": int,
            "confidence_threshold": float (optional, default: 0.6)
        }

    Returns:
        JSON with linking results and statistics
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        application_id = data.get("application_id")
        process_id = data.get("process_id")
        confidence_threshold = data.get("confidence_threshold", 0.6)

        if not application_id or not process_id:
            return (
                jsonify({"success": False, "error": "application_id and process_id are required"}),
                400,
            )

        result = apqc_service.auto_link_parent_processes(
            application_id, process_id, confidence_threshold
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error auto-linking parent processes: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@apqc_hierarchy_bp.route("/industry/<industry>/processes", methods=["GET"])
@login_required
def get_industry_processes(industry: str):
    """
    Get industry-specific APQC process variants.

    Path Parameters:
        industry: Industry name (banking, healthcare, manufacturing)

    Returns:
        JSON with industry-specific process modifications and additions
    """
    try:
        processes = apqc_service.get_industry_processes(industry)

        return jsonify(
            {
                "success": True,
                "industry": industry,
                "processes": processes,
                "total_processes": len(processes),
            }
        )

    except Exception as e:
        logger.error(f"Error getting industry processes: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@apqc_hierarchy_bp.route("/levels", methods=["GET"])
@login_required
def get_processes_by_level():
    """
    Get APQC processes grouped by hierarchy level.

    Query Parameters:
        level (int): Optional specific level to return (1 - 5)

    Returns:
        JSON with processes grouped by APQC level
    """
    try:
        from app.models.apqc_process import APQCProcess

        level = request.args.get("level", type=int)

        if level:
            if level < 1 or level > 5:
                return jsonify({"success": False, "error": "Level must be between 1 and 5"}), 400

            processes = APQCProcess.get_processes_by_level(level)
            result = {str(level): [p.to_dict() for p in processes]}
        else:
            # Get all levels
            result = {}
            for lvl in range(1, 6):
                processes = APQCProcess.get_processes_by_level(lvl)
                result[str(lvl)] = [p.to_dict() for p in processes]

        return jsonify({"success": True, "levels": result, "total_levels": len(result)})

    except Exception as e:
        logger.error(f"Error getting processes by level: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@apqc_hierarchy_bp.route("/categories", methods=["GET"])
@login_required
def get_process_categories():
    """
    Get all APQC process categories with process counts.

    Returns:
        JSON with process categories and statistics
    """
    try:
        from sqlalchemy import func

        from app.models.apqc_process import APQCProcess

        # Get category statistics
        category_stats = (
            db.session.query(
                APQCProcess.process_category,
                func.count(APQCProcess.id).label("process_count"),
                func.avg(APQCProcess.process_maturity).label("avg_maturity"),
            )
            .group_by(APQCProcess.process_category)
            .all()
        )

        categories = []
        for category, count, avg_maturity in category_stats:
            categories.append(
                {
                    "category": category,
                    "process_count": count,
                    "average_maturity": round(float(avg_maturity), 2) if avg_maturity else None,
                }
            )

        # Sort by process count
        categories.sort(key=lambda x: x["process_count"], reverse=True)

        return jsonify(
            {"success": True, "categories": categories, "total_categories": len(categories)}
        )

    except Exception as e:
        logger.error(f"Error getting process categories: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


def _count_tree_processes(tree) -> int:
    """Helper function to count total processes in tree structure."""
    if tree is None:
        return 0

    count = 0

    # Handle dict structure
    if isinstance(tree, dict):
        for key, value in tree.items():
            if isinstance(value, dict):
                count += 1
                if "children" in value:
                    children = value["children"]
                    if isinstance(children, dict):
                        count += _count_tree_processes(children)
                    elif isinstance(children, list):
                        for child in children:
                            count += _count_tree_processes(child)

    # Handle list structure
    elif isinstance(tree, list):
        for item in tree:
            count += _count_tree_processes(item)

    return count


def register_apqc_hierarchy_routes(app):
    """Register APQC hierarchy blueprint with Flask app."""
    app.register_blueprint(apqc_hierarchy_bp)
    logger.info("APQC hierarchy API routes registered")
