"""Assumption / Issue / Dependency — the three RAID categories Risk doesn't
cover. Risk (app/models/risk.py) already exists and works; this is not a
fourth near-duplicate of it but the missing complement, so a programme's full
RAID log has somewhere to live. One model with a `kind` discriminator rather
than three near-identical tables — Assumption/Issue/Dependency share every
field (title, description, owner, status, target date) and only differ in
which bucket they're filed under; three tables would be three authorities
answering "what needs tracking on this programme" (ADR-0008)."""
import enum
from datetime import datetime

from app import db
from app.models.mixins import TenantMixin


class RaidKind(enum.Enum):
    ASSUMPTION = "assumption"
    ISSUE = "issue"
    DEPENDENCY = "dependency"


class RaidStatus(enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    CLOSED = "closed"


class RaidItem(TenantMixin, db.Model):
    __tablename__ = "raid_items"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.Enum(RaidKind), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner = db.Column(db.String(128), nullable=True)
    status = db.Column(db.Enum(RaidStatus), default=RaidStatus.OPEN, nullable=False)
    # A Dependency's target_date is "needed by"; an Issue's is "resolve by";
    # an Assumption doesn't usually need one — nullable throughout.
    target_date = db.Column(db.Date, nullable=True)
    # Free-text link to the programme this item belongs to, matching how Risk
    # and Work Package are associated with a programme today (prose, not an FK
    # — the transformation-gap register's P4 "programme isn't the spine" is a
    # separate, larger fix; this does not attempt to solve that here).
    programme_name = db.Column(db.String(255), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind.value if self.kind else None,
            "title": self.title,
            "description": self.description,
            "owner": self.owner,
            "status": self.status.value if self.status else None,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "programme_name": self.programme_name,
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
