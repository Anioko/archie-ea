"""
Migration: Copied from app/api/capability_taxonomy_routes.py -> app/modules/capabilities/api/
Date: 2026-02-14 | Relative imports fixed for new location.

Capability Taxonomy Enforcement API Routes

Provides REST API endpoints for capability taxonomy enforcement,
validation, rule management, and violation correction for enterprise architecture.
"""

import logging
from typing import Optional

from flask import Blueprint, jsonify, request

from app.decorators import audit_log
from app.services.capability_taxonomy_service import CapabilityTaxonomyService
from flask_login import login_required

logger = logging.getLogger(__name__)

# Create blueprint
capability_taxonomy_bp = Blueprint(
    "capability_taxonomy", __name__, url_prefix="/api/capability/taxonomy"
)

# Initialize service
taxonomy_service = CapabilityTaxonomyService()


@capability_taxonomy_bp.route("/validate", methods=["POST"])
@login_required
def validate_capability():
    """
    Validate a capability against taxonomy rules.

    Request Body:
        {
            "name": "Strategic Customer Management Capability",
            "description": "Enterprise-level strategic customer relationship management",
            "level": "strategic",
            "domain": "business",
            "parent_id": null
        }

    Returns:
        JSON with validation results and violations
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        capability_data = {
            "name": data.get("name", "").strip(),
            "description": data.get("description", "").strip(),
            "level": data.get("level", "").strip(),
            "domain": data.get("domain", "").strip(),
            "parent_id": data.get("parent_id"),
        }

        auto_correct = data.get("auto_correct", False)
        user_id = data.get("user_id")

        # Validate required fields
        if not capability_data["name"]:
            return jsonify({"success": False, "error": "name is required"}), 400

        # Validate capability
        validation_result = taxonomy_service.validate_capability(
            capability_data, auto_correct, user_id
        )

        return jsonify(
            {
                "success": True,
                "validation_result": {
                    "is_valid": validation_result.is_valid,
                    "violations_count": len(validation_result.violations),
                    "corrections_count": len(validation_result.corrections_applied),
                    "violations": [
                        {
                            "rule_name": v.rule_name,
                            "violation_type": v.violation_type,
                            "severity": v.severity,
                            "message": v.message,
                            "actual_value": v.actual_value,
                            "expected_value": v.expected_value,
                            "can_auto_correct": v.can_auto_correct,
                            "correction_suggestion": v.correction_suggestion,
                        }
                        for v in validation_result.violations
                    ],
                    "corrections": validation_result.corrections_applied,
                    "audit_entries": validation_result.audit_entries,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error validating capability: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_taxonomy_bp.route("/validate-bulk", methods=["POST"])
@login_required
def validate_bulk_capabilities():
    """
    Validate multiple capabilities in bulk.

    Request Body:
        {
            "capabilities": [
                {
                    "name": "Strategic Customer Management Capability",
                    "description": "Enterprise-level strategic customer relationship management",
                    "level": "strategic",
                    "domain": "business"
                },
                {
                    "name": "Customer Relationship Management Capability",
                    "description": "Tactical customer relationship management processes",
                    "level": "tactical",
                    "domain": "business",
                    "parent_id": 123
                }
            ],
            "auto_correct": false,
            "user_id": 789,
            "batch_id": "batch_001"
        }

    Returns:
        JSON with bulk validation results
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        capabilities = data.get("capabilities", [])
        auto_correct = data.get("auto_correct", False)
        user_id = data.get("user_id")
        batch_id = data.get("batch_id")

        if not capabilities:
            return jsonify({"success": False, "error": "capabilities array is required"}), 400

        # Validate capabilities in bulk
        results = taxonomy_service.validate_bulk_capabilities(
            capabilities, auto_correct, user_id, batch_id
        )

        return jsonify({"success": True, "bulk_results": results})

    except Exception as e:
        logger.error(f"Error validating capabilities in bulk: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_taxonomy_bp.route("/rules", methods=["GET"])
@login_required
def get_taxonomy_rules():
    """
    Get active taxonomy rules with optional filtering.

    Query Parameters:
        rule_type (str): Optional rule type filter
        capability_level (str): Optional capability level filter

    Returns:
        JSON with active taxonomy rules
    """
    try:
        rule_type = request.args.get("rule_type")
        capability_level = request.args.get("capability_level")

        rules = taxonomy_service.get_active_rules(rule_type, capability_level)

        return jsonify({"success": True, "rules": rules, "total_rules": len(rules)})

    except Exception as e:
        logger.error(f"Error getting taxonomy rules: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_taxonomy_bp.route("/rules", methods=["POST"])
@login_required
@audit_log("taxonomy_rule_create")
def create_taxonomy_rule():
    """
    Create a new taxonomy rule.

    Request Body:
        {
            "rule_name": "Custom Naming Convention Rule",
            "rule_type": "naming_validation",
            "rule_category": "naming",
            "capability_level": "strategic",
            "domain": "business",
            "rule_pattern": {"pattern": "^Custom [A-Z].*"},
            "description": "Custom naming convention for strategic capabilities",
            "severity": "warning",
            "auto_correct": false,
            "examples": {
                "valid": ["Custom Strategic Capability"],
                "invalid": ["Invalid Name"]
            }
        }

    Returns:
        JSON with rule creation result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        user_id = data.get("user_id")

        if not user_id:
            return (
                jsonify({"success": False, "error": "user_id is required for rule creation"}),
                400,
            )

        # Create rule
        result = taxonomy_service.create_taxonomy_rule(data, user_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error creating taxonomy rule: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_taxonomy_bp.route("/violations", methods=["GET"])
@login_required
def get_taxonomy_violations():
    """
    Get taxonomy violations with optional filtering.

    Query Parameters:
        capability_id (int): Optional capability ID filter
        status (str): Optional status filter (open, corrected, ignored, escalated)
        severity (str): Optional severity filter (info, warning, error, critical)

    Returns:
        JSON with violations
    """
    try:
        capability_id = request.args.get("capability_id", type=int)
        status = request.args.get("status")
        severity = request.args.get("severity")

        violations = taxonomy_service.get_violations(capability_id, status, severity)

        return jsonify(
            {"success": True, "violations": violations, "total_violations": len(violations)}
        )

    except Exception as e:
        logger.error(f"Error getting taxonomy violations: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_taxonomy_bp.route("/violations/<int:violation_id>/correct", methods=["POST"])
@login_required
@audit_log("taxonomy_violation_correct")
def correct_violation(violation_id: int):
    """
    Correct a taxonomy violation.

    Request Body:
        {
            "corrected_value": "Strategic Customer Management Capability",
            "user_id": 789
        }

    Returns:
        JSON with correction result
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        corrected_value = data.get("corrected_value", "").strip()
        user_id = data.get("user_id")

        if not corrected_value:
            return jsonify({"success": False, "error": "corrected_value is required"}), 400

        if not user_id:
            return jsonify({"success": False, "error": "user_id is required for correction"}), 400

        # Correct violation
        result = taxonomy_service.correct_violation(violation_id, corrected_value, user_id)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error correcting violation {violation_id}: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_taxonomy_bp.route("/statistics", methods=["GET"])
@login_required
def get_taxonomy_statistics():
    """
    Get comprehensive taxonomy enforcement statistics.

    Returns:
        JSON with taxonomy statistics
    """
    try:
        statistics = taxonomy_service.get_taxonomy_statistics()

        if "error" in statistics:
            return jsonify({"success": False, "error": statistics["error"]}), 500

        return jsonify({"success": True, "statistics": statistics})

    except Exception as e:
        logger.error(f"Error getting taxonomy statistics: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_taxonomy_bp.route("/level-definitions", methods=["GET"])
@login_required
def get_level_definitions():
    """
    Get capability level definitions.

    Returns:
        JSON with level definitions
    """
    try:
        from app.models.application_capability import CapabilityLevelDefinition

        levels = (
            CapabilityLevelDefinition.query.filter_by(is_active=True)
            .order_by(CapabilityLevelDefinition.level_number)
            .all()
        )

        return jsonify(
            {
                "success": True,
                "levels": [level.to_dict() for level in levels],
                "total_levels": len(levels),
            }
        )

    except Exception as e:
        logger.error(f"Error getting level definitions: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_taxonomy_bp.route("/domain-definitions", methods=["GET"])
@login_required
def get_domain_definitions():
    """
    Get capability domain definitions.

    Returns:
        JSON with domain definitions
    """
    try:
        from app.models.application_capability import CapabilityDomainDefinition

        domains = (
            CapabilityDomainDefinition.query.filter_by(is_active=True)
            .order_by(CapabilityDomainDefinition.strategic_importance.desc())
            .all()
        )

        return jsonify(
            {
                "success": True,
                "domains": [domain.to_dict() for domain in domains],
                "total_domains": len(domains),
            }
        )

    except Exception as e:
        logger.error(f"Error getting domain definitions: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_taxonomy_bp.route("/audit-trail", methods=["GET"])
@login_required
def get_audit_trail():
    """
    Get taxonomy audit trail.

    Query Parameters:
        capability_id (int): Optional capability ID filter
        audit_type (str): Optional audit type filter
        limit (int): Maximum results (default: 100)

    Returns:
        JSON with audit trail
    """
    try:
        from app.models.application_capability import CapabilityTaxonomyAudit

        capability_id = request.args.get("capability_id", type=int)
        audit_type = request.args.get("audit_type")
        limit = min(request.args.get("limit", 100, type=int), 500)

        query = CapabilityTaxonomyAudit.query

        if capability_id:
            query = query.filter_by(capability_id=capability_id)

        if audit_type:
            query = query.filter_by(audit_type=audit_type)

        audits = query.order_by(CapabilityTaxonomyAudit.created_at.desc()).limit(limit).all()

        return jsonify(
            {
                "success": True,
                "audits": [audit.to_dict() for audit in audits],
                "total_audits": len(audits),
            }
        )

    except Exception as e:
        logger.error(f"Error getting audit trail: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


def register_capability_taxonomy_routes(app):
    """Register capability taxonomy blueprint with Flask app."""
    app.register_blueprint(capability_taxonomy_bp)
    logger.info("Capability taxonomy API routes registered")
