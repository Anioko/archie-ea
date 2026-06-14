"""
-> app.modules.import_batch.services.import_service

Import Rollback Service

Handles rolling back import operations.
"""

from flask import current_app
from flask_login import current_user

from app import db
from app.models.import_history import ImportHistory
from app.models.application_portfolio import ApplicationComponent
from app.models.vendor import VendorOrganization
from app.modules.import_batch.v2.services.audit_service_v2 import AuditService


class ImportRollbackError(Exception):
    """Exception for rollback errors"""

    pass


class ImportRollbackService:
    """Service for rolling back import operations."""

    @classmethod
    def can_rollback(cls, import_id):
        """
        Check if an import can be rolled back.

        Returns:
            (can_rollback: bool, message: str)
        """
        import_history = ImportHistory.get_by_id(import_id)

        if not import_history:
            return False, "Import not found"

        return import_history.can_rollback()

    @classmethod
    def rollback(cls, import_id, reason=None):
        """
        Rollback an import operation.

        Args:
            import_id: ID of import to rollback
            reason: Reason for rollback

        Returns:
            dict: Rollback results

        Raises:
            ImportRollbackError: If rollback fails
        """
        import_history = ImportHistory.get_by_id(import_id)

        if not import_history:
            raise ImportRollbackError("Import not found")

        # Check if can rollback
        can_rb, message = import_history.can_rollback()
        if not can_rb:
            raise ImportRollbackError(message)

        entity_ids = import_history.created_entity_ids or {}
        rollback_results = {"applications": 0, "vendors": 0, "errors": []}

        try:
            # Rollback applications
            if "applications" in entity_ids:
                for app_id in entity_ids["applications"]:
                    try:
                        app = ApplicationComponent.query.get(app_id)
                        if app:
                            db.session.delete(app)
                            rollback_results["applications"] += 1
                    except Exception as e:
                        rollback_results["errors"].append(
                            f"Failed to delete application {app_id}: {str(e)}"
                        )

            # Rollback vendors
            if "vendors" in entity_ids:
                for vendor_id in entity_ids["vendors"]:
                    try:
                        vendor = VendorOrganization.query.get(vendor_id)
                        if vendor:
                            db.session.delete(vendor)
                            rollback_results["vendors"] += 1
                    except Exception as e:
                        rollback_results["errors"].append(
                            f"Failed to delete vendor {vendor_id}: {str(e)}"
                        )

            # Commit deletions
            db.session.commit()

            # Mark as rolled back
            import_history.mark_rolled_back(
                user_id=current_user.id
                if current_user and current_user.is_authenticated
                else None,
                reason=reason or "User requested rollback",
            )

            # Audit log
            AuditService.log(
                action="import_rollback",
                entity_type="import",
                entity_id=import_id,
                description=f"Rolled back import {import_id}: {rollback_results}",
                status="success"
                if not rollback_results["errors"]
                else "partial_success",
            )

            current_app.logger.info(
                f"Import {import_id} rolled back: {rollback_results}"
            )

            return {
                "success": True,
                "import_id": import_id,
                "records_rolled_back": rollback_results["applications"]
                + rollback_results["vendors"],
                "details": rollback_results,
            }

        except Exception as e:
            db.session.rollback()

            # Audit log failure
            AuditService.log(
                action="import_rollback",
                entity_type="import",
                entity_id=import_id,
                description=f"Failed to rollback import {import_id}",
                status="failure",
                error_message=str(e),
            )

            current_app.logger.error(f"Failed to rollback import {import_id}: {e}")
            raise ImportRollbackError(f"Rollback failed: {str(e)}")

    @classmethod
    def get_import_history(cls, limit=50, user_id=None):
        """Get import history with rollback status."""
        return ImportHistory.get_recent(limit=limit, user_id=user_id)
