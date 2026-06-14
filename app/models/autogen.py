"""Auto-generation support models

Tracks generation events (success/failure) and user overrides for auto-generation
rules per framework/domain.
"""

from datetime import datetime

from sqlalchemy.orm import relationship

from .. import db


class GenerationEvent(db.Model):
    __tablename__ = "generation_event"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)  # create, update, error, validate
    source = db.Column(db.String(100))  # service or model that triggered the event
    target_type = db.Column(db.String(100))  # e.g., BusinessCapability, ApplicationComponent
    target_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(50))  # started, success, failure
    message = db.Column(db.Text)
    metadata_blob = db.Column(db.Text)  # JSON blob for extra context
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "source": self.source,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "status": self.status,
            "message": self.message,
            "metadata": self.metadata_blob,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    # Note: relationship() connections to ArchiMate elements can be added as needed


class AutoGenOverride(db.Model):
    __tablename__ = "autogen_override"

    id = db.Column(db.Integer, primary_key=True)
    framework = db.Column(db.String(100), nullable=True)  # COBIT, ITIL, APQC, custom
    domain = db.Column(db.String(100), nullable=True)  # e.g., finance, hr, it
    target_type = db.Column(db.String(100), nullable=True)  # BusinessCapability, BusinessProcess
    enabled = db.Column(db.Boolean, default=True)
    rule = db.Column(db.Text)  # JSON/YAML rule describing override behaviour
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "framework": self.framework,
            "domain": self.domain,
            "target_type": self.target_type,
            "enabled": self.enabled,
            "rule": self.rule,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
