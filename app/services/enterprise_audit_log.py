"""
Enterprise Audit Log Service

Logs all capability and compliance modifications for compliance tracking.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EnterpriseAuditLog:
    """Service for logging enterprise operations."""

    @staticmethod
    def _create_audit_entry(user_id, action, entity_type, entity_id, details):
        """Create an audit log entry.

        Args:
            user_id: ID of user performing action
            action: Action type (e.g., 'created', 'updated', 'deleted')
            entity_type: Entity type (e.g., 'capability', 'policy', 'violation')
            entity_id: ID of the entity
            details: Dictionary with additional context
        """
        from flask import request
        from flask_login import current_user

        try:
            ip_address = request.remote_addr or "unknown"
        except RuntimeError:
            ip_address = "unknown"

        username = current_user.username if current_user and hasattr(current_user, "username") else "unknown"

        entry = {
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details,
        }

        # Log to application logger
        logger.info(f"[AUDIT] {json.dumps(entry)}")

        return entry

    @staticmethod
    def log_capability_created(user_id, capability_name, details):
        """Log capability creation.

        Args:
            user_id: ID of user
            capability_name: Name of created capability
            details: Dictionary with capability details
        """
        return EnterpriseAuditLog._create_audit_entry(
            user_id,
            "capability_created",
            "capability",
            0,  # ID not yet available
            {"name": capability_name, **details},
        )

    @staticmethod
    def log_capability_updated(user_id, capability_id, changes):
        """Log capability update.

        Args:
            user_id: ID of user
            capability_id: ID of capability
            changes: Dictionary of {field: {from: old, to: new}}
        """
        return EnterpriseAuditLog._create_audit_entry(
            user_id,
            "capability_updated",
            "capability",
            capability_id,
            {"changes": changes},
        )

    @staticmethod
    def log_capability_deleted(user_id, capability_id, capability_name):
        """Log capability deletion.

        Args:
            user_id: ID of user
            capability_id: ID of deleted capability
            capability_name: Name of deleted capability
        """
        return EnterpriseAuditLog._create_audit_entry(
            user_id,
            "capability_deleted",
            "capability",
            capability_id,
            {"name": capability_name},
        )

    @staticmethod
    def log_compliance_change(user_id, action, entity_id, details):
        """Log compliance-related change.

        Args:
            user_id: ID of user
            action: Action type (e.g., 'policy_created', 'violation_updated')
            entity_id: ID of entity
            details: Dictionary with change details
        """
        # Determine entity type from action
        if "policy" in action:
            entity_type = "policy"
        elif "violation" in action:
            entity_type = "violation"
        else:
            entity_type = "compliance"

        return EnterpriseAuditLog._create_audit_entry(
            user_id,
            action,
            entity_type,
            entity_id,
            details,
        )

    @staticmethod
    def log_violation_logged(user_id, violation_id, severity):
        """Log violation creation.

        Args:
            user_id: ID of user
            violation_id: ID of violation
            severity: Severity level
        """
        return EnterpriseAuditLog._create_audit_entry(
            user_id,
            "violation_logged",
            "violation",
            violation_id,
            {"severity": severity},
        )
