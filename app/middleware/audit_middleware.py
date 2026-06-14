"""
audit_middleware — SQLAlchemy event listeners for SOC 2 audit logging.

Registers ``after_insert``, ``after_update``, and ``after_delete`` mapper
events on the key controlled models so that every DB mutation is captured
in ``soc2_audit_log`` without requiring callers to remember to call the
audit service explicitly.

Controlled models: Solution, ApplicationComponent, ArchitectureReviewBoard,
User.

Registration is attempted lazily so that import failures on any individual
model class never prevent the application from starting.

Call ``install_audit_logging(app)`` once in ``app/__init__.py``.
"""

import importlib
import logging

from sqlalchemy import event, inspect

logger = logging.getLogger(__name__)

# (module_path, class_name, logical_table_name)
_CONTROLLED_MODELS = [
    ("app.models.solution_models", "Solution", "solution"),
    ("app.models.application", "ApplicationComponent", "application_component"),
    (
        "app.models.architecture_review_board",
        "ArchitectureReviewBoard",
        "architecture_review_board",
    ),
    ("app.models.user", "User", "user"),
]

_EXCLUDED_COLUMNS = frozenset(
    ["password_hash", "token", "secret", "api_key", "fernet_key"]
)


def _get_request_context():
    """Return (user_id, org_id, ip, ua) from the current Flask request.

    Returns four ``None`` values when called outside a request context.
    """
    try:
        from flask import g, has_request_context, request
        from flask_login import current_user

        if not has_request_context():
            return None, None, None, None

        user_id = current_user.id if current_user.is_authenticated else None
        org_id = getattr(g, "current_org_id", None)

        forwarded = request.headers.get("X-Forwarded-For")
        ip = (forwarded.split(",")[0].strip() if forwarded else request.remote_addr or "")[:45]

        ua_raw = request.headers.get("User-Agent", "")
        ua = ua_raw[:500] if ua_raw else None

        return user_id, org_id, ip, ua
    except Exception:
        return None, None, None, None


def _make_after_insert(table_label: str):
    def _after_insert(mapper, connection, target):
        try:
            from app.services.audit_log_service import AuditLogService

            user_id, org_id, ip, ua = _get_request_context()
            record_id = getattr(target, "id", None)
            new_val = {
                col: getattr(target, col)
                for col in inspect(target).attrs.keys()
                if col not in _EXCLUDED_COLUMNS
            }
            AuditLogService.log(
                action="create",
                resource_type=table_label,
                resource_id=record_id,
                extra_json=new_val,
                user_id=user_id,
                org_id=org_id,
                ip_address=ip,
                user_agent=ua,
            )
        except Exception:
            logger.debug("audit after_insert failed for %s", table_label, exc_info=True)

    return _after_insert


def _make_after_update(table_label: str):
    def _after_update(mapper, connection, target):
        try:
            from app.services.audit_log_service import AuditLogService

            user_id, org_id, ip, ua = _get_request_context()
            record_id = getattr(target, "id", None)

            old_val = {}
            new_val = {}
            for attr in inspect(target).attrs:
                hist = attr.history
                if hist.has_changes():
                    key = attr.key
                    if key in _EXCLUDED_COLUMNS:
                        continue
                    old_val[key] = hist.deleted[0] if hist.deleted else None
                    new_val[key] = hist.added[0] if hist.added else None

            if not old_val and not new_val:
                return  # nothing auditable changed

            AuditLogService.log(
                action="update",
                resource_type=table_label,
                resource_id=record_id,
                extra_json={"old": old_val, "new": new_val},
                user_id=user_id,
                org_id=org_id,
                ip_address=ip,
                user_agent=ua,
            )
        except Exception:
            logger.debug("audit after_update failed for %s", table_label, exc_info=True)

    return _after_update


def _make_after_delete(table_label: str):
    def _after_delete(mapper, connection, target):
        try:
            from app.services.audit_log_service import AuditLogService

            user_id, org_id, ip, ua = _get_request_context()
            record_id = getattr(target, "id", None)
            old_val = {
                col: getattr(target, col)
                for col in inspect(target).attrs.keys()
                if col not in _EXCLUDED_COLUMNS
            }
            AuditLogService.log(
                action="delete",
                resource_type=table_label,
                resource_id=record_id,
                extra_json=old_val,
                user_id=user_id,
                org_id=org_id,
                ip_address=ip,
                user_agent=ua,
            )
        except Exception:
            logger.debug("audit after_delete failed for %s", table_label, exc_info=True)

    return _after_delete


def install_audit_logging(app):
    """Register SQLAlchemy mapper events for SOC 2 audit logging.

    Call once from ``app/__init__.py`` inside ``create_app()``.
    """
    registered = 0
    for module_path, class_name, table_label in _CONTROLLED_MODELS:
        try:
            module = importlib.import_module(module_path)
            model_cls = getattr(module, class_name)

            event.listen(model_cls, "after_insert", _make_after_insert(table_label))
            event.listen(model_cls, "after_update", _make_after_update(table_label))
            event.listen(model_cls, "after_delete", _make_after_delete(table_label))

            registered += 1
            logger.debug("audit_middleware: registered events for %s.%s", module_path, class_name)
        except (ImportError, AttributeError) as exc:
            logger.debug(
                "audit_middleware: skipped %s.%s — %s", module_path, class_name, exc
            )

    logger.info("audit_middleware: registered events on %d controlled models", registered)
