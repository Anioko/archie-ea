"""
Audit Service

Convenience functions for creating audit logs.
"""

from flask import request, g
from flask_login import current_user

from app import db
from app.models.audit_log import AuditLog


class AuditService:
    """Service for creating audit logs."""

    @staticmethod
    def get_client_info():
        """Get client information from request."""
        return {
            "ip_address": request.remote_addr if request else None,
            "user_agent": request.user_agent.string
            if request and request.user_agent
            else None,
        }

    @staticmethod
    def get_user_info():
        """Get current user information."""
        if current_user and current_user.is_authenticated:
            return {"user_id": current_user.id, "user_email": current_user.email}
        return {"user_id": None, "user_email": None}

    @classmethod
    def log(
        cls,
        action,
        entity_type,
        entity_id=None,
        entity_name=None,
        description=None,
        old_values=None,
        new_values=None,
        status="success",
        error_message=None,
    ):
        """
        Create an audit log entry.

        Automatically captures user and request context.
        """
        user_info = cls.get_user_info()
        client_info = cls.get_client_info()

        return AuditLog.log(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            user_id=user_info["user_id"],
            user_email=user_info["user_email"],
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            description=description,
            old_values=old_values,
            new_values=new_values,
            status=status,
            error_message=error_message,
        )

    @classmethod
    def log_create(
        cls, entity_type, entity_id, entity_name, new_values, description=None
    ):
        """Log entity creation."""
        return cls.log(
            action="create",
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            description=description or f"Created {entity_type}: {entity_name}",
            new_values=new_values,
            status="success",
        )

    @classmethod
    def log_update(
        cls,
        entity_type,
        entity_id,
        entity_name,
        old_values,
        new_values,
        description=None,
    ):
        """Log entity update."""
        return cls.log(
            action="update",
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            description=description or f"Updated {entity_type}: {entity_name}",
            old_values=old_values,
            new_values=new_values,
            status="success",
        )

    @classmethod
    def log_delete(
        cls, entity_type, entity_id, entity_name, old_values, description=None
    ):
        """Log entity deletion."""
        return cls.log(
            action="delete",
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            description=description or f"Deleted {entity_type}: {entity_name}",
            old_values=old_values,
            status="success",
        )

    @classmethod
    def log_login(cls, user_id, user_email, status="success", error_message=None):
        """Log user login."""
        return cls.log(
            action="login",
            entity_type="user",
            entity_id=user_id,
            entity_name=user_email,
            description=f"User login: {user_email}",
            status=status,
            error_message=error_message,
        )

    @classmethod
    def log_import(
        cls, import_type, record_count, status="success", error_message=None
    ):
        """Log import operation."""
        return cls.log(
            action="import",
            entity_type="import",
            entity_name=f"{import_type}_import",
            description=f"Import {import_type}: {record_count} records",
            new_values={"record_count": record_count, "import_type": import_type},
            status=status,
            error_message=error_message,
        )

    @classmethod
    def log_bulk_operation(cls, action, entity_type, entity_ids, description=None):
        """Log bulk operation."""
        return cls.log(
            action=f"bulk_{action}",
            entity_type=entity_type,
            description=description
            or f"Bulk {action} on {len(entity_ids)} {entity_type}(s)",
            new_values={"entity_ids": entity_ids, "count": len(entity_ids)},
            status="success",
        )

    @classmethod
    def log_ai_usage(
        cls,
        feature,
        model_used=None,
        token_count=None,
        status="success",
        error_message=None,
    ):
        """Log AI feature usage for audit trail."""
        return cls.log(
            action="ai_usage",
            entity_type="ai_feature",
            entity_name=feature,
            description=f"AI feature used: {feature}"
            + (f" (model: {model_used})" if model_used else ""),
            new_values={
                "feature": feature,
                "model_used": model_used,
                "token_count": token_count,
            },
            status=status,
            error_message=error_message,
        )

    @classmethod
    def log_permission_change(
        cls, target_user_id, target_email, old_role, new_role, description=None
    ):
        """Log permission/role change for security audit trail."""
        return cls.log(
            action="permission_change",
            entity_type="user",
            entity_id=target_user_id,
            entity_name=target_email,
            description=description
            or f"Role changed for {target_email}: {old_role} -> {new_role}",
            old_values={"role": old_role},
            new_values={"role": new_role},
            status="success",
        )
