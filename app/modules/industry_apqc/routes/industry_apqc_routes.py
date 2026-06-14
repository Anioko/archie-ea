"""
Industry APQC Routes - UI Views

Provides web interface routes for managing industry-specific APQC process frameworks.

Migrated from: app/main/routes_industry_apqc.py
"""

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.decorators import audit_log

from app.services.industry_apqc_service import IndustryAPQCService

industry_apqc_bp = Blueprint("industry_apqc", __name__, url_prefix="/industry-apqc")


# =========================================================================
# UI VIEWS
# =========================================================================


@industry_apqc_bp.route("/")
@login_required
def industry_apqc_dashboard():
    """Industry APQC dashboard showing all available industry frameworks."""
    try:
        service = IndustryAPQCService()
        frameworks = service.get_all_frameworks()

        # Get statistics for each framework
        framework_stats = []
        for fw in frameworks:
            stats = service.get_industry_statistics(fw.industry_code)
            framework_stats.append({"framework": fw.to_dict(), "stats": stats})

        return render_template(
            "industry_apqc/dashboard.html",
            frameworks=frameworks,
            framework_stats=framework_stats,
        )
    except Exception as e:
        return render_template(
            "industry_apqc/dashboard.html",
            frameworks=[],
            framework_stats=[],
            error=str(e),
        )


@industry_apqc_bp.route("/framework/<industry_code>")
@login_required
def industry_apqc_framework_detail(industry_code):
    """Detail view for a specific industry framework."""
    try:
        service = IndustryAPQCService()
        framework = service.get_framework_by_code(industry_code)

        if not framework:
            return render_template("errors/404.html"), 404

        processes = service.get_industry_processes(industry_code)
        unique_processes = service.get_industry_unique_processes(industry_code)
        regulatory_processes = service.get_regulatory_processes(industry_code)
        stats = service.get_industry_statistics(industry_code)

        return render_template(
            "industry_apqc/framework_detail.html",
            framework=framework,
            processes=processes,
            unique_processes=unique_processes,
            regulatory_processes=regulatory_processes,
            stats=stats,
        )
    except Exception as e:
        return jsonify({"error": "An internal error occurred"}), 500


@industry_apqc_bp.route("/recommendations")
@login_required
def industry_apqc_recommendations():
    """View pending recommendations across all industries."""
    try:
        service = IndustryAPQCService()

        industry_code = request.args.get("industry")
        quick_wins_only = request.args.get("quick_wins", "false").lower() == "true"

        recommendations = service.get_pending_recommendations(
            industry_code=industry_code, quick_wins_only=quick_wins_only
        )

        frameworks = service.get_all_frameworks()

        return render_template(
            "industry_apqc/recommendations.html",
            recommendations=recommendations,
            frameworks=frameworks,
            selected_industry=industry_code,
            quick_wins_only=quick_wins_only,
        )
    except Exception:
        current_app.logger.error(
            "industry_apqc_recommendations failed", exc_info=True
        )
        return jsonify({"error": "An internal error occurred"}), 500


# =========================================================================
# API ENDPOINTS (Industry-specific)
# =========================================================================


@industry_apqc_bp.route("/api/frameworks")
@login_required
def api_industry_apqc_frameworks():
    """API: Get all industry frameworks."""
    try:
        service = IndustryAPQCService()
        frameworks = service.get_all_frameworks()
        return jsonify(
            {"success": True, "frameworks": [fw.to_dict() for fw in frameworks]}
        )
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@industry_apqc_bp.route("/api/frameworks/<industry_code>")
@login_required
def api_industry_apqc_framework(industry_code):
    """API: Get specific framework details."""
    try:
        service = IndustryAPQCService()
        framework = service.get_framework_by_code(industry_code)

        if not framework:
            return jsonify({"success": False, "error": "Framework not found"}), 404

        return jsonify({"success": True, "framework": framework.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@industry_apqc_bp.route("/api/frameworks/<industry_code>/processes")
@login_required
def api_industry_apqc_processes(industry_code):
    """API: Get processes for an industry framework."""
    try:
        service = IndustryAPQCService()
        processes = service.get_industry_processes(industry_code)

        return jsonify(
            {
                "success": True,
                "industry_code": industry_code,
                "processes": [p.to_dict() for p in processes],
                "total": len(processes),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@industry_apqc_bp.route("/api/frameworks/<industry_code>/statistics")
@login_required
def api_industry_apqc_statistics(industry_code):
    """API: Get statistics for an industry framework."""
    try:
        service = IndustryAPQCService()
        stats = service.get_industry_statistics(industry_code)

        if not stats:
            return jsonify({"success": False, "error": "Framework not found"}), 404

        return jsonify({"success": True, "statistics": stats})
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@industry_apqc_bp.route("/api/recommendations", methods=["POST"])
@login_required
@audit_log("apqc_recommendations_generate")
def api_generate_recommendations():
    """API: Generate recommendations based on maturity assessment."""
    try:
        data = request.get_json()

        industry_code = data.get("industry_code")
        maturity_data = data.get("maturity_data", {})
        automation_data = data.get("automation_data")
        focus_areas = data.get("focus_areas")
        max_recommendations = data.get("max_recommendations", 10)

        if not industry_code:
            return jsonify(
                {"success": False, "error": "industry_code is required"}
            ), 400

        service = IndustryAPQCService()
        recommendations = service.generate_recommendations(
            industry_code=industry_code,
            current_maturity_data=maturity_data,
            current_automation_data=automation_data,
            focus_areas=focus_areas,
            max_recommendations=max_recommendations,
        )

        return jsonify(
            {
                "success": True,
                "recommendations": [
                    r.to_dict() if hasattr(r, "to_dict") else str(r)
                    for r in recommendations
                ],
                "total": len(recommendations),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@industry_apqc_bp.route(
    "/api/recommendations/<int:recommendation_id>/accept", methods=["POST"]
)
@login_required
@audit_log("apqc_recommendation_accept")
def api_accept_recommendation(recommendation_id):
    """API: Accept a recommendation."""
    try:
        service = IndustryAPQCService()
        result = service.accept_recommendation(
            recommendation_id=recommendation_id, user_id=current_user.id
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@industry_apqc_bp.route(
    "/api/recommendations/<int:recommendation_id>/reject", methods=["POST"]
)
@login_required
@audit_log("apqc_recommendation_reject")
def api_reject_recommendation(recommendation_id):
    """API: Reject a recommendation."""
    try:
        data = request.get_json()
        reason = data.get("reason", "No reason provided")

        service = IndustryAPQCService()
        result = service.reject_recommendation(
            recommendation_id=recommendation_id, user_id=current_user.id, reason=reason
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@industry_apqc_bp.route("/api/seed-frameworks", methods=["POST"])
@login_required
@audit_log("apqc_frameworks_seed")
def api_seed_frameworks():
    """API: Seed default industry frameworks (admin only)."""
    try:
        # Check if user has admin role
        if not current_user.is_admin():
            return jsonify({"success": False, "error": "Admin access required"}), 403

        service = IndustryAPQCService()
        created = service.seed_default_frameworks()

        return jsonify(
            {
                "success": True,
                "created_frameworks": [fw.to_dict() for fw in created],
                "total_created": len(created),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
