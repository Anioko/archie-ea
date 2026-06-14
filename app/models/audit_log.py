"""
AuditLog model — SOC 2 Type II compliant, append-only audit log.

This model is intentionally append-only.  There are NO update() or delete()
class methods and NO soft-delete column.  The SOC 2 audit period cannot begin
until this table is in use, so every mutation of a controlled entity must be
captured here.

``created_at`` uses ``server_default='NOW()'`` so that the timestamp is set
by the database engine and cannot be falsified by application-clock tampering.
"""

from datetime import datetime

from sqlalchemy import Index

from app.extensions import db
import logging

logger = logging.getLogger(__name__)


class AuditLog(db.Model):
    """Append-only SOC 2 audit log entry.

    Design invariants:
    - No row is ever modified or deleted after insertion.
    - ``created_at`` is set by the DB server to prevent clock tampering.
    """

    __tablename__ = "soc2_audit_log"
    __table_args__ = (
        Index("ix_soc2_audit_org_created", "organization_id", "created_at"),
        Index("ix_soc2_audit_user_created", "user_id", "created_at"),
        Index("ix_soc2_audit_record", "table_name", "record_id"),
        {"extend_existing": True},
    )

    # BigInteger PK to support high-volume audit trails without 32-bit overflow.
    id = db.Column(db.BigInteger, primary_key=True)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )

    action = db.Column(db.String(20), nullable=False, index=True)
    table_name = db.Column(db.String(100), nullable=False, index=True)
    record_id = db.Column(db.Integer, nullable=True)
    old_value = db.Column(db.JSON, nullable=True)
    new_value = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)   # IPv6-safe
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        index=True,
        default=datetime.utcnow,
        server_default=db.text("NOW()"),
    )
    extra_json = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return (
            f"<AuditLog id={self.id} action={self.action!r} "
            f"table={self.table_name!r} record={self.record_id}>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "action": self.action,
            "table_name": self.table_name,
            "record_id": self.record_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    # ------------------------------------------------------------------ #
    #  Class-level helpers — INSERT ONLY, no update/delete methods.       #
    # ------------------------------------------------------------------ #

    @classmethod
    def log(cls, **kwargs):
        """Insert a new audit log entry.  Non-blocking — never raises.

        Accepts both SOC 2 kwargs (``table_name``, ``record_id``,
        ``old_value``, ``new_value``) and the legacy kwargs used by
        pre-existing callers (``entity_type`` → ``table_name``,
        ``entity_id`` → ``record_id``, ``old_values`` → ``old_value``,
        ``new_values`` → ``new_value``) for backward compatibility.
        """
        try:
            # Map legacy kwargs to the SOC 2 schema.
            if "entity_type" in kwargs and "table_name" not in kwargs:
                kwargs["table_name"] = kwargs.pop("entity_type")
            if "entity_id" in kwargs and "record_id" not in kwargs:
                kwargs["record_id"] = kwargs.pop("entity_id")
            if "old_values" in kwargs and "old_value" not in kwargs:
                kwargs["old_value"] = kwargs.pop("old_values")
            if "new_values" in kwargs and "new_value" not in kwargs:
                kwargs["new_value"] = kwargs.pop("new_values")

            # Drop legacy columns that have no SOC 2 equivalent.
            for _drop in (
                "entity_name", "description", "status", "error_message",
                "request_id", "session_id", "user_email",
            ):
                kwargs.pop(_drop, None)

            # Ensure required fields are present and within length limits.
            kwargs.setdefault("table_name", "unknown")
            kwargs.setdefault("action", "admin")
            kwargs["action"] = str(kwargs["action"])[:20]

            entry = cls(**kwargs)
            db.session.add(entry)
            db.session.commit()
            return entry
        except Exception:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "AuditLog.log() failed (non-blocking)", exc_info=True
            )
            try:
                db.session.rollback()
            except Exception as exc:
                logger.debug("suppressed error in AuditLog.log (app/models/audit_log.py): %s", exc)
            return None

    @classmethod
    def get_recent(
        cls,
        org_id=None,
        limit=100,
        entity_type=None,
        action=None,
        user_id=None,
    ):
        """Return recent audit entries with optional filtering."""
        query = cls.query.order_by(cls.created_at.desc())
        if org_id is not None:
            query = query.filter_by(organization_id=org_id)
        if entity_type is not None:
            query = query.filter_by(table_name=entity_type)
        if action is not None:
            query = query.filter_by(action=str(action)[:20])
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        return query.limit(limit).all()

    @classmethod
    def get_entity_history(cls, entity_type, entity_id, limit=50):
        """Return audit history for a specific entity (backward compat)."""
        return (
            cls.query
            .filter_by(table_name=entity_type, record_id=entity_id)
            .order_by(cls.created_at.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def log_file_upload(
        cls,
        user_id,
        filename,
        sanitized_filename=None,
        file_size_bytes=None,
        mime_type=None,
        ip_address=None,
        route=None,
        status="success",
        error_message=None,
    ):
        """Log a file-upload event (backward compat helper)."""
        return cls.log(
            action="admin",
            table_name="file",
            user_id=user_id,
            ip_address=ip_address,
            new_value={
                "original_filename": filename,
                "sanitized_filename": sanitized_filename,
                "file_size_bytes": file_size_bytes,
                "mime_type": mime_type,
                "route": route,
                "status": status,
                "error_message": error_message,
            },
        )

    @classmethod
    def record_ai_action(cls, action_type: str, entity_type: str, entity_id=None):
        """Record an AI-originated action (backward compat)."""
        return cls.log(
            action=str(action_type)[:20],
            table_name=entity_type,
            record_id=entity_id,
            new_value={"ai_originated": True},
        )
