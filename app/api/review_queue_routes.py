"""
Review Queue API Routes - Frontend-Backend Integration

Provides API endpoints for the AI review queue interface.
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.decorators import audit_log
from app.services.confidence_review_service import ConfidenceReviewService
from app.services.rate_limiter import rate_limit

logger = logging.getLogger(__name__)

# Create blueprint
review_queue_bp = Blueprint("review_queue", __name__, url_prefix="/api/review-queue")


@review_queue_bp.route("", methods=["GET"])
@login_required
def get_review_queue():
    """Get pending AI mappings requiring human review."""
    try:
        service = ConfidenceReviewService()

        # Get pagination parameters
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        status = request.args.get("status", "pending")

        # Get pending review items
        items = service.get_pending_reviews(
            user_id=current_user.id, status=status, page=page, per_page=per_page
        )

        # Get queue statistics
        stats = service.get_queue_statistics()

        return jsonify(
            {
                "success": True,
                "items": [item.to_dict() for item in items],
                "total_items": len(items),
                "statistics": stats,
                "page": page,
                "per_page": per_page,
            }
        )

    except Exception as e:
        logger.error(f"Error getting review queue: {e}")
        return jsonify({"success": False, "error": "Failed to load review queue"}), 500


@review_queue_bp.route("/<int:item_id>/approve", methods=["POST"])
@login_required
@audit_log("review_approve")
@rate_limit(30, "1h")
def approve_review_item(item_id):
    """Approve a specific review queue item."""
    try:
        data = request.get_json() or {}

        service = ConfidenceReviewService()
        result = service.approve_item(
            item_id=item_id,
            reviewer_id=current_user.id,
            reviewer_role=data.get("reviewer_role", "architect"),
            reviewer_experience_level=data.get("reviewer_experience_level", "senior"),
            decision_reason=data.get("decision_reason", "Approved by reviewer"),
            quality_assessment=data.get("quality_assessment", {}),
            identified_issues=data.get("identified_issues", []),
            suggested_improvements=data.get("suggested_improvements", []),
            human_confidence_estimate=data.get("human_confidence_estimate", 0.9),
            ai_accuracy_assessment=data.get("ai_accuracy_assessment", 4),
            correction_made=data.get("correction_made", False),
            corrected_data=data.get("corrected_data", {}),
            review_duration_seconds=data.get("review_duration_seconds", 30),
        )

        if result["success"]:
            logger.info(f"Review item {item_id} approved by user {current_user.id}")
            return jsonify(result)
        else:
            return jsonify({"success": False, "error": result.get("error", "Approval failed")}), 400

    except Exception as e:
        logger.error(f"Error approving review item {item_id}: {e}")
        return jsonify({"success": False, "error": "Failed to approve item"}), 500


@review_queue_bp.route("/<int:item_id>/reject", methods=["POST"])
@login_required
@audit_log("review_reject")
@rate_limit(30, "1h")
def reject_review_item(item_id):
    """Reject a specific review queue item."""
    try:
        data = request.get_json() or {}

        service = ConfidenceReviewService()
        result = service.reject_item(
            item_id=item_id,
            reviewer_id=current_user.id,
            reviewer_role=data.get("reviewer_role", "architect"),
            reviewer_experience_level=data.get("reviewer_experience_level", "senior"),
            decision_reason=data.get("decision_reason", "Rejected by reviewer"),
            quality_assessment=data.get("quality_assessment", {}),
            identified_issues=data.get("identified_issues", []),
            suggested_improvements=data.get("suggested_improvements", []),
            human_confidence_estimate=data.get("human_confidence_estimate", 0.3),
            ai_accuracy_assessment=data.get("ai_accuracy_assessment", 2),
            correction_made=data.get("correction_made", False),
            corrected_data=data.get("corrected_data", {}),
            review_duration_seconds=data.get("review_duration_seconds", 30),
        )

        if result["success"]:
            logger.info(f"Review item {item_id} rejected by user {current_user.id}")
            return jsonify(result)
        else:
            return (
                jsonify({"success": False, "error": result.get("error", "Rejection failed")}),
                400,
            )

    except Exception as e:
        logger.error(f"Error rejecting review item {item_id}: {e}")
        return jsonify({"success": False, "error": "Failed to reject item"}), 500


@review_queue_bp.route("/bulk-approve", methods=["POST"])
@login_required
@audit_log("reviews_bulk_approve")
def bulk_approve_items():
    """Approve multiple review queue items."""
    try:
        data = request.get_json()
        if not data or "item_ids" not in data:
            return jsonify({"success": False, "error": "item_ids is required"}), 400

        item_ids = data["item_ids"]
        if not isinstance(item_ids, list):
            return jsonify({"success": False, "error": "item_ids must be a list"}), 400

        service = ConfidenceReviewService()
        results = []

        for item_id in item_ids:
            result = service.approve_item(
                item_id=item_id,
                reviewer_id=current_user.id,
                reviewer_role=data.get("reviewer_role", "architect"),
                reviewer_experience_level=data.get("reviewer_experience_level", "senior"),
                decision_reason=data.get("decision_reason", "Bulk approved"),
                quality_assessment=data.get("quality_assessment", {}),
                identified_issues=data.get("identified_issues", []),
                suggested_improvements=data.get("suggested_improvements", []),
                human_confidence_estimate=data.get("human_confidence_estimate", 0.9),
                ai_accuracy_assessment=data.get("ai_accuracy_assessment", 4),
                correction_made=data.get("correction_made", False),
                corrected_data=data.get("corrected_data", {}),
                review_duration_seconds=data.get("review_duration_seconds", 30),
            )
            results.append(result)

        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        logger.info(f"Bulk approve: {len(successful)} successful, {len(failed)} failed")

        return jsonify(
            {
                "success": True,
                "results": results,
                "successful_count": len(successful),
                "failed_count": len(failed),
                "message": f"Bulk approval completed: {len(successful)} approved, {len(failed)} failed",
            }
        )

    except Exception as e:
        logger.error(f"Error in bulk approve: {e}")
        return jsonify({"success": False, "error": "Bulk approval failed"}), 500


@review_queue_bp.route("/bulk-reject", methods=["POST"])
@login_required
@audit_log("reviews_bulk_reject")
def bulk_reject_items():
    """Reject multiple review queue items."""
    try:
        data = request.get_json()
        if not data or "item_ids" not in data:
            return jsonify({"success": False, "error": "item_ids is required"}), 400

        item_ids = data["item_ids"]
        if not isinstance(item_ids, list):
            return jsonify({"success": False, "error": "item_ids must be a list"}), 400

        service = ConfidenceReviewService()
        results = []

        for item_id in item_ids:
            result = service.reject_item(
                item_id=item_id,
                reviewer_id=current_user.id,
                reviewer_role=data.get("reviewer_role", "architect"),
                reviewer_experience_level=data.get("reviewer_experience_level", "senior"),
                decision_reason=data.get("decision_reason", "Bulk rejected"),
                quality_assessment=data.get("quality_assessment", {}),
                identified_issues=data.get("identified_issues", []),
                suggested_improvements=data.get("suggested_improvements", []),
                human_confidence_estimate=data.get("human_confidence_estimate", 0.3),
                ai_accuracy_assessment=data.get("ai_accuracy_assessment", 2),
                correction_made=data.get("correction_made", False),
                corrected_data=data.get("corrected_data", {}),
                review_duration_seconds=data.get("review_duration_seconds", 30),
            )
            results.append(result)

        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        logger.info(f"Bulk reject: {len(successful)} successful, {len(failed)} failed")

        return jsonify(
            {
                "success": True,
                "results": results,
                "successful_count": len(successful),
                "failed_count": len(failed),
                "message": f"Bulk rejection completed: {len(successful)} rejected, {len(failed)} failed",
            }
        )

    except Exception as e:
        logger.error(f"Error in bulk reject: {e}")
        return jsonify({"success": False, "error": "Bulk rejection failed"}), 500


@review_queue_bp.route("/statistics", methods=["GET"])
@login_required
def get_queue_statistics():
    """Get review queue statistics."""
    try:
        service = ConfidenceReviewService()
        stats = service.get_queue_statistics()

        return jsonify({"success": True, "statistics": stats})

    except Exception as e:
        logger.error(f"Error getting queue statistics: {e}")
        return jsonify({"success": False, "error": "Failed to get statistics"}), 500


@review_queue_bp.route("/thresholds", methods=["GET"])
@login_required
def get_confidence_thresholds():
    """Get current confidence thresholds."""
    try:
        service = ConfidenceReviewService()
        thresholds = service.get_current_thresholds()

        return jsonify({"success": True, "thresholds": thresholds})

    except Exception as e:
        logger.error(f"Error getting confidence thresholds: {e}")
        return jsonify({"success": False, "error": "Failed to get thresholds"}), 500


@review_queue_bp.route("/thresholds", methods=["POST"])
@login_required
@audit_log("confidence_thresholds_set")
def set_confidence_thresholds():
    """Set confidence thresholds."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request data is required"}), 400

        service = ConfidenceReviewService()
        result = service.create_threshold(
            threshold_name=data.get("threshold_name", "User Configured"),
            threshold_type=data.get("threshold_type", "global"),
            minimum_confidence=data.get("minimum_confidence", 0.5),
            auto_approval_threshold=data.get("auto_approval_threshold", 0.8),
            rejection_threshold=data.get("rejection_threshold", 0.3),
            requires_human_review=data.get("requires_human_review", True),
            user_id=current_user.id,
        )

        if result["success"]:
            logger.info(f"Confidence thresholds updated by user {current_user.id}")
            return jsonify(result)
        else:
            return (
                jsonify(
                    {"success": False, "error": result.get("error", "Failed to set thresholds")}
                ),
                400,
            )

    except Exception as e:
        logger.error(f"Error setting confidence thresholds: {e}")
        return jsonify({"success": False, "error": "Failed to set thresholds"}), 500


def register_review_queue_routes(app):
    """Register review queue blueprint with Flask app."""
    app.register_blueprint(review_queue_bp)
    logger.info("Review queue API routes registered")
