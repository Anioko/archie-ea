"""Fenced command receipts and immutable transformation operation envelopes."""

from __future__ import annotations

from app import db
from app.models.mixins import TenantMixin


COMMAND_STATUSES = (
    "in_progress",
    "retryable_failure",
    "failed_non_retryable",
    "succeeded",
)


class CommandIdempotencyRecord(TenantMixin, db.Model):
    """Short-transaction claim for one actor/operation/idempotency key."""

    __tablename__ = "command_idempotency_records"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operation = db.Column(db.String(120), nullable=False)
    idempotency_key = db.Column(db.String(255), nullable=False)
    request_digest = db.Column(db.String(64), nullable=False)
    natural_key = db.Column(db.String(512), nullable=False)
    status = db.Column(
        db.String(32), nullable=False, default="in_progress", server_default="in_progress"
    )
    lease_generation = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    claim_token = db.Column(db.String(64), nullable=False)
    claimant_request_id = db.Column(db.String(255), nullable=False)
    lease_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    operation_result_id = db.Column(db.Integer, nullable=True, index=True)
    attempt_count = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    last_error_class = db.Column(db.String(255), nullable=True)
    terminal_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    actor = db.relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "actor_id",
            "operation",
            "idempotency_key",
            name="uq_command_idempotency_identity",
        ),
        db.CheckConstraint("lease_generation > 0", name="ck_command_lease_generation"),
        db.CheckConstraint("attempt_count > 0", name="ck_command_attempt_count"),
        db.CheckConstraint(
            "status IN ('in_progress', 'retryable_failure', "
            "'failed_non_retryable', 'succeeded')",
            name="ck_command_status",
        ),
    )


class OperationResult(TenantMixin, db.Model):
    """Canonical, append-only response for one natural business operation."""

    __tablename__ = "operation_results"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operation = db.Column(db.String(120), nullable=False)
    natural_key = db.Column(db.String(512), nullable=False)
    request_digest = db.Column(db.String(64), nullable=False)
    receipt_id = db.Column(
        db.Integer,
        db.ForeignKey("command_idempotency_records.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    receipt_generation = db.Column(db.Integer, nullable=False)
    object_ids = db.Column(db.JSON, nullable=False)
    response_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    receipt = db.relationship("CommandIdempotencyRecord", foreign_keys=[receipt_id])

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "operation",
            "natural_key",
            name="uq_operation_result_natural_key",
        ),
        db.UniqueConstraint("receipt_id", name="uq_operation_result_receipt"),
        db.CheckConstraint(
            "receipt_generation > 0", name="ck_operation_result_generation"
        ),
    )


class CommandMaterialisation(TenantMixin, db.Model):
    """Immutable recovery envelope for one exact natural-key domain mutation.

    This row is committed atomically with the domain mutation.  It deliberately
    does not depend on ``operation_results``: a damaged receipt/result envelope
    can therefore be rebuilt without guessing from mutable domain state.
    """

    __tablename__ = "command_materialisations"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operation = db.Column(db.String(120), nullable=False)
    natural_key = db.Column(db.String(512), nullable=False)
    request_digest = db.Column(db.String(64), nullable=False)
    receipt_id = db.Column(
        db.Integer,
        db.ForeignKey("command_idempotency_records.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    receipt_generation = db.Column(db.Integer, nullable=False)
    object_ids = db.Column(db.JSON, nullable=False)
    response_json = db.Column(db.JSON, nullable=False)
    outbox_events = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    actor = db.relationship("User", foreign_keys=[actor_id])
    receipt = db.relationship("CommandIdempotencyRecord", foreign_keys=[receipt_id])

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "operation",
            "natural_key",
            name="uq_command_materialisation_natural_key",
        ),
        db.UniqueConstraint("receipt_id", name="uq_command_materialisation_receipt"),
        db.CheckConstraint(
            "length(request_digest) = 64",
            name="ck_command_materialisation_digest",
        ),
        db.CheckConstraint(
            "receipt_generation > 0",
            name="ck_command_materialisation_generation",
        ),
    )


class OperationOutboxEvent(TenantMixin, db.Model):
    """Append-only, at-least-once delivery payload with a deduplication ID."""

    __tablename__ = "transformation_outbox_events"

    id = db.Column(db.Integer, primary_key=True)
    operation_result_id = db.Column(
        db.Integer,
        db.ForeignKey("operation_results.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_id = db.Column(db.String(36), nullable=False, unique=True)
    ordinal = db.Column(db.Integer, nullable=False)
    event_type = db.Column(db.String(160), nullable=False)
    payload_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    delivery_attempts = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    operation_result = db.relationship(
        "OperationResult",
        foreign_keys=[operation_result_id],
        backref=db.backref("outbox_events", lazy="select", passive_deletes=True),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "operation_result_id", "ordinal", name="uq_operation_outbox_ordinal"
        ),
        db.CheckConstraint("ordinal >= 0", name="ck_operation_outbox_ordinal"),
        db.CheckConstraint(
            "delivery_attempts >= 0", name="ck_operation_outbox_delivery_attempts"
        ),
    )


__all__ = [
    "COMMAND_STATUSES",
    "CommandMaterialisation",
    "CommandIdempotencyRecord",
    "OperationOutboxEvent",
    "OperationResult",
]
