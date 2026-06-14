"""
Audit Decorator

Decorator to automatically audit route calls.

Usage:
    @audit_action('create', 'application')
    def create_application():
        pass
"""

import functools
from flask import request

from app.services.audit_service import AuditService
import logging

logger = logging.getLogger(__name__)


def audit_action(action, entity_type, get_entity_id=None, get_entity_name=None):
    """
    Decorator to audit route actions.

    Args:
        action: The action being performed ('create', 'update', 'delete', etc.)
        entity_type: Type of entity ('application', 'vendor', etc.)
        get_entity_id: Function to extract entity ID from args/kwargs
        get_entity_name: Function to extract entity name from args/kwargs

    Usage:
        @audit_action('delete', 'application',
                      get_entity_id=lambda *a, **kw: kw.get('id'))
        def delete_application(id):
            pass
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # Extract entity info
            entity_id = get_entity_id(*args, **kwargs) if get_entity_id else None
            entity_name = get_entity_name(*args, **kwargs) if get_entity_name else None

            try:
                # Execute the function
                result = f(*args, **kwargs)

                # Log success
                AuditService.log(
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    status="success",
                )

                return result

            except Exception as e:
                # Log failure
                AuditService.log(
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    status="failure",
                    error_message=str(e),
                )
                raise

        return wrapper

    return decorator


def audit_crud(entity_type):
    """
    Decorator to audit CRUD operations.

    Automatically determines action from route method.

    Usage:
        @audit_crud('application')
        def application_create():
            pass
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # Determine action from request method
            method = request.method if request else "GET"
            action_map = {
                "POST": "create",
                "PUT": "update",
                "PATCH": "update",
                "DELETE": "delete",
            }
            action = action_map.get(method, "read")

            try:
                result = f(*args, **kwargs)

                # Try to extract entity info from result
                entity_id = None
                entity_name = None

                if hasattr(result, "id"):
                    entity_id = result.id
                if hasattr(result, "name"):
                    entity_name = result.name

                AuditService.log(
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    status="success",
                )

                return result

            except Exception as e:
                AuditService.log(
                    action=action,
                    entity_type=entity_type,
                    status="failure",
                    error_message=str(e),
                )
                raise

        return wrapper

    return decorator


def audit_log(action_name: str):
    """Audit logging decorator for route-level CRUD action tracking (ISS-006).

    Logs the action, user, entity info, and request metadata to AuditLog.
    Gracefully degrades if audit model import fails (e.g., during tests).

    Usage:
        @audit_log("application_create")
        def create_application():
            ...
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            result = f(*args, **kwargs)

            # Best-effort audit — never break the request
            try:
                from app.models.audit_log import AuditLog
                from flask import request as _req, g
                from flask_login import current_user as _cu

                user_id = _cu.id if _cu and _cu.is_authenticated else None
                user_email = _cu.email if _cu and _cu.is_authenticated else None

                # Extract entity info from route kwargs or view args
                entity_id = kwargs.get("id") or kwargs.get("item_id") or kwargs.get("review_id")
                entity_type = action_name.rsplit("_", 1)[0] if "_" in action_name else action_name

                AuditLog.log(
                    action=action_name,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    user_id=user_id,
                    user_email=user_email,
                    ip_address=_req.remote_addr if _req else None,
                    description=f"{action_name} via {_req.path}" if _req else action_name,
                    status="success",
                    request_id=getattr(g, "request_id", None) if g else None,
                )
            except Exception as exc:
                logger.debug("suppressed error in audit_log.decorator.wrapper (app/decorators/audit.py): %s", exc)  # Never break the request for audit failures

            return result

        return wrapper

    return decorator
