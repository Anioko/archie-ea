"""
Application Capability Tagging Routes

Integrates capability tagging system with application management.
Provides endpoints for tagging applications with capabilities, analyzing gaps,
and tracking tagging analytics.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app import db
from app.decorators import audit_log
from app.models.application_portfolio import ApplicationComponent
from app.models.capability_tagging import CapabilityTag
from app.services.capability_tagging_service import CapabilityTagService

application_tags_bp = Blueprint(
    "application_tags", __name__, url_prefix="/dashboard/api/applications"
)


@application_tags_bp.route("/<int:app_id>/tags", methods=["GET"])
@login_required
def get_application_tags(app_id):
    """Get all capability tags for an application."""
    try:
        app = ApplicationComponent.query.get_or_404(app_id)
        service = CapabilityTagService()

        # Get tags through the application's capability relationships
        tags = []
        if hasattr(app, "capability_tags"):
            for tag in app.capability_tags:
                tags.append(
                    {
                        "id": tag.id,
                        "name": tag.name,
                        "category": tag.category,
                        "description": tag.description,
                        "color": tag.color,
                        "icon": tag.icon,
                    }
                )

        return jsonify(
            {
                "success": True,
                "application_id": app_id,
                "application_name": app.name,
                "tags": tags,
                "total": len(tags),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@application_tags_bp.route("/<int:app_id>/tags", methods=["POST"])
@login_required
@audit_log("application_tag")
def tag_application(app_id):
    """Tag an application with multiple capability tags."""
    try:
        app = ApplicationComponent.query.get_or_404(app_id)
        data = request.get_json()

        if not data or "tag_ids" not in data:
            return jsonify({"success": False, "error": "Missing tag_ids"}), 400

        tag_ids = data["tag_ids"]

        # Clear existing tags
        if hasattr(app, "capability_tags"):
            app.capability_tags.clear()

        # Add new tags
        for tag_id in tag_ids:
            tag = CapabilityTag.query.get(tag_id)
            if tag:
                app.capability_tags.append(tag)

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": f"Application {app.name} tagged successfully",
                "tag_ids": tag_ids,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@application_tags_bp.route("/capability-gaps", methods=["GET"])
@login_required
def get_capability_gaps():
    """Get capability gap analysis for applications."""
    try:
        service = CapabilityTagService()

        # Get all applications
        applications = ApplicationComponent.query.limit(2000).all()

        # Get all capability tags
        all_tags = service.get_all_tags()

        # Analyze gaps
        gaps = []
        for tag in all_tags:
            if tag["usage"]["total"] == 0:
                gaps.append(
                    {"tag": tag, "gap_type": "unused_capability", "severity": "medium"}
                )

        return jsonify(
            {
                "success": True,
                "total_applications": len(applications),
                "total_tags": len(all_tags),
                "capability_gaps": gaps,
                "gap_percentage": len(gaps) / len(all_tags) * 100 if all_tags else 0,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@application_tags_bp.route("/tag-analytics", methods=["GET"])
@login_required
def get_tag_analytics():
    """Get analytics for application capability tagging."""
    try:
        service = CapabilityTagService()

        # Get tag statistics
        stats = service.get_tag_statistics()

        # Get application-specific analytics
        applications = ApplicationComponent.query.all()

        tagged_applications = 0
        untagged_applications = 0

        for app in applications:
            if hasattr(app, "capability_tags") and app.capability_tags.count() > 0:
                tagged_applications += 1
            else:
                untagged_applications += 1

        return jsonify(
            {
                "success": True,
                "tag_statistics": stats,
                "application_analytics": {
                    "total_applications": len(applications),
                    "tagged_applications": tagged_applications,
                    "untagged_applications": untagged_applications,
                    "tagging_coverage": (tagged_applications / len(applications) * 100)
                    if applications
                    else 0,
                },
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
