"""
Audit Logging Integration for Existing Routes

This module integrates audit logging into existing routes without modifying route files.
Uses Flask before/after request hooks and signals.
"""

import logging

from flask import request, g
from flask.signals import request_started, request_finished

from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class AuditIntegration:
    """
    Integrates audit logging into existing Flask routes.

    Usage:
        audit_integration = AuditIntegration(app)
        audit_integration.enable_for_blueprint('unified_applications')
    """

    def __init__(self, app=None):
        self.app = app
        self.enabled_blueprints = set()

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize with Flask app."""
        self.app = app

        # Register global before/after request handlers
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def enable_for_blueprint(self, blueprint_name):
        """Enable audit logging for a specific blueprint."""
        self.enabled_blueprints.add(blueprint_name)

    def _before_request(self):
        """Store request start time and info."""
        import time

        g.audit_request_start = time.time()
        g.audit_entity_before = None

        # Try to get entity before modification (for updates/deletes)
        if self._should_audit_request():
            g.audit_entity_before = self._get_entity_before_change()

    def _after_request(self, response):
        """Log audit after request completes."""
        try:
            if not self._should_audit_request():
                return response

            import time

            # Determine action type
            action = self._determine_action()
            if not action:
                return response

            # Get entity info
            entity_type = self._get_entity_type()
            entity_id = self._get_entity_id()
            entity_name = self._get_entity_name()

            # Get before/after values
            old_values = getattr(g, "audit_entity_before", None)
            new_values = (
                self._get_entity_after_change()
                if action in ["create", "update"]
                else None
            )

            # Determine status
            status = "success" if response.status_code < 400 else "failure"
            error_message = None
            if status == "failure":
                error_message = f"HTTP {response.status_code}"

            # Log the action
            AuditService.log(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                description=f"{action.capitalize()} {entity_type} via {request.endpoint}",
                old_values=old_values,
                new_values=new_values,
                status=status,
                error_message=error_message,
            )

        except Exception as e:
            # Don't let audit logging break the request
            if self.app:
                self.app.logger.error(f"Audit logging error: {e}")

        return response

    def _should_audit_request(self):
        """Determine if current request should be audited."""
        # Only audit modifying requests
        if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
            return False

        # Check if blueprint is enabled
        if request.blueprint not in self.enabled_blueprints:
            return False

        # Skip certain endpoints
        skip_patterns = [
            "health",
            "metrics",
            "static",
            "debug",
            "login",
            "logout",
        ]

        if request.endpoint:
            for pattern in skip_patterns:
                if pattern in request.endpoint:
                    return False

        return True

    def _determine_action(self):
        """Determine action type from request."""
        method = request.method
        endpoint = request.endpoint or ""

        # Map methods to actions
        if method == "POST":
            return "create"
        elif method in ["PUT", "PATCH"]:
            return "update"
        elif method == "DELETE":
            return "delete"

        return None

    def _get_entity_type(self):
        """Determine entity type from request."""
        endpoint = request.endpoint or ""
        blueprint = request.blueprint or ""

        # Map blueprints/endpoints to entity types
        entity_map = {
            "unified_applications": "application",
            "vendor_management": "vendor",
            "capability_map": "capability",
            "application_mgmt": "application",
        }

        return entity_map.get(blueprint, "unknown")

    def _get_entity_id(self):
        """Extract entity ID from request."""
        # Try to get from URL parameters
        view_args = request.view_args or {}

        for key in ["id", "app_id", "vendor_id", "capability_id", "entity_id"]:
            if key in view_args:
                return view_args[key]

        return None

    def _get_entity_name(self):
        """Extract entity name from request data."""
        # Try to get name from form data or JSON
        name_fields = ["name", "title", "filename"]

        # Check form data
        if request.form:
            for field in name_fields:
                if field in request.form:
                    return request.form[field]

        # Check JSON data
        if request.is_json:
            data = request.get_json() or {}
            for field in name_fields:
                if field in data:
                    return data[field]

        return None

    def _get_entity_before_change(self):
        """Get entity state before modification (for updates/deletes)."""
        entity_type = self._get_entity_type()
        entity_id = self._get_entity_id()

        if not entity_id:
            return None

        try:
            # Query entity from database
            if entity_type == "application":
                from app.models.application_portfolio import ApplicationComponent

                entity = ApplicationComponent.query.get(entity_id)
                if entity:
                    return {
                        "id": entity.id,
                        "name": entity.name,
                        "description": entity.description,
                    }

            elif entity_type == "vendor":
                from app.models.vendor import VendorOrganization

                entity = VendorOrganization.query.get(entity_id)
                if entity:
                    return {
                        "id": entity.id,
                        "name": entity.name,
                    }

        except Exception as e:
            logger.debug("Entity lookup failed for %s/%s: %s", entity_type, entity_id, e)

        return None

    def _get_entity_after_change(self):
        """Get entity state after modification (for creates/updates)."""
        # This is simplified - in practice, you'd re-query the entity
        # or extract from the response
        entity_id = self._get_entity_id()
        entity_name = self._get_entity_name()

        if entity_id or entity_name:
            return {
                "id": entity_id,
                "name": entity_name,
            }

        return None


# Global instance for easy import
audit_integration = AuditIntegration()
