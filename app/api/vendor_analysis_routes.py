"""
Vendor Analysis API Routes

RESTful endpoints for vendor analysis functionality.
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.exceptions import DatabaseError, ExternalServiceError, FlaskShadcnException, NotFoundError
from app.services.vendor_analyzer import VendorAnalyzer

logger = logging.getLogger(__name__)

# Create blueprint
vendor_analysis_bp = Blueprint("vendor_analysis", __name__)


@vendor_analysis_bp.route("/api/vendor-analysis/<int:vendor_id>", methods=["GET"])
@login_required
def analyze_vendor(vendor_id):
    """
    Perform comprehensive vendor analysis.

    Args:
        vendor_id: ID of the vendor to analyze

    Returns:
        JSON response with analysis results including:
        - Capability coverage percentage
        - Process coverage metrics
        - Technology stack analysis
        - Integration complexity score
        - Recommendations

    Raises:
        404: Vendor not found
        500: Database or service error
    """
    try:
        logger.info(f"Starting vendor analysis for vendor_id={vendor_id}")

        # Initialize analyzer
        analyzer = VendorAnalyzer()

        # Perform analysis
        results = analyzer.analyze_vendor(vendor_id)

        logger.info(
            f"Vendor analysis completed successfully for vendor_id={vendor_id}, "
            f"overall_score={results.get('overall_score', {}).get('score', 0)}"
        )

        return jsonify(results), 200

    except NotFoundError as e:
        logger.warning(f"Vendor not found: vendor_id={vendor_id}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": e.user_message,
                    "error_code": e.error_code,
                    "recovery_action": e.recovery_action,
                }
            ),
            e.status_code,
        )

    except DatabaseError as e:
        logger.error(
            f"Database error during vendor analysis: vendor_id={vendor_id}, error={str(e)}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": e.user_message,
                    "error_code": e.error_code,
                    "recovery_action": e.recovery_action,
                }
            ),
            e.status_code,
        )

    except ExternalServiceError as e:
        logger.error(
            f"External service error during vendor analysis: vendor_id={vendor_id}, error={str(e)}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": e.user_message,
                    "error_code": e.error_code,
                    "recovery_action": e.recovery_action,
                }
            ),
            e.status_code,
        )

    except FlaskShadcnException as e:
        logger.error(
            f"Application error during vendor analysis: vendor_id={vendor_id}, error={str(e)}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": e.user_message,
                    "error_code": e.error_code,
                    "recovery_action": e.recovery_action,
                }
            ),
            e.status_code,
        )

    except Exception as e:
        logger.error(
            f"Unexpected error during vendor analysis: vendor_id={vendor_id}, error={str(e)}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An unexpected error occurred while analyzing the vendor.",
                    "error_code": "INTERNAL_ERROR",
                    "recovery_action": "Please try again. If the problem persists, contact support.",
                }
            ),
            500,
        )


@vendor_analysis_bp.route("/api/vendor-analysis/<int:vendor_id>/summary", methods=["GET"])
@login_required
def get_vendor_analysis_summary(vendor_id):
    """
    Get a quick summary of vendor analysis.

    Args:
        vendor_id: ID of the vendor

    Returns:
        JSON response with summary metrics only
    """
    try:
        logger.info(f"Fetching vendor analysis summary for vendor_id={vendor_id}")

        analyzer = VendorAnalyzer()
        results = analyzer.analyze_vendor(vendor_id)

        # Return only summary information
        summary = {
            "success": True,
            "vendor_id": results["vendor_id"],
            "vendor_name": results["vendor_name"],
            "overall_score": results["overall_score"],
            "capability_coverage_pct": results["capability_coverage"]["coverage_percentage"],
            "process_coverage_pct": results["process_coverage"]["coverage_percentage"],
            "integration_complexity": results["integration_complexity"]["level"],
            "recommendation_count": len(results["recommendations"]),
        }

        return jsonify(summary), 200

    except NotFoundError as e:
        return (
            jsonify(
                {
                    "success": False,
                    "error": e.user_message,
                    "error_code": e.error_code,
                }
            ),
            e.status_code,
        )

    except Exception as e:
        logger.error(
            f"Error fetching vendor analysis summary: vendor_id={vendor_id}, error={str(e)}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to fetch vendor analysis summary.",
                    "error_code": "INTERNAL_ERROR",
                }
            ),
            500,
        )
