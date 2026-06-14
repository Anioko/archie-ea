"""Solution Domain Spec — per-solution ACM domain state (tier, status, confirmation)."""
# migration-exempt — new table created via db.create_all() (migration freeze)

from app import db
from app.models.mixins import TenantMixin


class SolutionDomainSpec(TenantMixin, db.Model):
    __tablename__ = "solution_domain_specs"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    solution_id = db.Column(db.Integer, db.ForeignKey("solutions.id"), nullable=False, index=True)
    domain_code = db.Column(db.String(5), nullable=False)
    relevance_tier = db.Column(db.String(16), default="standard")
    status = db.Column(db.String(16), default="pending")
    status_justification = db.Column(db.Text, nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return "<SolutionDomainSpec sol=%d domain=%s status=%s>" % (
            self.solution_id, self.domain_code, self.status,
        )

    def to_dict(self):
        return {
            "id": self.id,
            "solution_id": self.solution_id,
            "domain_code": self.domain_code,
            "relevance_tier": self.relevance_tier,
            "status": self.status,
            "status_justification": self.status_justification,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
        }
