"""Technology Radar (ARCH-124).

The register's ask was "no technology standards catalogue or tech radar".
The Technology ArchiMate layer, Vendor records and Application lifecycle
status already exist — a tech radar is a classification layer over what is
already modelled, not a new inventory. This model holds that classification:
one row per (organization, technology-layer ArchiMateElement), carrying an
adopt/trial/assess/hold ring set by a human architect.

Nothing here is inferred or defaulted to a ring — an unclassified technology
element simply has no TechRadarEntry row, and the UI must render that as
"not yet classified", never as a default ring.
"""

from datetime import datetime

from .. import db
from .mixins import TenantMixin

RADAR_RINGS = ("adopt", "trial", "assess", "hold")
RADAR_RING_LABELS = {
    "adopt": "Adopt",
    "trial": "Trial",
    "assess": "Assess",
    "hold": "Hold",
}


class TechRadarEntry(TenantMixin, db.Model):
    """An architect's adopt/trial/assess/hold classification of one
    Technology-layer ArchiMateElement, already backed by a real Node,
    Device, SystemSoftware or TechnologyService record (see
    app/models/technology_layer.py's before_insert listeners)."""

    __tablename__ = "tech_radar_entries"
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "archimate_element_id", name="uq_tech_radar_entry_element"
        ),
        {"extend_existing": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    archimate_element_id = db.Column(
        db.Integer, db.ForeignKey("archimate_elements.id"), nullable=False, index=True
    )
    ring = db.Column(db.String(10), nullable=False)  # one of RADAR_RINGS
    rationale = db.Column(db.Text, nullable=True)
    set_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True
    )

    element = db.relationship("ArchiMateElement", foreign_keys=[archimate_element_id])
    set_by = db.relationship("User", foreign_keys=[set_by_user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "archimate_element_id": self.archimate_element_id,
            "element_name": self.element.name if self.element else None,
            "element_type": self.element.type if self.element else None,
            "ring": self.ring,
            "ring_label": RADAR_RING_LABELS.get(self.ring, self.ring),
            "rationale": self.rationale,
            "set_by_user_id": self.set_by_user_id,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
