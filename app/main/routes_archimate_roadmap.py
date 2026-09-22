"""ArchiMate 3.2 Implementation & Migration Roadmap Routes - Option 2"""

import logging
from datetime import datetime  # dead-code-ok

from flask import jsonify, request, redirect, url_for
from flask_login import current_user, login_required

from app import db

# Import main blueprint from views to avoid circular import
from app.main.views import main
from app.models.archimate_core import ArchiMateElement
from app.models.unified_capability import UnifiedCapability  # dead-code-ok
from app.models.unified_work_package import UnifiedWorkPackage

logger = logging.getLogger(__name__)


@main.route("/archimate-roadmap")
@login_required
def archimate_roadmap():
    """The ArchiMate roadmap moved to the single Roadmaps page; redirect there."""
    return redirect(url_for("main.capability_roadmap"))


@main.route("/api/archimate-work-packages", methods=["GET"])
@login_required
def get_archimate_work_packages():
    """API endpoint for ArchiMate work packages with level filtering"""
    try:
        # Get filter parameters
        selected_levels = request.args.getlist("levels") or ["L1", "L2", "L3"]
        request.args.get("domain", "")
        request.args.get("importance", "")

        # Convert level strings to integers
        ([
            int(level[1])
            for level in selected_levels
            if level.startswith("L") and level[1:].isdigit()
        ])

        # Use ORM without backend filtering (let frontend handle filtering)
        work_packages_query = UnifiedWorkPackage.query.filter(
            UnifiedWorkPackage.layer.in_(
                ["implementation", "business", "application", "technology"]
            )
        )

        # Get all work packages without filtering - frontend will handle filtering
        all_work_packages = work_packages_query.order_by(
            UnifiedWorkPackage.start_date.asc(), UnifiedWorkPackage.priority.desc()
        ).all()

        # Batch-prefetch capabilities and elements to avoid N+1 queries
        api_cap_names = {wp.business_capability for wp in all_work_packages if wp.business_capability}
        api_caps_by_name = {
            c.name: c for c in UnifiedCapability.query.filter(UnifiedCapability.name.in_(api_cap_names)).all()
        } if api_cap_names else {}

        api_element_ids = {wp.archimate_element_id for wp in all_work_packages if wp.archimate_element_id}
        api_elements_by_id = {
            e.id: e for e in ArchiMateElement.query.filter(ArchiMateElement.id.in_(api_element_ids)).all()
        } if api_element_ids else {}

        work_packages_list = []
        for wp in all_work_packages:
            capability = api_caps_by_name.get(wp.business_capability)

            # Get linked element capabilities
            element_capabilities = []
            if wp.archimate_element_id:
                element = api_elements_by_id.get(wp.archimate_element_id)
                if element:
                    element_capabilities = [c.name for c in element.unified_capabilities]

            work_packages_list.append(
                {
                    "id": wp.id,
                    "name": wp.name,
                    "description": wp.description or "",
                    "business_capability": wp.business_capability,
                    "capability_name": wp.business_capability,
                    "element_capabilities": element_capabilities,
                    "capability_level": f"L{capability.level}" if capability else "Unknown",
                    "capability_level_int": capability.level if capability else 0,
                    "domain_name": "Unknown",  # Default since domains table doesn't exist
                    "domain_code": "UNK",  # Default since domains table doesn't exist
                    "strategic_importance": capability.strategic_importance
                    if capability
                    else "medium",
                    "assigned_to": wp.assigned_to or "Unassigned",
                    "status": wp.status,
                    "start_date": wp.start_date.isoformat() if wp.start_date else None,
                    "end_date": wp.end_date.isoformat() if wp.end_date else None,
                    "progress_percentage": wp.progress_percentage or 0,
                    "estimated_cost": wp.estimated_cost or 0,
                    "priority": wp.priority,
                    "risk_level": wp.risk_level,
                    "layer": wp.layer,
                    "element_type": wp.element_type,
                }
            )

        return jsonify({"work_packages": work_packages_list})
    except Exception as e:
        logger.error("Error getting ArchiMate work packages: %s", e, exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@main.route("/api/archimate-work-packages", methods=["POST"])
@login_required
def create_archimate_work_package():
    """Create new ArchiMate work package"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ["name", "business_capability", "start_date", "end_date"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Create new work package
        new_wp = UnifiedWorkPackage(
            name=data["name"],
            description=data.get("description", ""),
            business_capability=data["business_capability"],
            assigned_to=data.get("assigned_to", "Unassigned"),
            status=data.get("status", "planned"),
            start_date=datetime.fromisoformat(data["start_date"])
            if isinstance(data["start_date"], str)
            else data["start_date"],
            end_date=datetime.fromisoformat(data["end_date"])
            if isinstance(data["end_date"], str)
            else data["end_date"],
            progress_percentage=data.get("progress_percentage", 0),
            estimated_cost=data.get("estimated_cost", 0),
            priority=data.get("priority", "medium"),
            risk_level=data.get("risk_level", "medium"),
            layer="implementation",  # Default layer for roadmap work packages
            element_type="WorkPackage",
            created_by=current_user.id,
        )

        db.session.add(new_wp)
        db.session.commit()

        # Return the created work package
        return jsonify(
            {
                "success": True,
                "work_package": {
                    "id": new_wp.id,
                    "name": new_wp.name,
                    "description": new_wp.description,
                    "business_capability": new_wp.business_capability,
                    "assigned_to": new_wp.assigned_to,
                    "status": new_wp.status,
                    "start_date": new_wp.start_date.isoformat(),
                    "end_date": new_wp.end_date.isoformat(),
                    "progress_percentage": new_wp.progress_percentage,
                    "estimated_cost": new_wp.estimated_cost,
                    "priority": new_wp.priority,
                    "risk_level": new_wp.risk_level,
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        logger.error("Error creating ArchiMate work package: %s", e, exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@main.route("/api/archimate-work-packages/<int:wp_id>", methods=["PUT"])
@login_required
def update_archimate_work_package(wp_id):
    """Update ArchiMate work package"""
    try:
        data = request.get_json()

        # Get existing work package
        work_package = UnifiedWorkPackage.query.get_or_404(wp_id)

        # Update fields
        if "name" in data:
            work_package.name = data["name"]
        if "description" in data:
            work_package.description = data["description"]
        if "business_capability" in data:
            work_package.business_capability = data["business_capability"]
        if "assigned_to" in data:
            work_package.assigned_to = data["assigned_to"]
        if "status" in data:
            work_package.status = data["status"]
        if "start_date" in data:
            work_package.start_date = (
                datetime.fromisoformat(data["start_date"])
                if isinstance(data["start_date"], str)
                else data["start_date"]
            )
        if "end_date" in data:
            work_package.end_date = (
                datetime.fromisoformat(data["end_date"])
                if isinstance(data["end_date"], str)
                else data["end_date"]
            )
        if "progress_percentage" in data:
            work_package.progress_percentage = data["progress_percentage"]
        if "estimated_cost" in data:
            work_package.estimated_cost = data["estimated_cost"]
        if "priority" in data:
            work_package.priority = data["priority"]
        if "risk_level" in data:
            work_package.risk_level = data["risk_level"]

        work_package.updated_by = current_user.id
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "work_package": {
                    "id": work_package.id,
                    "name": work_package.name,
                    "description": work_package.description,
                    "business_capability": work_package.business_capability,
                    "assigned_to": work_package.assigned_to,
                    "status": work_package.status,
                    "start_date": work_package.start_date.isoformat(),
                    "end_date": work_package.end_date.isoformat(),
                    "progress_percentage": work_package.progress_percentage,
                    "estimated_cost": work_package.estimated_cost,
                    "priority": work_package.priority,
                    "risk_level": work_package.risk_level,
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        logger.error("Error updating ArchiMate work package: %s", e, exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500


@main.route("/api/archimate-work-packages/<int:wp_id>", methods=["DELETE"])
@login_required
def delete_archimate_work_package(wp_id):
    """Delete ArchiMate work package"""
    try:
        # Get existing work package
        work_package = UnifiedWorkPackage.query.get_or_404(wp_id)

        # Delete work package
        db.session.delete(work_package)
        db.session.commit()

        return jsonify({"success": True, "message": f"ArchiMate work package {wp_id} deleted"})

    except Exception as e:
        db.session.rollback()
        logger.error("Error deleting ArchiMate work package %d: %s", wp_id, e, exc_info=True)
        return jsonify({"error": "An internal error occurred"}), 500
