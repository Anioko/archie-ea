"""Fenced command receipts and immutable transformation operation envelopes."""

from __future__ import annotations

from sqlalchemy import event, inspect

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


class DeliveryExportAttempt(TenantMixin, db.Model):
    """Append-only result of one attempt to export canonical delivery work."""

    __tablename__ = "delivery_export_attempts"

    id = db.Column(db.Integer, primary_key=True)
    work_package_id = db.Column(
        db.Integer,
        db.ForeignKey("work_packages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    predecessor_attempt_id = db.Column(
        db.Integer,
        db.ForeignKey("delivery_export_attempts.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    provider_key = db.Column(db.String(120), nullable=False)
    attempt_key = db.Column(db.String(64), nullable=False)
    request_json = db.Column(db.JSON, nullable=False)
    response_digest = db.Column(db.String(64), nullable=True)
    external_key = db.Column(db.String(512), nullable=True)
    status = db.Column(db.String(24), nullable=False)
    error_class = db.Column(db.String(255), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    attempted_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    work_package = db.relationship("WorkPackage", foreign_keys=[work_package_id])
    predecessor_attempt = db.relationship(
        "DeliveryExportAttempt", remote_side=[id], foreign_keys=[predecessor_attempt_id]
    )
    attempted_by = db.relationship("User", foreign_keys=[attempted_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "attempt_key",
            name="uq_delivery_export_attempt_key",
        ),
        db.CheckConstraint(
            "length(btrim(provider_key)) > 0 AND length(attempt_key) = 64",
            name="ck_delivery_export_attempt_identity",
        ),
        db.CheckConstraint(
            "status IN ('in_progress','succeeded','failed')",
            name="ck_delivery_export_attempt_status",
        ),
        db.CheckConstraint(
            "(status = 'in_progress' AND completed_at IS NULL "
            "AND response_digest IS NULL AND external_key IS NULL "
            "AND error_class IS NULL AND error_message IS NULL) OR "
            "(status = 'succeeded' AND completed_at IS NOT NULL "
            "AND length(response_digest) = 64 "
            "AND length(btrim(external_key)) > 0 "
            "AND error_class IS NULL AND error_message IS NULL) OR "
            "(status = 'failed' AND completed_at IS NOT NULL "
            "AND length(btrim(error_message)) > 0 "
            "AND (response_digest IS NULL OR length(response_digest) = 64))",
            name="ck_delivery_export_attempt_completion",
        ),
    )


class OutcomeMeasurement(TenantMixin, db.Model):
    """Immutable observation against the canonical Benefit projection."""

    __tablename__ = "outcome_measurements"

    id = db.Column(db.Integer, primary_key=True)
    benefit_id = db.Column(
        db.Integer,
        db.ForeignKey("benefits.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    value = db.Column(db.Numeric(24, 6), nullable=True)
    unavailable_reason = db.Column(db.Text, nullable=True)
    observed_at = db.Column(db.DateTime(timezone=True), nullable=False)
    source_identity = db.Column(db.String(512), nullable=False)
    source_version = db.Column(db.String(255), nullable=False)
    recorded_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    benefit = db.relationship("Benefit", foreign_keys=[benefit_id])
    recorded_by = db.relationship("User", foreign_keys=[recorded_by_id])

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "benefit_id",
            "source_identity",
            "observed_at",
            "source_version",
            name="uq_outcome_measurement_observation",
        ),
        db.CheckConstraint(
            "length(btrim(source_identity)) > 0 "
            "AND length(btrim(source_version)) > 0",
            name="ck_outcome_measurement_source",
        ),
        db.CheckConstraint(
            "(value IS NOT NULL AND unavailable_reason IS NULL) OR "
            "(value IS NULL AND length(btrim(unavailable_reason)) > 0)",
            name="ck_outcome_measurement_fact",
        ),
    )


def _reject_outcome_measurement_mutation(_mapper, _connection, _target):
    raise ValueError("outcome measurements are append-only")


def _guard_completed_export_attempt(_mapper, _connection, target):
    history = inspect(target).attrs.status.history
    previous = history.deleted[0] if history.deleted else target.status
    if previous in {"succeeded", "failed"}:
        raise ValueError("completed delivery export attempts are immutable")


def _guard_completed_export_delete(_mapper, _connection, target):
    if target.status in {"succeeded", "failed"}:
        raise ValueError("completed delivery export attempts are immutable")


event.listen(OutcomeMeasurement, "before_update", _reject_outcome_measurement_mutation)
event.listen(OutcomeMeasurement, "before_delete", _reject_outcome_measurement_mutation)
event.listen(DeliveryExportAttempt, "before_update", _guard_completed_export_attempt)
event.listen(DeliveryExportAttempt, "before_delete", _guard_completed_export_delete)


def ensure_execution_history_immutability(connection):
    """Install database guards for Task 9 append-only/completed history."""
    connection.execute(
        db.text(
            """
            CREATE OR REPLACE FUNCTION archie_reject_outcome_measurement_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'outcome measurements are append-only';
            END;
            $$;
            CREATE OR REPLACE FUNCTION archie_guard_delivery_export_attempt_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF OLD.status IN ('succeeded', 'failed') THEN
                    RAISE EXCEPTION 'completed delivery export attempts are immutable';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END;
            $$;
            DO $$
            BEGIN
                IF to_regclass('outcome_measurements') IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM pg_trigger
                       WHERE tgname = 'trg_reject_outcome_measurement_mutation'
                         AND tgrelid = to_regclass('outcome_measurements')
                   ) THEN
                    CREATE TRIGGER trg_reject_outcome_measurement_mutation
                    BEFORE UPDATE OR DELETE ON outcome_measurements
                    FOR EACH ROW EXECUTE FUNCTION
                    archie_reject_outcome_measurement_mutation();
                END IF;
                IF to_regclass('delivery_export_attempts') IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM pg_trigger
                       WHERE tgname = 'trg_guard_delivery_export_attempt_mutation'
                         AND tgrelid = to_regclass('delivery_export_attempts')
                   ) THEN
                    CREATE TRIGGER trg_guard_delivery_export_attempt_mutation
                    BEFORE UPDATE OR DELETE ON delivery_export_attempts
                    FOR EACH ROW EXECUTE FUNCTION
                    archie_guard_delivery_export_attempt_mutation();
                END IF;
            END;
            $$;
            """
        )
    )


@event.listens_for(OutcomeMeasurement.__table__, "after_create")
def _install_outcome_measurement_immutability(_target, connection, **_kwargs):
    ensure_execution_history_immutability(connection)


@event.listens_for(DeliveryExportAttempt.__table__, "after_create")
def _install_delivery_export_immutability(_target, connection, **_kwargs):
    ensure_execution_history_immutability(connection)


__all__ = [
    "COMMAND_STATUSES",
    "CommandMaterialisation",
    "CommandIdempotencyRecord",
    "DeliveryExportAttempt",
    "OperationOutboxEvent",
    "OperationResult",
    "OutcomeMeasurement",
    "ensure_execution_history_immutability",
]
