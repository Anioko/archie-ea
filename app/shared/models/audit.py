"""
Re-exports the canonical AuditLog model for cross-module use.

Multiple domain-specific audit logs exist (ARBAuditLog, ADMAuditLog, etc.)
but the general-purpose AuditLog at ``app.models.audit_log`` is the shared
audit trail used across all modules.

Usage::

    from app.shared.models.audit import AuditLog

    AuditLog.log(
        action="create",
        entity_type="application",
        entity_id=42,
        user_id=current_user.id,
        description="Created new application",
    )
"""

from app.models.audit_log import AuditLog

__all__ = ["AuditLog"]
