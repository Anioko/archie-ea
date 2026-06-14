"""Spec Webhook model — webhook subscriptions for spec change notifications.  # migration-exempt

Stores webhook configurations per solution for notifying external systems
when specs change or drift is detected.

Table created via db.create_all() — no Alembic migration needed (migration freeze).
"""

from datetime import datetime

from app import db


class SpecWebhook(db.Model):
    """Webhook subscription for spec change and drift notifications."""

    __tablename__ = "spec_webhooks"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    solution_id = db.Column(
        db.Integer, db.ForeignKey("solutions.id"), nullable=False, index=True
    )

    # Webhook config
    url = db.Column(db.String(500), nullable=False)
    event_types = db.Column(db.JSON, default=["spec_changed"])  # spec_changed, drift_detected, compliance_failed
    auth_header_env = db.Column(db.String(100))  # env var name for auth token

    # Settings
    enabled = db.Column(db.Boolean, default=True)
    retry_count = db.Column(db.Integer, default=3)

    # Status
    last_triggered_at = db.Column(db.DateTime)
    last_status = db.Column(db.String(20))  # success, failed, pending
    failure_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    solution = db.relationship("Solution", foreign_keys=[solution_id], lazy="select")

    def to_dict(self):
        return {
            "id": self.id,
            "solution_id": self.solution_id,
            "url": self.url,
            "event_types": self.event_types,
            "auth_header_env": self.auth_header_env,
            "enabled": self.enabled,
            "retry_count": self.retry_count,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "last_status": self.last_status,
            "failure_count": self.failure_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
