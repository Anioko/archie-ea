"""Architecture Decision Records (ADR) model.  # migration-exempt

Structured capture of technology choices, vendor selections, and pattern
decisions with ARB approval workflow.  Part of GOV-02.
Table created via db.create_all() per migration-freeze policy.
"""

from app import db
from datetime import datetime


class ArchitectureDecision(db.Model):
    __tablename__ = "architecture_decisions"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    solution_id = db.Column(db.Integer, db.ForeignKey("solutions.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default="proposed")  # proposed, approved, rejected, superseded
    decision_type = db.Column(db.String(50))  # technology_choice, vendor_selection, pattern_selection, integration_approach
    context = db.Column(db.Text)  # why this decision was needed
    decision = db.Column(db.Text)  # what was decided
    rationale = db.Column(db.Text)  # why this option was chosen
    alternatives = db.Column(db.JSON)  # [{name, pros, cons, rejected_reason}]
    constraints = db.Column(db.JSON)  # [{constraint_name, impact}]
    consequences = db.Column(db.Text)
    related_element_ids = db.Column(db.JSON)  # [element_id, ...]
    decided_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    decided_at = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)
    superseded_by_id = db.Column(db.Integer, db.ForeignKey("architecture_decisions.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "solution_id": self.solution_id,
            "title": self.title,
            "status": self.status,
            "decision_type": self.decision_type,
            "context": self.context,
            "decision": self.decision,
            "rationale": self.rationale,
            "alternatives": self.alternatives or [],
            "constraints": self.constraints or [],
            "consequences": self.consequences,
            "related_element_ids": self.related_element_ids or [],
            "decided_by_id": self.decided_by_id,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "approved_by_id": self.approved_by_id,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason,
            "superseded_by_id": self.superseded_by_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
