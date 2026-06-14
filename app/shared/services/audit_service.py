"""
Shared audit service — convenience wrapper around AuditLog.log().

Provides a simplified interface for common audit operations that modules
can use without importing the full AuditLog model.

Usage::

    from app.shared.services import audit_action

    audit_action(
        action="update",
        entity_type="vendor",
        entity_id=vendor.id,
        user_id=current_user.id,
        description="Updated vendor contact info",
        old_values={"email": "old@co.com"},
        new_values={"email": "new@co.com"},
    )
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def audit_action(
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    entity_name: Optional[str] = None,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    ip_address: Optional[str] = None,
    description: Optional[str] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    status: str = "success",
    error_message: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Optional[Any]:
    """Log an audit action using the canonical AuditLog model.

    This is a convenience wrapper that handles import and error
    recovery so callers don't need to worry about the audit table
    not existing or database errors.

    Returns:
        The AuditLog instance if created, or None on failure.
    """
    try:
        from app.models.audit_log import AuditLog

        return AuditLog.log(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            user_id=user_id,
            user_email=user_email,
            ip_address=ip_address,
            description=description,
            old_values=old_values,
            new_values=new_values,
            status=status,
            error_message=error_message,
            request_id=request_id,
        )
    except Exception as exc:
        logger.warning("Shared audit_action failed (non-fatal): %s", exc)
        return None
