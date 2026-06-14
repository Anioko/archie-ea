"""
Migration: Copied from app/routes/enterprise_crud_routes.py -> app/modules/capabilities/routes/
Date: 2026-02-14 | Relative imports fixed for new location.

Enterprise CRUD Routes

Routes for managing enterprise capabilities, compliance policies, and violations.
Provides full CRUD operations with RBAC enforcement and audit logging.
"""

import logging
from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.decorators import audit_log, require_roles
from app.models.business_capabilities import BusinessCapability
from app.models.compliance_models import CompliancePolicy, ComplianceViolation
from app.services.enterprise_validation_service import EnterpriseValidationService
from app.services.enterprise_audit_log import EnterpriseAuditLog
from app.services.enterprise_search_service import EnterpriseSearchService

logger = logging.getLogger(__name__)

enterprise_crud_bp = Blueprint("enterprise_crud", __name__, url_prefix="/enterprise")


# ============================================================================
# CAPABILITY CRUD OPERATIONS
# ============================================================================


@enterprise_crud_bp.route("/capabilities", methods=["GET"])
@login_required
def list_capabilities():
    """List all capabilities with pagination and filtering."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        search = request.args.get("search", "", type=str)
        filter_type = request.args.get("type", "", type=str)
        filter_health = request.args.get("health", "", type=str)

        query = BusinessCapability.query

        # Apply search filter
        if search:
            query = query.filter(
                (BusinessCapability.name.ilike(f"%{search}%"))
                | (BusinessCapability.description.ilike(f"%{search}%"))
            )

        # Apply type filter (maps to category field)
        if filter_type:
            query = query.filter(BusinessCapability.category == filter_type)

        # Sort by name for APQC ordering (01, 02, ... 11, then 1.1, 1.2, etc.)
        query = query.order_by(BusinessCapability.level, BusinessCapability.name)

        # Pagination
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify(
            {
                "success": True,
                "data": {
                    "capabilities": [cap.to_dict() for cap in paginated.items],
                    "total": paginated.total,
                    "pages": paginated.pages,
                    "current_page": page,
                    "per_page": per_page,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error listing capabilities: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/capabilities/app-counts", methods=["GET"])
@login_required
def capability_app_counts():
    """Return app counts for all capabilities in one query."""
    try:
        from app.models.business_capabilities import ApplicationCapabilityCoverage
        rows = (
            db.session.query(
                ApplicationCapabilityCoverage.capability_id,
                db.func.count(ApplicationCapabilityCoverage.id),
            )
            .group_by(ApplicationCapabilityCoverage.capability_id)
            .all()
        )
        counts = {str(cid): cnt for cid, cnt in rows}
        return jsonify({"success": True, "counts": counts})
    except Exception as e:
        logger.error(f"Error getting app counts: {e}")
        return jsonify({"success": True, "counts": {}})


@enterprise_crud_bp.route("/capabilities/<int:capability_id>", methods=["GET"])
@login_required
def get_capability(capability_id):
    """Get a specific capability detail."""
    try:
        capability = BusinessCapability.query.get(capability_id)
        if not capability:
            return jsonify({"success": False, "error": "Capability not found"}), 404

        data = capability.to_dict()
        # Include app coverage mappings
        from app.models.business_capabilities import ApplicationCapabilityCoverage
        from app.models.application_portfolio import ApplicationComponent
        coverages = (
            db.session.query(ApplicationCapabilityCoverage, ApplicationComponent)
            .join(ApplicationComponent, ApplicationCapabilityCoverage.application_component_id == ApplicationComponent.id)
            .filter(ApplicationCapabilityCoverage.capability_id == capability_id)
            .limit(50)
            .all()
        )
        data["applications"] = [
            {
                "id": ac.id,
                "name": ac.name,
                "support_level": cov.support_level,
                "confidence": cov.confidence_score,
            }
            for cov, ac in coverages
        ]
        data["application_count"] = (
            ApplicationCapabilityCoverage.query
            .filter_by(capability_id=capability_id)
            .count()
        )
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Error getting capability {capability_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/capabilities", methods=["POST"])
@login_required
@require_roles("admin", "architect")
@audit_log("capability_create")
def create_capability():
    """Create a new capability."""
    try:
        data = request.get_json() or {}

        # Validate input
        is_valid, errors = EnterpriseValidationService.validate_capability(data)
        if not is_valid:
            return (
                jsonify({"success": False, "error": "Validation failed", "errors": errors}),
                400,
            )

        # Check if capability name already exists
        existing = BusinessCapability.query.filter_by(name=data["name"]).first()
        if existing:
            return (
                jsonify({"success": False, "error": "Capability with this name already exists"}),
                409,
            )

        # Create capability
        capability = BusinessCapability(
            name=data["name"],
            category=data.get("type", "operational"),
            description=data.get("description", ""),
            level=data.get("level", 1),
        )

        db.session.add(capability)
        db.session.commit()

        # Audit log
        EnterpriseAuditLog.log_capability_created(
            current_user.id,
            capability.name,
            {"category": capability.category, "level": capability.level},
        )

        logger.info(f"Capability created: {capability.name} (ID: {capability.id})")
        return jsonify({"success": True, "data": capability.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating capability: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/capabilities/<int:capability_id>", methods=["PUT"])
@login_required
@require_roles("admin", "architect")
@audit_log("capability_update")
def update_capability(capability_id):
    """Update an existing capability."""
    try:
        capability = BusinessCapability.query.get(capability_id)
        if not capability:
            return jsonify({"success": False, "error": "Capability not found"}), 404

        data = request.get_json() or {}

        # Validate input
        is_valid, errors = EnterpriseValidationService.validate_capability(data)
        if not is_valid:
            return (
                jsonify({"success": False, "error": "Validation failed", "errors": errors}),
                400,
            )

        # Check for duplicate name (if name is being changed)
        if "name" in data and data["name"] != capability.name:
            existing = BusinessCapability.query.filter_by(name=data["name"]).first()
            if existing:
                return (
                    jsonify({"success": False, "error": "Capability with this name already exists"}),
                    409,
                )

        # Track changes for audit
        changes = {}
        if "name" in data and data["name"] != capability.name:
            changes["name"] = {"from": capability.name, "to": data["name"]}
            capability.name = data["name"]
        if "type" in data and data["type"] != capability.category:
            changes["type"] = {
                "from": capability.category,
                "to": data["type"],
            }
            capability.category = data["type"]
        if "description" in data and data["description"] != capability.description:
            changes["description"] = {"from": capability.description, "to": data["description"]}
            capability.description = data["description"]
        if "level" in data and data["level"] != capability.level:
            changes["level"] = {
                "from": capability.level,
                "to": data["level"],
            }
            capability.level = data["level"]

        db.session.commit()

        # Audit log
        if changes:
            EnterpriseAuditLog.log_capability_updated(current_user.id, capability_id, changes)
            logger.info(f"Capability updated: {capability.name} (ID: {capability_id})")

        return jsonify({"success": True, "data": capability.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating capability {capability_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/capabilities/<int:capability_id>", methods=["DELETE"])
@login_required
@require_roles("admin")
@audit_log("capability_delete")
def delete_capability(capability_id):
    """Delete a capability."""
    try:
        capability = BusinessCapability.query.get(capability_id)
        if not capability:
            return jsonify({"success": False, "error": "Capability not found"}), 404

        cap_name = capability.name

        db.session.delete(capability)
        db.session.commit()

        # Audit log
        EnterpriseAuditLog.log_capability_deleted(current_user.id, capability_id, cap_name)
        logger.info(f"Capability deleted: {cap_name} (ID: {capability_id})")

        return jsonify({"success": True, "message": "Capability deleted successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting capability {capability_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# ============================================================================
# COMPLIANCE MANAGEMENT OPERATIONS
# ============================================================================


@enterprise_crud_bp.route("/compliance", methods=["GET"])
@login_required
def compliance_dashboard():
    """Get compliance dashboard with statistics."""
    try:
        total_policies = CompliancePolicy.query.count()
        total_violations = ComplianceViolation.query.count()
        critical_violations = ComplianceViolation.query.filter_by(severity="Critical").count()
        open_violations = ComplianceViolation.query.filter_by(status="Open").count()

        return jsonify(
            {
                "success": True,
                "data": {
                    "total_policies": total_policies,
                    "total_violations": total_violations,
                    "critical_violations": critical_violations,
                    "open_violations": open_violations,
                    "compliance_score": max(0, 100 - (critical_violations * 10)),
                },
            }
        )
    except Exception as e:
        logger.error(f"Error getting compliance dashboard: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/compliance/policies", methods=["GET"])
@login_required
def list_compliance_policies():
    """List all compliance policies."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        filter_type = request.args.get("type", "", type=str)

        query = CompliancePolicy.query

        if filter_type:
            query = query.filter(CompliancePolicy.policy_type == filter_type)

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        return jsonify(
            {
                "success": True,
                "data": {
                    "policies": [p.to_dict() for p in paginated.items],
                    "total": paginated.total,
                    "pages": paginated.pages,
                    "current_page": page,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error listing compliance policies: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/compliance/policies", methods=["POST"])
@login_required
@require_roles("admin", "compliance_officer")
@audit_log("compliance_policy_create")
def create_compliance_policy():
    """Create a new compliance policy."""
    try:
        data = request.get_json() or {}

        # Validate input
        is_valid, errors = EnterpriseValidationService.validate_compliance_policy(data)
        if not is_valid:
            return (
                jsonify({"success": False, "error": "Validation failed", "errors": errors}),
                400,
            )

        # Check for duplicate
        existing = CompliancePolicy.query.filter_by(name=data["name"]).first()
        if existing:
            return (
                jsonify({"success": False, "error": "Policy with this name already exists"}),
                409,
            )

        # Create policy
        policy = CompliancePolicy(
            name=data["name"],
            policy_type=data.get("type", "NIST"),
            description=data.get("description", ""),
        )

        db.session.add(policy)
        db.session.commit()

        # Audit log
        EnterpriseAuditLog.log_compliance_change(
            current_user.id,
            "policy_created",
            policy.id,
            {"name": policy.name, "type": policy.policy_type},
        )

        logger.info(f"Compliance policy created: {policy.name} (ID: {policy.id})")
        return jsonify({"success": True, "data": policy.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating compliance policy: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/compliance/violations", methods=["GET"])
@login_required
def list_compliance_violations():
    """List all compliance violations."""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        filter_severity = request.args.get("severity", "", type=str)
        filter_status = request.args.get("status", "", type=str)

        query = ComplianceViolation.query

        if filter_severity:
            query = query.filter(ComplianceViolation.severity == filter_severity)
        if filter_status:
            query = query.filter(ComplianceViolation.status == filter_status)

        paginated = query.order_by(ComplianceViolation.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify(
            {
                "success": True,
                "data": {
                    "violations": [v.to_dict() for v in paginated.items],
                    "total": paginated.total,
                    "pages": paginated.pages,
                    "current_page": page,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error listing compliance violations: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/compliance/violations", methods=["POST"])
@login_required
@require_roles("admin", "compliance_officer")
@audit_log("compliance_violation_create")
def create_compliance_violation():
    """Log a new compliance violation."""
    try:
        data = request.get_json() or {}

        # Validate input
        is_valid, errors = EnterpriseValidationService.validate_compliance_violation(data)
        if not is_valid:
            return (
                jsonify({"success": False, "error": "Validation failed", "errors": errors}),
                400,
            )

        # Verify policy exists
        policy = CompliancePolicy.query.get(data["policy_id"])
        if not policy:
            return jsonify({"success": False, "error": "Policy not found"}), 404

        # Create violation
        violation = ComplianceViolation(
            policy_id=data["policy_id"],
            severity=data.get("severity", "Medium"),
            description=data.get("description", ""),
            status="Open",
        )

        db.session.add(violation)
        db.session.commit()

        # Audit log
        EnterpriseAuditLog.log_violation_logged(
            current_user.id,
            violation.id,
            data.get("severity", "Medium"),
        )

        logger.info(f"Compliance violation logged: {violation.id} for policy {policy.name}")
        return jsonify({"success": True, "data": violation.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating compliance violation: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/compliance/violations/<int:violation_id>", methods=["PUT"])
@login_required
@require_roles("admin", "compliance_officer")
@audit_log("compliance_violation_update")
def update_compliance_violation(violation_id):
    """Update compliance violation status."""
    try:
        violation = ComplianceViolation.query.get(violation_id)
        if not violation:
            return jsonify({"success": False, "error": "Violation not found"}), 404

        data = request.get_json() or {}

        # Validate status
        valid_statuses = ["Open", "In Progress", "Resolved"]
        if "status" in data and data["status"] not in valid_statuses:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                    }
                ),
                400,
            )

        old_status = violation.status
        if "status" in data:
            violation.status = data["status"]
        if "remediation_plan" in data:
            violation.remediation_plan = data["remediation_plan"]

        db.session.commit()

        # Audit log
        if old_status != violation.status:
            EnterpriseAuditLog.log_compliance_change(
                current_user.id,
                "violation_updated",
                violation_id,
                {"status": {"from": old_status, "to": violation.status}},
            )

        logger.info(f"Compliance violation updated: {violation_id} status now {violation.status}")
        return jsonify({"success": True, "data": violation.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating compliance violation {violation_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@enterprise_crud_bp.route("/compliance/violations/<int:violation_id>", methods=["DELETE"])
@login_required
@require_roles("admin")
@audit_log("compliance_violation_delete")
def delete_compliance_violation(violation_id):
    """Delete a compliance violation."""
    try:
        violation = ComplianceViolation.query.get(violation_id)
        if not violation:
            return jsonify({"success": False, "error": "Violation not found"}), 404

        db.session.delete(violation)
        db.session.commit()

        # Audit log
        EnterpriseAuditLog.log_compliance_change(
            current_user.id,
            "violation_deleted",
            violation_id,
            {"id": violation_id},
        )

        logger.info(f"Compliance violation deleted: {violation_id}")
        return jsonify({"success": True, "message": "Violation deleted successfully"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting compliance violation {violation_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# ============================================================================
# SEARCH & REPORTING OPERATIONS
# ============================================================================


@enterprise_crud_bp.route("/search", methods=["GET"])
@login_required
def enterprise_search():
    """Search across capabilities and compliance."""
    try:
        query = request.args.get("q", "", type=str)
        entity_type = request.args.get("type", "all", type=str)  # all, capability, compliance
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        if not query or len(query) < 2:
            return (
                jsonify({"success": False, "error": "Query must be at least 2 characters"}),
                400,
            )

        results = EnterpriseSearchService.search(query, entity_type, page, per_page)

        return jsonify(
            {
                "success": True,
                "data": results,
            }
        )
    except Exception as e:
        logger.error(f"Error searching: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


# ============================================================================
# TPM REPLACEMENT — Requirements Backlog & Traceability Dashboard Pages
# ============================================================================


@enterprise_crud_bp.route("/requirements-backlog", methods=["GET"])
@login_required
def requirements_backlog():
    """Requirements Backlog — TPM replacement lifecycle management page."""
    from app.models.business_capabilities import BusinessCapability as BC
    capabilities = BC.query.order_by(BC.name).all()
    return render_template("enterprise/requirements_backlog.html", capabilities=capabilities)


@enterprise_crud_bp.route("/requirements-traceability", methods=["GET"])
@login_required
def requirements_traceability():
    """Requirements Traceability Dashboard — Driver → Goal → Capability → Requirement → Solution → ADM."""
    from app.models.solution_architect_models import SolutionRequirement
    from app.models.business_capabilities import BusinessCapability as BC
    from app.models.archimate_core import ArchiMateElement

    reqs = (
        SolutionRequirement.query
        .order_by(SolutionRequirement.status, SolutionRequirement.id)
        .limit(300)
        .all()
    )
    cap_map = {c.id: c.name for c in BC.query.all()}
    driver_map = {
        d.id: d.name for d in ArchiMateElement.query.filter(
            ArchiMateElement.type == "Driver",
            ArchiMateElement.name.isnot(None), ArchiMateElement.name != "",
        ).all()
    }
    goal_map = {
        g.id: g.name for g in ArchiMateElement.query.filter(
            ArchiMateElement.type.in_(["Goal", "Outcome"]),
            ArchiMateElement.name.isnot(None), ArchiMateElement.name != "",
        ).all()
    }
    caps_json = [{"id": k, "name": v} for k, v in cap_map.items()]
    return render_template(
        "enterprise/requirements_traceability.html",
        requirements=reqs,
        cap_map=cap_map,
        driver_map=driver_map,
        goal_map=goal_map,
        caps_json=caps_json,
    )
