"""
DEPRECATED: This file is migrated to app/modules/applications/.
Registration is now centralized via app.modules.applications.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

Application Merging API Routes

REST API endpoints for application merging functionality
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.decorators import audit_log
from app.models.application_portfolio import (
    ApplicationComponent as ApplicationComponent,
)
from app.models.architecture_review_board import ARBAuditLog
from app.services.application_merging_service import (
    ApplicationMatchingService,
    ApplicationMergeService,
    MergeConfig,
)

logger = logging.getLogger(__name__)

# Create blueprint following API compliance standards
merging_bp = Blueprint(
    "application_merging", __name__, url_prefix="/dashboard/api/applications/merging"
)

# Mark as guardrailed BEFORE routes are registered
from app.core.compat import mark_blueprint_guardrailed

mark_blueprint_guardrailed(merging_bp)


@merging_bp.route("/candidates", methods=["GET"])
@login_required
def get_merge_candidates():
    """
    Get potential merge candidates for applications

    Query Parameters:
    - threshold: Similarity threshold (default: 0.7)
    - limit: Maximum number of candidates to return (default: 50)
    """
    try:
        threshold = float(request.args.get("threshold", 0.7))
        limit = int(request.args.get("limit", 50))
        mode = request.args.get("mode", "balanced")

        # Adjust threshold based on merge mode
        mode_multipliers = {
            "conservative": 1.15,  # Stricter: require higher similarity
            "balanced": 1.0,  # Use configured threshold as-is
            "aggressive": 0.85,  # Looser: accept lower similarity
        }
        threshold = threshold * mode_multipliers.get(mode, 1.0)
        threshold = max(0.4, min(threshold, 0.99))  # Clamp to valid range

        # Get all active applications (exclude retired/deprecated)
        applications = ApplicationComponent.query.filter(
            ApplicationComponent.lifecycle_status.notin_(
                ["retired", "deprecated"]
            )
        ).all()

        # Configure matching service
        config = MergeConfig(similarity_threshold=threshold)
        matching_service = ApplicationMatchingService(config)

        # Find candidates
        candidates = matching_service.find_merge_candidates(applications)

        # Filter out ignored pairs
        ignored_entries = ARBAuditLog.query.filter_by(
            entity_type="merge_candidate", action="ignore"
        ).all()
        ignored_pairs = set()
        for entry in ignored_entries:
            if entry.entity_reference:
                ignored_pairs.add(entry.entity_reference)
        candidates = [
            c
            for c in candidates
            if f"{c.primary_app.id}:{c.duplicate_app.id}" not in ignored_pairs
            and f"{c.duplicate_app.id}:{c.primary_app.id}" not in ignored_pairs
        ]

        # Limit results
        candidates = candidates[:limit]

        # Format response
        response_data = {
            "success": True,
            "candidates": [],
            "total_analyzed": len(applications),
            "threshold_used": threshold,
            "total_candidates": len(candidates),
        }

        for candidate in candidates:
            candidate_data = {
                "primary_app": {
                    "id": candidate.primary_app.id,
                    "name": candidate.primary_app.name,
                    "description": candidate.primary_app.description,
                    "vendor": getattr(candidate.primary_app, "vendor", ""),
                    "business_owner": getattr(
                        candidate.primary_app, "business_owner", ""
                    ),
                    "criticality": getattr(candidate.primary_app, "criticality", ""),
                    "user_count": getattr(candidate.primary_app, "user_count", 0),
                },
                "duplicate_app": {
                    "id": candidate.duplicate_app.id,
                    "name": candidate.duplicate_app.name,
                    "description": candidate.duplicate_app.description,
                    "vendor": getattr(candidate.duplicate_app, "vendor", ""),
                    "business_owner": getattr(
                        candidate.duplicate_app, "business_owner", ""
                    ),
                    "criticality": getattr(candidate.duplicate_app, "criticality", ""),
                    "user_count": getattr(candidate.duplicate_app, "user_count", 0),
                },
                "similarity_score": candidate.similarity_score,
                "match_reasons": candidate.match_reasons,
                "conflicts": candidate.conflicts,
            }
            response_data["candidates"].append(candidate_data)

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error getting merge candidates: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to get merge candidates: {str(e)}",
                }
            ),
            500,
        )


@merging_bp.route("/analyze/<int:app_id>", methods=["GET"])
@login_required
def analyze_application_merges(app_id):
    """
    Analyze potential merges for a specific application

    Args:
        app_id: ID of the application to analyze
    """
    try:
        threshold = float(request.args.get("threshold", 0.7))

        # Get the target application
        target_app = ApplicationComponent.query.get_or_404(app_id)

        # Get all other active applications (exclude retired/deprecated)
        other_apps = ApplicationComponent.query.filter(
            ApplicationComponent.id != app_id,
            ApplicationComponent.lifecycle_status.notin_(
                ["retired", "deprecated"]
            ),
        ).all()

        # Configure matching service
        config = MergeConfig(similarity_threshold=threshold)
        matching_service = ApplicationMatchingService(config)

        # Find candidates for this specific app
        all_candidates = matching_service.find_merge_candidates(
            [target_app] + other_apps
        )

        # Filter to only candidates involving the target app
        target_candidates = [
            candidate
            for candidate in all_candidates
            if candidate.primary_app.id == app_id
            or candidate.duplicate_app.id == app_id
        ]

        # Format response
        response_data = {
            "success": True,
            "target_application": {
                "id": target_app.id,
                "name": target_app.name,
                "description": target_app.description,
                "vendor": target_app.vendor_name or "",
                "business_owner": target_app.business_owner or "",
                "criticality": target_app.criticality or "",
                "user_count": target_app.user_count or 0,
            },
            "merge_candidates": [],
            "total_candidates": len(target_candidates),
            "threshold_used": threshold,
        }

        for candidate in target_candidates:
            # Determine which app is the other one
            other_app = (
                candidate.duplicate_app
                if candidate.primary_app.id == app_id
                else candidate.primary_app
            )

            candidate_data = {
                "application": {
                    "id": other_app.id,
                    "name": other_app.name,
                    "description": other_app.description,
                    "vendor": other_app.vendor_name or "",
                    "business_owner": other_app.business_owner or "",
                    "criticality": other_app.criticality or "",
                    "user_count": other_app.user_count or 0,
                },
                "similarity_score": candidate.similarity_score,
                "match_reasons": candidate.match_reasons,
                "conflicts": candidate.conflicts,
                "recommended_action": "merge"
                if candidate.similarity_score > 0.8
                else "review",
            }
            response_data["merge_candidates"].append(candidate_data)

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error analyzing application merges: {str(e)}")
        return jsonify({"success": False, "error": "Failed to analyze merges"}), 500


@merging_bp.route("/execute", methods=["POST"])
@login_required
@audit_log("application_merge_execute")
def execute_merge():
    """
    Execute a merge between two applications

    Request Body:
    {
        "primary_app_id": int,
        "duplicate_app_id": int,
        "merge_strategy": {
            "description": "primary|duplicate",
            "business_owner": "primary|duplicate",
            "cost_center": "primary|duplicate",
            "criticality": "primary|duplicate",
            "merge_capabilities": bool,
            "merge_technologies": bool
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        primary_app_id = data.get("primary_app_id")
        duplicate_app_id = data.get("duplicate_app_id")
        merge_strategy = data.get("merge_strategy", {})

        if not primary_app_id or not duplicate_app_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Both primary_app_id and duplicate_app_id are required",
                    }
                ),
                400,
            )

        if primary_app_id == duplicate_app_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Cannot merge an application with itself",
                    }
                ),
                400,
            )

        # Get applications
        primary_app = ApplicationComponent.query.get_or_404(primary_app_id)
        duplicate_app = ApplicationComponent.query.get_or_404(duplicate_app_id)

        # Validate applications are not retired (using lifecycle_status)
        inactive_stages = ["retired", "deprecated", "decommissioned"]
        if (
            primary_app.lifecycle_status in inactive_stages
            or duplicate_app.lifecycle_status in inactive_stages
        ):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Both applications must be active to merge",
                    }
                ),
                400,
            )

        # Execute merge
        merge_service = ApplicationMergeService()
        result = merge_service.execute_merge(primary_app, duplicate_app, merge_strategy)

        if result["success"]:
            return jsonify(
                {
                    "success": True,
                    "message": result["message"],
                    "merge_result": {
                        "primary_app_id": result["primary_app_id"],
                        "duplicate_app_id": result["duplicate_app_id"],
                        "merged_fields": result["merged_fields"],
                    },
                }
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": result.get("error") or result["message"],
                    }
                ),
                500,
            )

    except Exception as e:
        logger.error(f"Error executing merge: {str(e)}")
        return jsonify({"success": False, "error": "Failed to execute merge"}), 500


