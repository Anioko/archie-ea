"""Issue / Dependency — the two RAID categories nothing else already covers.

Risk (app/models/risk.py) is the R. Assumption (app/models/demand.py) is
already the A — a richer model (confidence, exposure, validate-by date,
conversion-to-risk) that existed before this file did. This model originally
also carried an ASSUMPTION kind, added without checking for that existing
store first — the exact ADR-0008 mistake this docstring now warns against.
It was removed once no real data depended on it (2 Sep 2026); create/link
assumptions against demand.Assumption instead. SolutionIssue
(app/models/solution_governance.py) is a close cousin of the Issue kind here
but is scoped to one Solution's implementation — this model's Issue is
programme-level, not tied to a single solution, which is why it survives as
a distinct concept rather than a duplicate.

One model with a `kind` discriminator rather than two near-identical tables —
Issue/Dependency share every field (title, description, owner, status,
target date) and only differ in which bucket they're filed under."""
import enum
from datetime import datetime

from app import db
from app.models.mixins import TenantMixin


class RaidKind(enum.Enum):
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
    # A Dependency's target_date is "needed by"; an Issue's is "resolve by" —
    # nullable throughout.
    target_date = db.Column(db.Date, nullable=True)
    # Real linkage to the programme this item belongs to (2 Sep 2026 —
    # replaces the original free-text programme_name, which could not be
    # queried as "every RAID item for programme X", only string-matched).
    # StrategicInitiative, not EnterpriseInitiative: it's the aggregate root
    # with real programme governance (workstreams, role assignments, outcome
    # commitments) and the one WorkPackage/Benefit/Solution already point at.
    strategic_initiative_id = db.Column(
        db.Integer, db.ForeignKey("strategic_initiatives.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # Kept for the handful of pre-migration rows and for a quick label when no
    # StrategicInitiative record exists yet — no longer the primary path.
    programme_name = db.Column(db.String(255), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    strategic_initiative = db.relationship(
        "StrategicInitiative", foreign_keys=[strategic_initiative_id], back_populates="raid_items"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "kind": self.kind.value if self.kind else None,
            "title": self.title,
            "description": self.description,
            "owner": self.owner,
            "status": self.status.value if self.status else None,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "strategic_initiative_id": self.strategic_initiative_id,
            "programme_name": (
                self.strategic_initiative.name if self.strategic_initiative else self.programme_name
            ),
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
