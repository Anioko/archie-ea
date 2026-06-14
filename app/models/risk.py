"""Risk model for TPM-013 risk heat map feature."""
import enum
from datetime import datetime

from app import db
from app.models.mixins import TenantMixin


class RiskStatus(enum.Enum):
    OPEN = "open"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    CLOSED = "closed"


class Risk(TenantMixin, db.Model):
    __tablename__ = "risks"

    id = db.Column(db.Integer, primary_key=True)
    solution_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    likelihood = db.Column(db.Integer, nullable=False)  # 1-5
    impact = db.Column(db.Integer, nullable=False)       # 1-5
    status = db.Column(db.Enum(RiskStatus), default=RiskStatus.OPEN, nullable=False)
    owner = db.Column(db.String(128), nullable=True)
    mitigation_plan = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def risk_score(self):
        return self.likelihood * self.impact

    @property
    def risk_level(self):
        s = self.risk_score
        if s >= 15:
            return "critical"
        if s >= 9:
            return "high"
        if s >= 5:
            return "medium"
        return "low"

    def to_dict(self):
        return {
            "id": self.id,
            "solution_id": self.solution_id,
            "title": self.title,
            "description": self.description,
            "likelihood": self.likelihood,
            "impact": self.impact,
            "status": self.status.value,
            "owner": self.owner,
            "mitigation_plan": self.mitigation_plan,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
