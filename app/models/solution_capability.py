"""Solution-scoped capabilities derived by AI but not yet in the global catalog."""
# migration-exempt

from app import db
from app.datetime_helpers import utcnow
from app.models.mixins import TenantMixin


class SolutionCapability(TenantMixin, db.Model):
    """A capability derived by AI for a specific solution.

    Lives in the solution scope until explicitly promoted to the global
    BusinessCapability catalog by a user.
    """

    __tablename__ = "solution_capability"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    solution_id = db.Column(
        db.Integer,
        db.ForeignKey("solutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), default="required")  # required | optional | future
    source = db.Column(db.String(50), default="ai_derived")
    promoted_to_id = db.Column(
        db.Integer,
        db.ForeignKey("business_capability.id"),
        nullable=True,
    )
    closest_match_id = db.Column(
        db.Integer,
        db.ForeignKey("business_capability.id"),
        nullable=True,
    )
    match_type = db.Column(db.String(20), default="novel")  # exact | partial | novel
    match_score = db.Column(db.Float, nullable=True)
    quality_score = db.Column(db.Float, nullable=True)
    quality_warnings = db.Column(db.Text, nullable=True)  # JSON array of warning strings
    created_at = db.Column(db.DateTime, default=utcnow)

    solution = db.relationship(
        "Solution", backref=db.backref("solution_capabilities", lazy="dynamic")
    )
    promoted_to = db.relationship(
        "BusinessCapability", foreign_keys=[promoted_to_id]
    )
    closest_match = db.relationship(
        "BusinessCapability", foreign_keys=[closest_match_id]
    )

    def to_dict(self):
        return {
            "id": self.id,
            "solution_id": self.solution_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "source": self.source,
            "match_type": self.match_type,
            "match_score": self.match_score,
            "quality_score": self.quality_score,
            "quality_warnings": self.quality_warnings,
            "promoted_to_id": self.promoted_to_id,
            "closest_match_id": self.closest_match_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "solution_scoped": True,
        }
