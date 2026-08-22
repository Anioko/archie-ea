"""Transformation candidate decisions and their immutable discovery citations."""

from __future__ import annotations

from app import db
from app.models.mixins import TenantMixin


class TransformationCandidate(TenantMixin, db.Model):
    """An accepted workstream subject; the canonical subject is never copied."""

    __tablename__ = "transformation_candidates"

    id = db.Column(db.Integer, primary_key=True)
    workstream_id = db.Column(
        db.Integer,
        db.ForeignKey("programme_workstreams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subject_type = db.Column(db.String(40), nullable=False)
    subject_id = db.Column(db.Integer, nullable=False, index=True)
    inclusion_status = db.Column(db.String(30), nullable=False, default="accepted")
    inclusion_reason = db.Column(db.Text, nullable=False)
    accepted_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=False)
    revision = db.Column(
        db.Integer, nullable=False, default=1, server_default="1"
    )

    workstream = db.relationship("ProgrammeWorkstream", foreign_keys=[workstream_id])
    accepted_by = db.relationship("User", foreign_keys=[accepted_by_id])

    __mapper_args__ = {"version_id_col": revision}
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "workstream_id",
            "subject_type",
            "subject_id",
            name="uq_transformation_candidate_subject",
        ),
        db.CheckConstraint(
            "inclusion_status IN ('accepted', 'excluded')",
            name="ck_transformation_candidate_inclusion_status",
        ),
        db.CheckConstraint(
            "revision > 0", name="ck_transformation_candidate_revision"
        ),
    )


class CandidateSignal(TenantMixin, db.Model):
    """Append-only citation of one rule observation accepted with a candidate."""

    __tablename__ = "candidate_signals"

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("transformation_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_code = db.Column(db.String(80), nullable=False)
    rule_version = db.Column(db.String(160), nullable=False)
    payload_json = db.Column(db.JSON, nullable=False)
    source_record_ids = db.Column(db.JSON, nullable=False)
    evaluated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    content_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    candidate = db.relationship(
        "TransformationCandidate",
        foreign_keys=[candidate_id],
        backref=db.backref("signals", lazy="select", passive_deletes=True),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "candidate_id",
            "rule_code",
            name="uq_candidate_signal_rule",
        ),
        db.UniqueConstraint(
            "organization_id",
            "candidate_id",
            "content_hash",
            name="uq_candidate_signal_digest",
        ),
        db.CheckConstraint(
            "length(content_hash) = 64", name="ck_candidate_signal_hash_length"
        ),
    )


class EvidenceRequest(TenantMixin, db.Model):
    """Required claim request created when candidate ownership is unresolved.

    Task 6 extends this request into the complete versioned evidence workflow.
    The fields introduced here are the stable identity and gate-facing state
    required at candidate acceptance.
    """

    __tablename__ = "evidence_requests"

    id = db.Column(db.Integer, primary_key=True)
    workstream_id = db.Column(
        db.Integer,
        db.ForeignKey("programme_workstreams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("transformation_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_type = db.Column(db.String(40), nullable=False)
    subject_id = db.Column(db.Integer, nullable=False, index=True)
    claim_key = db.Column(db.String(100), nullable=False)
    assigned_to_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    required = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    status = db.Column(db.String(30), nullable=False, default="open", server_default="open")
    accepted_evidence_id = db.Column(db.Integer)
    acknowledgement_id = db.Column(db.Integer)
    waiver_id = db.Column(db.Integer)
    due_at = db.Column(db.DateTime(timezone=True))
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    revision = db.Column(db.Integer, nullable=False, default=1, server_default="1")

    candidate = db.relationship("TransformationCandidate", foreign_keys=[candidate_id])
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    __mapper_args__ = {"version_id_col": revision}
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "candidate_id",
            "claim_key",
            name="uq_evidence_request_candidate_claim",
        ),
        db.CheckConstraint(
            "status IN ('open', 'submitted', 'accepted', 'declined', 'expired', 'cancelled')",
            name="ck_evidence_request_status",
        ),
        db.CheckConstraint("revision > 0", name="ck_evidence_request_revision"),
    )


__all__ = ["CandidateSignal", "EvidenceRequest", "TransformationCandidate"]