@merging_bp.route("/preview", methods=["POST"])
@login_required
@audit_log("application_merge_preview")
def preview_merge():
    """
    Preview the result of a merge without executing it

    Request Body:
    {
        "primary_app_id": int,
        "duplicate_app_id": int,
        "merge_strategy": {
            "description": "primary|duplicate",
            "business_owner": "primary|duplicate",
            "cost_center": "primary|duplicate",
            "criticality": "primary|duplicate",
            "merge_capabilities": bool,
            "merge_technologies": bool
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        primary_app_id = data.get("primary_app_id")
        duplicate_app_id = data.get("duplicate_app_id")
        merge_strategy = data.get("merge_strategy", {})

        if not primary_app_id or not duplicate_app_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Both primary_app_id and duplicate_app_id are required",
                    }
                ),
                400,
            )

        # Get applications
        primary_app = ApplicationComponent.query.get_or_404(primary_app_id)
        duplicate_app = ApplicationComponent.query.get_or_404(duplicate_app_id)

        # Simulate merge result
        merge_service = ApplicationMergeService()
        merged_data = merge_service._apply_merge_strategy(
            primary_app, duplicate_app, merge_strategy
        )

        # Build preview data
        def _app_capabilities(app):
            caps = []
            for m in (app.capability_mappings or []):
                if m.business_capability:
                    caps.append(m.business_capability.name)
            return caps

        def _app_technologies(app):
            techs = []
            for t in (app.technology_instances or []):
                name = t.instance_name or (t.technology.name if t.technology else None)
                if name:
                    techs.append(name)
            return techs

        preview = {
            "primary_app": {
                "id": primary_app.id,
                "name": primary_app.name,
                "description": primary_app.description,
                "business_owner": primary_app.business_owner or "",
                "criticality": primary_app.criticality or "",
                "capabilities": _app_capabilities(primary_app),
                "technologies": _app_technologies(primary_app),
                "user_count": primary_app.user_count or 0,
            },
            "duplicate_app": {
                "id": duplicate_app.id,
                "name": duplicate_app.name,
                "description": duplicate_app.description,
                "business_owner": duplicate_app.business_owner or "",
                "criticality": duplicate_app.criticality or "",
                "capabilities": _app_capabilities(duplicate_app),
                "technologies": _app_technologies(duplicate_app),
                "user_count": duplicate_app.user_count or 0,
            },
            "merged_result": merged_data,
            "changes_detected": list(merged_data.keys()),
            "merge_strategy": merge_strategy,
        }

        return jsonify(
            {
                "success": True,
                "preview": preview,
                "message": "Merge preview generated successfully",
            }
        )

    except Exception as e:
        logger.error(f"Error previewing merge: {str(e)}")
        return jsonify({"success": False, "error": "Failed to preview merge"}), 500


@merging_bp.route("/config", methods=["GET", "PUT"])
@login_required
def merge_config():
    """Get or update merge configuration"""
    if request.method == "GET":
        # Return current configuration
        config = MergeConfig()
        return jsonify(
            {
                "success": True,
                "config": {
                    "name_weight": config.name_weight,
                    "description_weight": config.description_weight,
                    "vendor_weight": config.vendor_weight,
                    "capability_weight": config.capability_weight,
                    "technology_weight": config.technology_weight,
                    "similarity_threshold": config.similarity_threshold,
                },
            }
        )

    elif request.method == "PUT":
        # Update configuration (would typically persist this)
        data = request.get_json()
        if not data:
            return jsonify(
                {"success": False, "error": "No configuration data provided"}
            ), 400

        # Validate and update config
        try:
            config = MergeConfig(
                name_weight=float(data.get("name_weight", 0.3)),
                description_weight=float(data.get("description_weight", 0.25)),
                vendor_weight=float(data.get("vendor_weight", 0.2)),
                capability_weight=float(data.get("capability_weight", 0.15)),
                technology_weight=float(data.get("technology_weight", 0.1)),
                similarity_threshold=float(data.get("similarity_threshold", 0.7)),
            )

            # Validate weights sum to 1.0
            total_weight = (
                config.name_weight
                + config.description_weight
                + config.vendor_weight
                + config.capability_weight
                + config.technology_weight
            )

            if abs(total_weight - 1.0) > 0.01:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": f"Weights must sum to 1.0, current sum: {total_weight}",
                        }
                    ),
                    400,
                )

            # In a real implementation, this would be saved to database/config file
            return jsonify(
                {
                    "success": True,
                    "message": "Configuration updated successfully",
                    "config": {
                        "name_weight": config.name_weight,
                        "description_weight": config.description_weight,
                        "vendor_weight": config.vendor_weight,
                        "capability_weight": config.capability_weight,
                        "technology_weight": config.technology_weight,
                        "similarity_threshold": config.similarity_threshold,
                    },
                }
            )

        except (ValueError, TypeError) as e:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Invalid configuration values: {str(e)}",
                    }
                ),
                400,
            )
