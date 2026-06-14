"""
AI Suggestions API Routes

Provides REST endpoints for managing AI-generated suggestions
in the hybrid manual/automated workflow system.

Endpoints:
- GET /api/suggestions/ - List pending suggestions
- GET /api/suggestions/{id} - Get specific suggestion
- POST /api/suggestions/{id}/accept - Accept suggestion
- POST /api/suggestions/{id}/reject - Reject suggestion
- POST /api/suggestions/{id}/modify - Accept with modifications
- POST /api/suggestions/bulk-accept - Bulk accept high confidence
- POST /api/suggestions/bulk-reject - Bulk reject low confidence
- GET /api/suggestions/statistics - Get suggestion statistics
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.decorators import audit_log
from app.models.ai_suggestion import AISuggestion
from app.services.ai_suggestion_service import AISuggestionService

logger = logging.getLogger(__name__)

# Create blueprint
suggestions_bp = Blueprint("suggestions", __name__, url_prefix="/api/suggestions")

# Initialize service
suggestion_service = AISuggestionService()


@suggestions_bp.route("/", methods=["GET"])
@login_required
def list_suggestions():
    """
    List pending suggestions with optional filtering.

    Query Parameters:
    - entity_type: Filter by entity type (application, capability, etc.)
    - entity_id: Filter by specific entity ID
    - source: Filter by suggestion source
    - min_confidence: Minimum confidence threshold (0 - 1)
    - max_confidence: Maximum confidence threshold (0 - 1)
    - priority: Filter by priority (critical, high, normal, low)
    - workflow_name: Filter by workflow name
    - batch_id: Filter by batch ID
    - limit: Maximum results (default 50)
    - offset: Pagination offset (default 0)
    - order_by: Sort order (priority_confidence, confidence, created_at)

    Returns:
        JSON list of suggestions
    """
    try:
        # Get query parameters
        entity_type = request.args.get("entity_type")
        entity_id = request.args.get("entity_id", type=int)
        source = request.args.get("source")
        min_confidence = request.args.get("min_confidence", type=float)
        max_confidence = request.args.get("max_confidence", type=float)
        priority = request.args.get("priority")
        workflow_name = request.args.get("workflow_name")
        batch_id = request.args.get("batch_id")
        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        order_by = request.args.get("order_by", "priority_confidence")

        # Get suggestions
        suggestions = suggestion_service.get_pending_suggestions(
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            priority=priority,
            workflow_name=workflow_name,
            batch_id=batch_id,
            limit=limit,
            offset=offset,
            order_by=order_by,
        )

        # Convert to dict
        return jsonify(
            {
                "success": True,
                "suggestions": [s.to_summary_dict() for s in suggestions],
                "count": len(suggestions),
                "filters": {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "source": source,
                    "min_confidence": min_confidence,
                    "max_confidence": max_confidence,
                    "priority": priority,
                    "workflow_name": workflow_name,
                    "batch_id": batch_id,
                    "limit": limit,
                    "offset": offset,
                    "order_by": order_by,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error listing suggestions: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@suggestions_bp.route("/<int:suggestion_id>", methods=["GET"])
@login_required
def get_suggestion(suggestion_id):
    """
    Get a specific suggestion by ID.

    Args:
        suggestion_id: ID of suggestion to retrieve

    Returns:
        JSON suggestion object
    """
    try:
        suggestion = AISuggestion.query.get(suggestion_id)
        if not suggestion:
            return jsonify({"success": False, "error": "Suggestion not found"}), 404

        return jsonify({"success": True, "suggestion": suggestion.to_dict()})

    except Exception as e:
        logger.error(f"Error getting suggestion {suggestion_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@suggestions_bp.route("/<int:suggestion_id>/accept", methods=["POST"])
@login_required
@audit_log("suggestion_accept")
def accept_suggestion(suggestion_id):
    """
    Accept a suggestion.

    Request Body:
    - final_value: Optional value to use instead of suggested
    - notes: Optional review notes
    - apply_to_entity: Whether to apply to entity (default true)

    Returns:
        JSON result
    """
    try:
        data = request.get_json() or {}
        final_value = data.get("final_value")
        notes = data.get("notes")
        apply_to_entity = data.get("apply_to_entity", True)

        result = suggestion_service.accept_suggestion(
            suggestion_id=suggestion_id,
            user_id=current_user.id,
            final_value=final_value,
            notes=notes,
            apply_to_entity=apply_to_entity,
        )

        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error accepting suggestion {suggestion_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@suggestions_bp.route("/<int:suggestion_id>/reject", methods=["POST"])
@login_required
@audit_log("suggestion_reject")
def reject_suggestion(suggestion_id):
    """
    Reject a suggestion.

    Request Body:
    - notes: Optional reason for rejection

    Returns:
        JSON result
    """
    try:
        data = request.get_json() or {}
        notes = data.get("notes")

        result = suggestion_service.reject_suggestion(
            suggestion_id=suggestion_id, user_id=current_user.id, notes=notes
        )

        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error rejecting suggestion {suggestion_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@suggestions_bp.route("/<int:suggestion_id>/modify", methods=["POST"])
@login_required
@audit_log("suggestion_modify")
def modify_suggestion(suggestion_id):
    """
    Accept a suggestion with modifications.

    Request Body:
    - modified_value: User's modified value (required)
    - notes: Optional review notes
    - apply_to_entity: Whether to apply to entity (default true)

    Returns:
        JSON result
    """
    try:
        data = request.get_json() or {}
        modified_value = data.get("modified_value")
        notes = data.get("notes")
        apply_to_entity = data.get("apply_to_entity", True)

        if modified_value is None:
            return jsonify({"success": False, "error": "modified_value is required"}), 400

        result = suggestion_service.modify_and_accept(
            suggestion_id=suggestion_id,
            user_id=current_user.id,
            modified_value=modified_value,
            notes=notes,
            apply_to_entity=apply_to_entity,
        )

        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error modifying suggestion {suggestion_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@suggestions_bp.route("/<int:suggestion_id>/helpful", methods=["POST"])
@login_required
def mark_helpful(suggestion_id):
    """
    Record feedback on suggestion quality.

    Request Body:
    - helpful: Boolean indicating if suggestion was helpful

    Returns:
        JSON result
    """
    try:
        data = request.get_json() or {}
        helpful = data.get("helpful")

        if helpful is None:
            return jsonify({"success": False, "error": "helpful field is required"}), 400

        result = suggestion_service.mark_helpful(suggestion_id=suggestion_id, helpful=helpful)

        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        logger.error(f"Error marking helpful {suggestion_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@suggestions_bp.route("/bulk-accept", methods=["POST"])
@login_required
@audit_log("suggestions_bulk_accept")
def bulk_accept():
    """
    Bulk accept suggestions by confidence threshold.

    Request Body:
    - threshold: Minimum confidence to auto-accept (default 0.85)
    - entity_type: Optional filter by entity type
    - batch_id: Optional filter by batch ID

    Returns:
        JSON result with count of accepted suggestions
    """
    try:
        data = request.get_json() or {}
        threshold = data.get("threshold", 0.85)
        entity_type = data.get("entity_type")
        batch_id = data.get("batch_id")

        if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
            return (
                jsonify({"success": False, "error": "threshold must be a number between 0 and 1"}),
                400,
            )

        result = suggestion_service.bulk_accept_by_confidence(
            user_id=current_user.id, threshold=threshold, entity_type=entity_type, batch_id=batch_id
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in bulk accept: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@suggestions_bp.route("/bulk-reject", methods=["POST"])
@login_required
@audit_log("suggestions_bulk_reject")
def bulk_reject():
    """
    Bulk reject suggestions by confidence threshold.

    Request Body:
    - threshold: Maximum confidence to reject (default 0.5)
    - entity_type: Optional filter by entity type
    - batch_id: Optional filter by batch ID

    Returns:
        JSON result with count of rejected suggestions
    """
    try:
        data = request.get_json() or {}
        threshold = data.get("threshold", 0.5)
        entity_type = data.get("entity_type")
        batch_id = data.get("batch_id")

        if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
            return (
                jsonify({"success": False, "error": "threshold must be a number between 0 and 1"}),
                400,
            )

        result = suggestion_service.bulk_reject_by_confidence(
            user_id=current_user.id, threshold=threshold, entity_type=entity_type, batch_id=batch_id
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in bulk reject: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@suggestions_bp.route("/statistics", methods=["GET"])
@login_required
def get_statistics():
    """
    Get suggestion statistics for dashboard.

    Query Parameters:
    - days: Number of days to include (default 30)

    Returns:
        JSON statistics
    """
    try:
        days = request.args.get("days", 30, type=int)

        if days < 1 or days > 365:
            return jsonify({"success": False, "error": "days must be between 1 and 365"}), 400

        stats = suggestion_service.get_statistics(days=days)

        return jsonify({"success": True, "statistics": stats})

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@suggestions_bp.route("/entity/<entity_type>/<int:entity_id>", methods=["GET"])
@login_required
def get_entity_suggestions(entity_type, entity_id):
    """
    Get all suggestions for a specific entity.

    Args:
        entity_type: Type of entity (application, capability, etc.)
        entity_id: Entity ID

    Query Parameters:
    - include_reviewed: Include already reviewed suggestions (default false)

    Returns:
        JSON list of suggestions
    """
    try:
        include_reviewed = request.args.get("include_reviewed", "false").lower() == "true"

        suggestions = suggestion_service.get_suggestions_for_entity(
            entity_type=entity_type, entity_id=entity_id, include_reviewed=include_reviewed
        )

        return jsonify(
            {
                "success": True,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "suggestions": [s.to_dict() for s in suggestions],
                "count": len(suggestions),
                "include_reviewed": include_reviewed,
            }
        )

    except Exception as e:
        logger.error(f"Error getting suggestions for {entity_type} {entity_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# Error handlers
@suggestions_bp.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Resource not found"}), 404


@suggestions_bp.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "error": "Internal server error"}), 500
