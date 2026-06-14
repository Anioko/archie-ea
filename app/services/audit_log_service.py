"""
AuditLogService — SOC 2 Type II audit-log write/read interface.

All writes are non-blocking: exceptions are swallowed so that audit
failures never surface to end users or break the calling request.

IP-address resolution honours the X-Forwarded-For header so that
reverse-proxy deployments log the real client address.
"""

import logging

from app.extensions import db
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditLogService:
    """Facade over ``AuditLog`` with request-context awareness."""

    # ------------------------------------------------------------------ #
    #  Write                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def log(
        action: str,
        table_name: str,
        record_id=None,
        old_value=None,
        new_value=None,
        user_id=None,
        org_id=None,
        ip_address=None,
        user_agent=None,
    ):
        """Insert one audit-log row.  Never raises.

        If ``ip_address`` is not provided the method attempts to read it
        from the current Flask request, preferring the ``X-Forwarded-For``
        header over ``request.remote_addr``.
        """
        try:
            if ip_address is None:
                ip_address = AuditLogService._resolve_ip()
            if user_agent is None:
                user_agent = AuditLogService._resolve_ua()

            entry = AuditLog(
                action=str(action)[:20],
                table_name=table_name,
                record_id=record_id,
                old_value=old_value,
                new_value=new_value,
                user_id=user_id,
                organization_id=org_id,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:500] if user_agent else None,
            )
            db.session.add(entry)
            db.session.commit()
            return entry
        except Exception:
            logger.warning("AuditLogService.log() failed (non-blocking)", exc_info=True)
            try:
                db.session.rollback()
            except Exception as exc:
                logger.debug("suppressed error in AuditLogService.log (app/services/audit_log_service.py): %s", exc)
            return None

    # ------------------------------------------------------------------ #
    #  Read                                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_recent(org_id, limit=100):
        """Return the *limit* most-recent entries for *org_id*."""
        return (
            AuditLog.query
            .filter_by(organization_id=org_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_for_record(table_name: str, record_id: int):
        """Return the full audit history for a specific record."""
        return (
            AuditLog.query
            .filter_by(table_name=table_name, record_id=record_id)
            .order_by(AuditLog.created_at.asc())
            .all()
        )

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_ip():
        try:
            from flask import has_request_context, request
            if not has_request_context():
                return None
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()[:45]
            return (request.remote_addr or "")[:45]
        except Exception:
            return None

    @staticmethod
    def _resolve_ua():
        try:
            from flask import has_request_context, request
            if not has_request_context():
                return None
            ua = request.headers.get("User-Agent", "")
            return ua[:500] if ua else None
        except Exception:
            return None
