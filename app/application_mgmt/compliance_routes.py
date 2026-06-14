"""API routes for compliance framework management."""

from flask import current_app, jsonify, request
from flask_login import current_user, login_required

from app import db
from app.application_mgmt import application_mgmt
from app.models.application_compliance import ApplicationComplianceControl
from app.models.application_portfolio import ApplicationComponent  # dead-code-ok
from app.models.compliance_models import ComplianceControl, RegulatoryFramework


@application_mgmt.route("/api/compliance/frameworks", methods=["GET"])
@login_required
def get_compliance_frameworks():
    """Get all active compliance frameworks."""
    frameworks = RegulatoryFramework.query.filter_by(status="active").all()
    return jsonify(
        [
            {
                "id": f.id,
                "code": f.code,
                "name": f.name,
                "description": f.description,
                "category": f.category,
                "enforcement_level": f.enforcement_level,
                "control_count": f.controls.count(),
            }
            for f in frameworks
        ]
    )


@application_mgmt.route("/api/compliance/frameworks/<int:framework_id>/controls", methods=["GET"])
@login_required
def get_framework_controls(framework_id):
    """Get all controls for a framework."""
    category = request.args.get("category")

    query = ComplianceControl.query.filter_by(framework_id=framework_id)

    if category:
        query = query.filter_by(category=category)

    controls = query.order_by(ComplianceControl.control_code).all()
    return jsonify(
        [
            {
                "id": c.id,
                "control_code": c.control_code,
                "title": c.title,
                "description": c.description,
                "category": c.category,
                "priority": c.priority,
            }
            for c in controls
        ]
    )


@application_mgmt.route("/api/applications/<string:app_id>/compliance", methods=["GET"])
@login_required
def get_application_compliance(app_id):
    """Get compliance control mappings for an application."""
    mappings = ApplicationComplianceControl.query.filter_by(application_id=app_id).all()

    result = {
        "application_id": app_id,
        "mappings": [m.to_dict() for m in mappings],
        "summary": {
            "total_controls": len(mappings),
            "implemented": len([m for m in mappings if m.status == "implemented"]),
            "planned": len([m for m in mappings if m.status == "planned"]),
            "not_implemented": len([m for m in mappings if m.status == "not_implemented"]),
        },
    }

    return jsonify(result)


@application_mgmt.route("/api/applications/<string:app_id>/compliance/map", methods=["POST"])
@login_required
def map_compliance_control(app_id):
    """Map a compliance control to an application component."""
    data = request.get_json()

    if not data or "control_id" not in data:
        return jsonify({"error": "control_id required"}), 400

    # Check if mapping already exists
    existing = ApplicationComplianceControl.query.filter_by(
        control_id=data["control_id"], application_id=app_id
    ).first()

    if existing:
        return jsonify({"error": "Mapping already exists"}), 409

    try:
        mapping = ApplicationComplianceControl(
            application_id=app_id,
            control_id=data["control_id"],
            status=data.get("status", "not_implemented"),
            coverage_percentage=data.get("coverage_percentage", 0),
            implementation_notes=data.get("implementation_notes"),
            evidence=data.get("evidence"),
        )

        db.session.add(mapping)
        db.session.commit()

        return jsonify({"success": True, "mapping": mapping.to_dict()})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating compliance mapping: {str(e)}")
        return jsonify({"error": "An internal error occurred"}), 500


@application_mgmt.route("/api/compliance/mappings/<int:mapping_id>", methods=["PUT"])
@login_required
def update_compliance_mapping(mapping_id):
    """Update a compliance mapping."""
    mapping = ApplicationComplianceControl.query.get_or_404(mapping_id)
    data = request.get_json()

    try:
        if "status" in data:
            mapping.status = data["status"]
        if "coverage_percentage" in data:
            mapping.coverage_percentage = data["coverage_percentage"]
        if "implementation_notes" in data:
            mapping.implementation_notes = data["implementation_notes"]
        if "evidence" in data:
            mapping.evidence = data["evidence"]

        db.session.commit()

        return jsonify({"success": True, "mapping": mapping.to_dict()})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            "Failed to update compliance mapping mapping_id=%s user=%s: %s",
            mapping_id,
            getattr(current_user, "id", None),
            e,
            exc_info=True,
        )
        return jsonify({"error": "An internal error occurred"}), 500


@application_mgmt.route("/api/compliance/mappings/<int:mapping_id>", methods=["DELETE"])
@login_required
def delete_compliance_mapping(mapping_id):
    """Remove a compliance mapping."""
    mapping = ApplicationComplianceControl.query.get_or_404(mapping_id)

    try:
        db.session.delete(mapping)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            "Failed to delete compliance mapping mapping_id=%s user=%s: %s",
            mapping_id,
            getattr(current_user, "id", None),
            e,
            exc_info=True,
        )
        return jsonify({"error": "An internal error occurred"}), 500
