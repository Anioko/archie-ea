"""
DEPRECATED: This file is migrated to app/modules/governance/.
Registration is now centralized via app.modules.governance.register().
Do NOT modify -- kept as fallback until Phase 6 cleanup.

Capability Management Routes

Routes for capability naming standardization and duplicate management.
"""

import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.decorators import audit_log, require_roles
from app.models.unified_capability import UnifiedCapability
from app.modules.governance.v2.services import CapabilityNamingService

logger = logging.getLogger(__name__)

capability_management = Blueprint("capability_management", __name__)


@capability_management.route("/naming-dashboard")
@login_required
def naming_dashboard():
    """Main capability naming management dashboard"""
    return render_template("capability_management/governance_dashboard.html")


@capability_management.route("/api/naming-statistics")
@login_required
def api_naming_statistics():
    """API endpoint to get naming statistics"""
    try:
        stats = CapabilityNamingService.get_naming_statistics()
        return jsonify({"success": True, "statistics": stats})
    except Exception as e:
        logger.error(f"Error getting naming statistics: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_management.route("/api/duplicate-capabilities")
@login_required
def api_duplicate_capabilities():
    """API endpoint to get duplicate capabilities"""
    try:
        duplicates = CapabilityNamingService.detect_duplicate_capabilities()
        return jsonify(
            {
                "success": True,
                "duplicates": duplicates,
                "total_groups": len(duplicates),
                "total_duplicates": sum(group["count"] for group in duplicates),
            }
        )
    except Exception as e:
        logger.error(f"Error getting duplicate capabilities: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_management.route("/api/standardize-names", methods=["POST"])
@login_required
@require_roles("admin", "architect")
@audit_log("capability_names_standardize")
def api_standardize_names():
    """
    Standardize capability names
    ---
    tags:
      - Capabilities
    summary: Standardize all capability names
    description: Apply naming conventions to standardize all capability names in the system
    parameters:
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            dry_run:
              type: boolean
              default: true
              description: Preview changes without applying them
    responses:
      200:
        description: Standardization results
        schema:
          type: object
          properties:
            success:
              type: boolean
            result:
              type: object
      500:
        description: Server error
    """
    try:
        data = request.get_json() or {}
        dry_run = data.get("dry_run", True)

        result = CapabilityNamingService.standardize_all_capability_names(dry_run=dry_run)

        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Error standardizing names: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_management.route("/api/merge-duplicates", methods=["POST"])
@login_required
@require_roles("admin", "architect")
@audit_log("capability_duplicates_merge")
def api_merge_duplicates():
    """
    Merge duplicate capabilities
    ---
    tags:
      - Capabilities
    summary: Merge duplicate capabilities
    description: Merge a group of duplicate capabilities into one, keeping the specified capability
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - duplicate_group
            - keep_capability_id
          properties:
            duplicate_group:
              type: array
              items:
                type: integer
              description: List of capability IDs that are duplicates
            keep_capability_id:
              type: integer
              description: ID of the capability to keep (others will be merged into this)
            dry_run:
              type: boolean
              default: true
              description: Preview changes without applying them
    responses:
      200:
        description: Merge results
        schema:
          type: object
          properties:
            success:
              type: boolean
            result:
              type: object
      400:
        description: Missing required parameters
      500:
        description: Server error
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        duplicate_group = data.get("duplicate_group")
        keep_capability_id = data.get("keep_capability_id")
        dry_run = data.get("dry_run", True)

        if not duplicate_group or not keep_capability_id:
            return jsonify({"success": False, "error": "Missing required parameters"}), 400

        result = CapabilityNamingService.merge_duplicate_capabilities(
            duplicate_group, keep_capability_id, dry_run
        )

        return jsonify({"success": True, "result": result})
    except Exception as e:
        logger.error(f"Error merging duplicates: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_management.route("/api/validate-name", methods=["POST"])
@login_required
def api_validate_name():
    """
    Validate capability name
    ---
    tags:
      - Capabilities
    summary: Validate a capability name
    description: Check if a capability name follows naming conventions and standards
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
              description: Capability name to validate
    responses:
      200:
        description: Validation result
        schema:
          type: object
          properties:
            success:
              type: boolean
            validation:
              type: object
              properties:
                is_valid:
                  type: boolean
                issues:
                  type: array
                  items:
                    type: string
                suggestions:
                  type: array
                  items:
                    type: string
      400:
        description: Name is required
      500:
        description: Server error
    """
    try:
        data = request.get_json()
        if not data or "name" not in data:
            return jsonify({"success": False, "error": "Name is required"}), 400

        name = data["name"]
        validation = CapabilityNamingService.validate_capability_name(name)

        return jsonify({"success": True, "validation": validation})
    except Exception as e:
        logger.error(f"Error validating name: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500


@capability_management.route("/api/capability-details/<int:capability_id>")
@login_required
def api_capability_details(capability_id):
    """
    Get capability details
    ---
    tags:
      - Capabilities
    summary: Get capability details by ID
    description: Retrieve detailed information about a specific capability including mapping counts
    parameters:
      - name: capability_id
        in: path
        type: integer
        required: true
        description: Capability ID
    responses:
      200:
        description: Capability details
        schema:
          type: object
          properties:
            success:
              type: boolean
            capability:
              type: object
              properties:
                id:
                  type: integer
                name:
                  type: string
                code:
                  type: string
                description:
                  type: string
                level:
                  type: integer
                category:
                  type: string
                strategic_importance:
                  type: string
                business_criticality:
                  type: string
                is_core_differentiator:
                  type: boolean
                status:
                  type: string
                mapping_count:
                  type: integer
                created_at:
                  type: string
                  format: date-time
                updated_at:
                  type: string
                  format: date-time
      404:
        description: Capability not found
      500:
        description: Server error
    """
    try:
        capability = UnifiedCapability.query.get_or_404(capability_id)

        # Get application mappings count
        from app.models.unified_application_capability_mapping import (
            UnifiedApplicationCapabilityMapping,
        )

        mapping_count = UnifiedApplicationCapabilityMapping.query.filter_by(
            unified_capability_id=capability_id
        ).count()

        return jsonify(
            {
                "success": True,
                "capability": {
                    "id": capability.id,
                    "name": capability.name,
                    "code": capability.code,
                    "description": capability.description,
                    "level": capability.level,
                    "category": capability.category,
                    "strategic_importance": capability.strategic_importance,
                    "business_criticality": capability.business_criticality,
                    "is_core_differentiator": capability.is_core_differentiator,
                    "status": capability.status,
                    "mapping_count": mapping_count,
                    "created_at": capability.created_at.isoformat()
                    if capability.created_at
                    else None,
                    "updated_at": capability.updated_at.isoformat()
                    if capability.updated_at
                    else None,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error getting capability details: {e}")
        return jsonify({"success": False, "error": "An internal error occurred"}), 500
