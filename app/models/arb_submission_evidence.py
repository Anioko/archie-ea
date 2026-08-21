"""Immutable evidence captured when a solution enters ARB review."""

from datetime import datetime

from sqlalchemy import event

from app import db
from app.models.mixins import TenantMixin


class ARBSubmissionEvidenceSnapshot(TenantMixin, db.Model):
    """Append-only copy of the evidence used for an ARB submission decision."""

    __tablename__ = "arb_submission_evidence_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), nullable=True, index=True
    )
    review_item_id = db.Column(
        db.Integer, db.ForeignKey("arb_review_items.id"), nullable=True, index=True
    )
    solution_id = db.Column(db.Integer, db.ForeignKey("solutions.id"), nullable=True, index=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("solution_analysis_sessions.id"), nullable=True, index=True
    )
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    schema_version = db.Column(db.Integer, nullable=True)
    workflow_type = db.Column(db.String(30), nullable=True)
    captured_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    checks = db.Column(db.JSON, nullable=True)
    artifacts = db.Column(db.JSON, nullable=True)
    governance_result = db.Column(db.JSON, nullable=True)
    request_assertions = db.Column(db.JSON, nullable=True)
    content_hash = db.Column(db.String(64), nullable=True, index=True)

    review_item = db.relationship("ARBReviewItem", foreign_keys=[review_item_id])


def _reject_snapshot_mutation(_mapper, _connection, _target):
    raise ValueError("ARB submission evidence snapshots are append-only")


event.listen(ARBSubmissionEvidenceSnapshot, "before_update", _reject_snapshot_mutation)
event.listen(ARBSubmissionEvidenceSnapshot, "before_delete", _reject_snapshot_mutation)
