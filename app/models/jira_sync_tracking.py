"""
Jira Sync Tracking Model

Tracks the push state of each application to Jira.
Enables drift detection via SHA-256 hash comparison of pushed field values.

Status lifecycle:
  PENDING → PUSHED → DRIFT_DETECTED → PUSHED (re-push)
  Any state → FAILED (on error)
  Any state → ARCHIVED (app removed from scope)
"""

import hashlib
import json
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from app import db


class PushStatus(str, Enum):
    PENDING = "pending"
    PUSHED = "pushed"
    DRIFT_DETECTED = "drift_detected"
    FAILED = "failed"
    ARCHIVED = "archived"


class JiraSyncTracking(db.Model):
    """Tracks Jira push state per application for bidirectional sync."""

    __tablename__ = "jira_sync_tracking"
    __table_args__ = (
        Index("ix_jira_sync_app_id", "application_id"),
        Index("ix_jira_sync_status", "push_status"),
    )

    id = Column(Integer, primary_key=True)
    application_id = Column(
        Integer,
        db.ForeignKey("application_components.id", ondelete="CASCADE"),
        nullable=False,
    )
    jira_issue_key = Column(String(20), unique=True, index=True, nullable=True)
    jira_project_key = Column(String(10), nullable=False)
    jira_component_name = Column(String(100), nullable=True)

    last_pushed_at = Column(DateTime, nullable=True)
    last_pushed_hash = Column(String(64), nullable=True)
    push_status = Column(String(20), default=PushStatus.PENDING.value, nullable=False)

    error_message = Column(Text, nullable=True)
    field_snapshot = Column(SQLiteJSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    application = db.relationship(
        "ApplicationComponent",
        backref=db.backref("jira_sync", uselist=False, lazy="select"),
    )

    @staticmethod
    def compute_hash(field_dict):
        """Compute deterministic SHA-256 hash of field values for drift detection.

        Args:
            field_dict: Dictionary of field name → value pairs.

        Returns:
            64-char hex digest string.
        """
        canonical = json.dumps(field_dict, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def is_stale(self, current_hash):
        """Check if the tracked state differs from the current application state.

        Args:
            current_hash: SHA-256 hash of current field values.

        Returns:
            True if the application has changed since last push.
        """
        return self.last_pushed_hash != current_hash

    def as_dict(self):
        return {
            "id": self.id,
            "application_id": self.application_id,
            "jira_issue_key": self.jira_issue_key,
            "jira_project_key": self.jira_project_key,
            "jira_component_name": self.jira_component_name,
            "last_pushed_at": self.last_pushed_at.isoformat() if self.last_pushed_at else None,
            "last_pushed_hash": self.last_pushed_hash,
            "push_status": self.push_status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<JiraSyncTracking app={self.application_id} key={self.jira_issue_key} status={self.push_status}>"
