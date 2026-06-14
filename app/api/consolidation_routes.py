"""
Consolidation Planning API Routes

REST API endpoints for application consolidation planning.
Generates comprehensive consolidation plans with financial analysis, risk assessment,
and implementation roadmaps.
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.decorators import audit_log
from app.exceptions import BusinessRuleError, DatabaseError, ValidationError
from app.services.consolidation_planner import ConsolidationPlanner

logger = logging.getLogger(__name__)

# Create blueprint
consolidation_bp = Blueprint("consolidation", __name__, url_prefix="/api/consolidation")


@consolidation_bp.route("/generate-plan", methods=["POST"])
@login_required
@audit_log("consolidation_plan_generate")
def generate_consolidation_plan():
    """
    Generate comprehensive consolidation plan for specified applications.

    Request Body:
    {
        "application_ids": [1, 2, 3, ...]
    }

    Returns:
    {
        "success": true,
        "data": {
            "generated_at": "2026 - 01 - 24T10:30:00",
            "application_count": 3,
            "applications": [...],
            "target_application": {...},
            "executive_summary": "...",
            "dependencies": {...},
            "cost_savings": {...},
            "risks": {...},
            "timeline": {...},
            "resources": {...},
            "recommendations": [...],
            "success_criteria": [...],
            "next_steps": [...]
        }
    }

    Errors:
    - 400: Invalid request (missing or invalid application_ids)
    - 404: Applications not found
    - 422: Business rule violation (insufficient apps, consolidation not feasible)
    - 500: Internal server error
    """
    try:
        # Validate request
        if not request.is_json:
            raise ValidationError(
                "Content-Type must be application/json",
                user_message="Please send request as JSON",
                error_code="INVALID_CONTENT_TYPE",
            )

        data = request.get_json()

        if not data:
            raise ValidationError(
                "Empty request body",
                user_message="Request body cannot be empty",
                error_code="EMPTY_REQUEST",
            )

        # Extract and validate application_ids
        application_ids = data.get("application_ids", [])

        if not application_ids:
            raise ValidationError(
                "Missing application_ids",
                user_message="Please provide a list of application IDs to consolidate",
                error_code="MISSING_APP_IDS",
            )

        if not isinstance(application_ids, list):
            raise ValidationError(
                "application_ids must be a list",
                user_message="Application IDs must be provided as a list",
                error_code="INVALID_APP_IDS_FORMAT",
            )

        # Validate all IDs are integers
        try:
            application_ids = [int(app_id) for app_id in application_ids]
        except (ValueError, TypeError) as e:
            raise ValidationError(
                f"Invalid application ID format: {e}",
                user_message="All application IDs must be valid integers",
                error_code="INVALID_APP_ID_TYPE",
            )

        # Remove duplicates while preserving order
        seen = set()
        application_ids = [x for x in application_ids if not (x in seen or seen.add(x))]

        logger.info(
            f"Generating consolidation plan for {len(application_ids)} applications: {application_ids}"
        )

        # Generate plan using service
        planner = ConsolidationPlanner()
        plan = planner.generate_plan(application_ids)

        logger.info(
            f"Successfully generated consolidation plan. "
            f"Estimated savings: ${plan['cost_savings']['estimated_annual_savings']:,.2f}"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": plan,
                    "message": f"Consolidation plan generated for {len(application_ids)} applications",
                }
            ),
            200,
        )

    except ValidationError as e:
        logger.warning(f"Validation error in generate_consolidation_plan: {e.message}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": e.user_message,
                    "error_code": e.error_code,
                    "details": e.details,
                }
            ),
            400,
        )

    except BusinessRuleError as e:
        logger.warning(f"Business rule error in generate_consolidation_plan: {e.message}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": e.user_message,
                    "error_code": e.error_code,
                    "recovery_action": e.recovery_action,
                }
            ),
            422,
        )

    except DatabaseError as e:
        logger.error(f"Database error in generate_consolidation_plan: {e.message}", exc_info=True)
        return jsonify({"success": False, "error": e.user_message, "error_code": e.error_code}), 500

    except Exception as e:
        logger.error(f"Unexpected error in generate_consolidation_plan: {e}", exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An unexpected error occurred while generating the consolidation plan",
                    "error_code": "INTERNAL_ERROR",
                }
            ),
            500,
        )


@consolidation_bp.route("/health", methods=["GET"])
@login_required
def health_check():
    """
    Health check endpoint for consolidation service.

    Returns:
    {
        "success": true,
        "service": "consolidation",
        "status": "healthy",
        "version": "1.0.0"
    }
    """
    return (
        jsonify(
            {"success": True, "service": "consolidation", "status": "healthy", "version": "1.0.0"}
        ),
        200,
    )


@consolidation_bp.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return (
        jsonify({"success": False, "error": "Endpoint not found", "error_code": "NOT_FOUND"}),
        404,
    )


@consolidation_bp.errorhandler(405)
def method_not_allowed_error(error):
    """Handle 405 errors."""
    return (
        jsonify(
            {"success": False, "error": "Method not allowed", "error_code": "METHOD_NOT_ALLOWED"}
        ),
        405,
    )
