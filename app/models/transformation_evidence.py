"""Transformation candidates, immutable evidence versions, and claim heads."""

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
    ruleset_version = db.Column(db.String(160), nullable=True)
    ruleset_digest = db.Column(db.String(64), nullable=True)
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


class CandidateOverlapDisposition(TenantMixin, db.Model):
    """Immutable human disposition of a positive capability-overlap signal."""

    __tablename__ = "candidate_overlap_dispositions"

    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("transformation_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_digest = db.Column(db.String(64), nullable=False)
    decision = db.Column(db.String(40), nullable=False)
    overlapping_application_ids = db.Column(db.JSON, nullable=False)
    rationale = db.Column(db.Text, nullable=False)
    target_application_id = db.Column(
        db.Integer,
        db.ForeignKey("application_components.id", ondelete="RESTRICT"),
        nullable=True,
    )
    decided_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    command_receipt_id = db.Column(
        db.Integer,
        db.ForeignKey("command_idempotency_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    command_generation = db.Column(db.Integer, nullable=False)
    decided_at = db.Column(db.DateTime(timezone=True), nullable=False)

    candidate = db.relationship("TransformationCandidate", foreign_keys=[candidate_id])
    decided_by = db.relationship("User", foreign_keys=[decided_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "candidate_id",
            name="uq_candidate_overlap_disposition",
        ),
        db.CheckConstraint(
            "decision IN ('confirmed_duplicate', 'justified_distinct', 'merge_repoint')",
            name="ck_candidate_overlap_disposition_decision",
        ),
        db.CheckConstraint(
            "length(signal_digest) = 64",
            name="ck_candidate_overlap_disposition_digest",
        ),
        db.CheckConstraint(
            "command_generation > 0",
            name="ck_candidate_overlap_disposition_generation",
        ),
        db.CheckConstraint(
            "length(btrim(rationale)) > 0",
            name="ck_candidate_overlap_disposition_rationale",
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


class EvidenceRecord(TenantMixin, db.Model):
    """One immutable, typed version of a claim from one canonical source."""

    __tablename__ = "evidence_records"

    id = db.Column(db.Integer, primary_key=True)
    programme_id = db.Column(
        db.Integer,
        db.ForeignKey("strategic_initiatives.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    workstream_id = db.Column(
        db.Integer,
        db.ForeignKey("programme_workstreams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    candidate_id = db.Column(
        db.Integer,
        db.ForeignKey("transformation_candidates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subject_type = db.Column(db.String(40), nullable=False)
    subject_id = db.Column(db.Integer, nullable=False, index=True)
    claim_key = db.Column(db.String(100), nullable=False)
    claim_contract_version = db.Column(db.String(80), nullable=True)

    value_json = db.Column(db.JSON, nullable=False)
    value_type = db.Column(db.String(30), nullable=False)
    unit = db.Column(db.String(80))
    currency = db.Column(db.String(3))
    classification = db.Column(db.String(40), nullable=False)

    source_identity = db.Column(db.String(1024), nullable=False)
    source_type = db.Column(db.String(80), nullable=False)
    source_record_id = db.Column(db.Integer)
    source_uri = db.Column(db.String(2048))
    source_version = db.Column(db.String(512), nullable=False)
    source_checksum = db.Column(db.String(64), nullable=False)
    source_system = db.Column(db.String(120), nullable=False)

    collected_at = db.Column(db.DateTime(timezone=True), nullable=False)
    observed_at = db.Column(db.DateTime(timezone=True), nullable=False)
    valid_from = db.Column(db.DateTime(timezone=True))
    valid_until = db.Column(db.DateTime(timezone=True))
    freshness_status = db.Column(db.String(30), nullable=False)
    freshness_expires_at = db.Column(db.DateTime(timezone=True))
    freshness_rule_version = db.Column(db.String(160), nullable=False)

    collector_type = db.Column(db.String(30), nullable=False, default="human")
    collector_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    ai_provider = db.Column(db.String(120))
    ai_model = db.Column(db.String(160))
    ai_run_id = db.Column(db.String(255))
    cited_evidence_ids = db.Column(
        db.JSON, nullable=False, default=list, server_default=db.text("'[]'::json")
    )
    confidence = db.Column(db.Numeric(6, 5))
    confidence_method = db.Column(db.String(160))
    supersedes_id = db.Column(
        db.Integer,
        db.ForeignKey("evidence_records.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    candidate = db.relationship("TransformationCandidate", foreign_keys=[candidate_id])
    supersedes = db.relationship(
        "EvidenceRecord", remote_side=[id], foreign_keys=[supersedes_id]
    )
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    __table_args__ = (
        db.CheckConstraint(
            "classification IN ('observed', 'attested', 'derived', 'estimated', "
            "'external_reference', 'unknown', 'conflict')",
            name="ck_evidence_record_classification",
        ),
        db.CheckConstraint(
            "freshness_status IN ('fresh', 'stale', 'unknown', 'not_applicable')",
            name="ck_evidence_record_freshness_status",
        ),
        db.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_evidence_record_confidence",
        ),
        db.CheckConstraint(
            "currency IS NULL OR length(currency) = 3",
            name="ck_evidence_record_currency",
        ),
        db.CheckConstraint(
            "length(source_checksum) = 64",
            name="ck_evidence_record_checksum",
        ),
    )


class EvidenceClaimHead(TenantMixin, db.Model):
    """Mutable pointer to the active immutable record for one source claim."""

    __tablename__ = "evidence_claim_heads"

    id = db.Column(db.Integer, primary_key=True)
    subject_type = db.Column(db.String(40), nullable=False)
    subject_id = db.Column(db.Integer, nullable=False, index=True)
    claim_key = db.Column(db.String(100), nullable=False)
    source_identity = db.Column(db.String(1024), nullable=False)
    current_record_id = db.Column(
        db.Integer,
        db.ForeignKey("evidence_records.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    revision = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    current_record = db.relationship("EvidenceRecord", foreign_keys=[current_record_id])

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "subject_type",
            "subject_id",
            "claim_key",
            "source_identity",
            name="uq_evidence_claim_head_identity",
        ),
        db.CheckConstraint("revision >= 0", name="ck_evidence_claim_head_revision"),
        db.CheckConstraint(
            "(revision = 0 AND current_record_id IS NULL) OR "
            "(revision > 0 AND current_record_id IS NOT NULL)",
            name="ck_evidence_claim_head_pointer",
        ),
    )


class EvidenceHeadEvent(TenantMixin, db.Model):
    """Append-only command/fence audit for exactly one guarded head movement."""

    __tablename__ = "evidence_head_events"

    id = db.Column(db.Integer, primary_key=True)
    head_id = db.Column(
        db.Integer,
        db.ForeignKey("evidence_claim_heads.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    old_record_id = db.Column(
        db.Integer,
        db.ForeignKey("evidence_records.id", ondelete="RESTRICT"),
        nullable=True,
    )
    new_record_id = db.Column(
        db.Integer,
        db.ForeignKey("evidence_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    command_receipt_id = db.Column(
        db.Integer,
        db.ForeignKey("command_idempotency_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    command_generation = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    revision = db.Column(db.Integer, nullable=False)
    created_txid = db.Column(
        db.BigInteger, nullable=False, server_default=db.text("txid_current()")
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    head = db.relationship("EvidenceClaimHead", foreign_keys=[head_id])

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "head_id", "revision", name="uq_evidence_head_event_revision"
        ),
        db.UniqueConstraint("new_record_id", name="uq_evidence_head_event_new_record"),
        db.CheckConstraint("revision > 0", name="ck_evidence_head_event_revision"),
        db.CheckConstraint(
            "command_generation > 0", name="ck_evidence_head_event_generation"
        ),
    )


class EvidenceRequest(TenantMixin, db.Model):
    """Mutable assignment/workflow around immutable submitted evidence."""

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
    claim_contract_version = db.Column(db.String(80), nullable=True)
    assigned_to_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    required = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    status = db.Column(db.String(30), nullable=False, default="open", server_default="open")
    submitted_evidence_id = db.Column(
        db.Integer,
        db.ForeignKey("evidence_records.id", ondelete="RESTRICT"),
        nullable=True,
    )
    accepted_evidence_id = db.Column(
        db.Integer,
        db.ForeignKey("evidence_records.id", ondelete="RESTRICT"),
        nullable=True,
    )
    acknowledgement_id = db.Column(db.Integer)
    waiver_id = db.Column(db.Integer)
    waiver_authority_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    waiver_reason = db.Column(db.Text)
    waiver_expires_at = db.Column(db.DateTime(timezone=True))
    interim_accountable_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decline_reason = db.Column(db.Text)
    due_at = db.Column(db.DateTime(timezone=True))
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    submitted_at = db.Column(db.DateTime(timezone=True))
    accepted_at = db.Column(db.DateTime(timezone=True))
    expired_at = db.Column(db.DateTime(timezone=True))
    waived_at = db.Column(db.DateTime(timezone=True))
    revision = db.Column(db.Integer, nullable=False, default=1, server_default="1")

    candidate = db.relationship("TransformationCandidate", foreign_keys=[candidate_id])
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    submitted_evidence = db.relationship("EvidenceRecord", foreign_keys=[submitted_evidence_id])
    accepted_evidence = db.relationship("EvidenceRecord", foreign_keys=[accepted_evidence_id])

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
        db.CheckConstraint(
            "waiver_id IS NULL OR (waiver_authority_id IS NOT NULL AND "
            "waiver_reason IS NOT NULL AND waiver_expires_at IS NOT NULL AND "
            "interim_accountable_id IS NOT NULL AND waived_at IS NOT NULL)",
            name="ck_evidence_request_waiver_complete",
        ),
    )


__all__ = [
    "CandidateOverlapDisposition",
    "CandidateSignal",
    "EvidenceClaimHead",
    "EvidenceHeadEvent",
    "EvidenceRecord",
    "EvidenceRequest",
    "TransformationCandidate",
]
