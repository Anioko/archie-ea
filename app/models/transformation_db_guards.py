"""PostgreSQL append-only and fenced-transition guards for command records."""

from __future__ import annotations

from sqlalchemy import event

from app.models.transformation_execution import (
    CommandIdempotencyRecord,
    OperationOutboxEvent,
    OperationResult,
)


_IMMUTABILITY_FUNCTION_SQL = r"""
CREATE OR REPLACE FUNCTION public.archie_reject_transformation_mutation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF TG_TABLE_NAME = 'transformation_outbox_events' AND TG_OP = 'UPDATE' THEN
        IF NEW.id = OLD.id
           AND NEW.organization_id = OLD.organization_id
           AND NEW.operation_result_id = OLD.operation_result_id
           AND NEW.event_id = OLD.event_id
           AND NEW.ordinal = OLD.ordinal
           AND NEW.event_type = OLD.event_type
           AND NEW.payload_json::jsonb = OLD.payload_json::jsonb
           AND NEW.created_at = OLD.created_at
           AND NEW.delivery_attempts >= OLD.delivery_attempts
           AND (
               NEW.published_at IS NOT DISTINCT FROM OLD.published_at
               OR (
                   NEW.published_at IS NOT NULL
                   AND (OLD.published_at IS NULL OR NEW.published_at >= OLD.published_at)
               )
           ) THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'transformation operation results and outbox rows are append-only'
        USING ERRCODE = '55000';
END;
$$
"""


_RECEIPT_FUNCTION_SQL = r"""
CREATE OR REPLACE FUNCTION public.archie_guard_transformation_receipt()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    now_at_database timestamptz := clock_timestamp();
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'command receipt identity and terminal result are immutable'
            USING ERRCODE = '55000';
    END IF;

    IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.actor_id IS DISTINCT FROM OLD.actor_id
       OR NEW.operation IS DISTINCT FROM OLD.operation
       OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       OR NEW.request_digest IS DISTINCT FROM OLD.request_digest
       OR NEW.natural_key IS DISTINCT FROM OLD.natural_key
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'command receipt identity, digest, and natural key are immutable'
            USING ERRCODE = '55000';
    END IF;

    IF OLD.operation_result_id IS NOT NULL
       AND NEW.operation_result_id IS DISTINCT FROM OLD.operation_result_id THEN
        RAISE EXCEPTION 'command receipt terminal result is immutable'
            USING ERRCODE = '55000';
    END IF;

    -- Heartbeat: same fence and state, expiry moves strictly forward.
    IF OLD.status = 'in_progress'
       AND NEW.status = 'in_progress'
       AND NEW.lease_generation = OLD.lease_generation
       AND NEW.claim_token = OLD.claim_token
       AND NEW.claimant_request_id = OLD.claimant_request_id
       AND NEW.operation_result_id IS NOT DISTINCT FROM OLD.operation_result_id
       AND NEW.attempt_count = OLD.attempt_count
       AND NEW.last_error_class IS NOT DISTINCT FROM OLD.last_error_class
       AND NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at
       AND NEW.lease_expires_at > OLD.lease_expires_at
       AND NEW.lease_expires_at > now_at_database THEN
        RETURN NEW;
    END IF;

    -- Reclaim: only an expired/retryable non-terminal lease, exactly next fence.
    IF OLD.status IN ('in_progress', 'retryable_failure')
       AND (OLD.status = 'retryable_failure'
            OR OLD.lease_expires_at IS NULL
            OR OLD.lease_expires_at <= now_at_database)
       AND NEW.status = 'in_progress'
       AND NEW.lease_generation = OLD.lease_generation + 1
       AND NEW.claim_token IS NOT NULL
       AND length(NEW.claim_token) >= 32
       AND NEW.claim_token IS DISTINCT FROM OLD.claim_token
       AND NEW.lease_expires_at > now_at_database
       AND NEW.operation_result_id IS NULL
       AND NEW.attempt_count = OLD.attempt_count + 1
       AND NEW.completed_at IS NULL THEN
        RETURN NEW;
    END IF;

    -- A known pre-commit transient is immediately reclaimable by the same digest.
    IF OLD.status = 'in_progress'
       AND NEW.status = 'retryable_failure'
       AND NEW.lease_generation = OLD.lease_generation
       AND NEW.claim_token = OLD.claim_token
       AND NEW.claimant_request_id = OLD.claimant_request_id
       AND NEW.operation_result_id IS NULL
       AND NEW.attempt_count = OLD.attempt_count
       AND NEW.last_error_class IS NOT NULL
       AND NEW.lease_expires_at <= now_at_database
       AND NEW.completed_at IS NULL THEN
        RETURN NEW;
    END IF;

    -- Validation/authorization failures are terminal but never business success.
    IF OLD.status = 'in_progress'
       AND NEW.status = 'failed_non_retryable'
       AND NEW.lease_generation = OLD.lease_generation
       AND NEW.claim_token = OLD.claim_token
       AND NEW.claimant_request_id = OLD.claimant_request_id
       AND NEW.operation_result_id IS NULL
       AND NEW.attempt_count = OLD.attempt_count
       AND NEW.last_error_class IS NOT NULL
       AND NEW.lease_expires_at IS NULL
       AND NEW.completed_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Atomic finalise or result-led repair. The immutable result is the proof.
    IF OLD.status IN ('in_progress', 'retryable_failure', 'succeeded')
       AND OLD.operation_result_id IS NULL
       AND NEW.status = 'succeeded'
       AND NEW.lease_generation = OLD.lease_generation
       AND NEW.claim_token = OLD.claim_token
       AND NEW.claimant_request_id = OLD.claimant_request_id
       AND NEW.operation_result_id IS NOT NULL
       AND NEW.attempt_count = OLD.attempt_count
       AND NEW.lease_expires_at IS NULL
       AND NEW.completed_at IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM public.operation_results result
           WHERE result.id = NEW.operation_result_id
             AND result.organization_id = NEW.organization_id
             AND result.operation = NEW.operation
             AND result.natural_key = NEW.natural_key
             AND result.request_digest = NEW.request_digest
       ) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'invalid command receipt transition or fence'
        USING ERRCODE = '55000';
END;
$$
"""


def ensure_transformation_db_guards(connection):
    """Install/refresh guards once under a transaction-scoped advisory lock."""
    if connection.dialect.name != "postgresql":
        return
    connection.exec_driver_sql(
        "SELECT pg_advisory_xact_lock(hashtext("
        "'archie_transformation_command_db_guards'))"
    )
    connection.exec_driver_sql(_IMMUTABILITY_FUNCTION_SQL)
    connection.exec_driver_sql(_RECEIPT_FUNCTION_SQL)
    connection.exec_driver_sql(
        "REVOKE ALL ON FUNCTION public.archie_reject_transformation_mutation() FROM PUBLIC"
    )
    connection.exec_driver_sql(
        "REVOKE ALL ON FUNCTION public.archie_guard_transformation_receipt() FROM PUBLIC"
    )
    connection.exec_driver_sql(
        """
        DO $$
        BEGIN
            IF to_regclass('public.operation_results') IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM pg_trigger
                   WHERE tgname = 'trg_transformation_result_immutable'
                     AND tgrelid = to_regclass('public.operation_results')
               ) THEN
                CREATE TRIGGER trg_transformation_result_immutable
                BEFORE UPDATE OR DELETE ON public.operation_results
                FOR EACH ROW
                EXECUTE FUNCTION public.archie_reject_transformation_mutation();
            END IF;

            IF to_regclass('public.transformation_outbox_events') IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM pg_trigger
                   WHERE tgname = 'trg_transformation_outbox_immutable'
                     AND tgrelid = to_regclass('public.transformation_outbox_events')
               ) THEN
                CREATE TRIGGER trg_transformation_outbox_immutable
                BEFORE UPDATE OR DELETE ON public.transformation_outbox_events
                FOR EACH ROW
                EXECUTE FUNCTION public.archie_reject_transformation_mutation();
            END IF;

            IF to_regclass('public.command_idempotency_records') IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM pg_trigger
                   WHERE tgname = 'trg_transformation_receipt_guard'
                     AND tgrelid = to_regclass('public.command_idempotency_records')
               ) THEN
                CREATE TRIGGER trg_transformation_receipt_guard
                BEFORE UPDATE OR DELETE ON public.command_idempotency_records
                FOR EACH ROW
                EXECUTE FUNCTION public.archie_guard_transformation_receipt();
            END IF;
        END;
        $$
        """
    )
    # PUBLIC normally has no table DML rights; make that invariant explicit
    # without removing the owning application's service-path privileges.
    for table_name in (
        "operation_results",
        "transformation_outbox_events",
        "command_idempotency_records",
    ):
        present = connection.exec_driver_sql(
            f"SELECT to_regclass('public.{table_name}') IS NOT NULL"
        ).scalar()
        if present:
            connection.exec_driver_sql(
                f"REVOKE UPDATE, DELETE ON TABLE public.{table_name} FROM PUBLIC"
            )


@event.listens_for(CommandIdempotencyRecord.__table__, "after_create")
@event.listens_for(OperationResult.__table__, "after_create")
@event.listens_for(OperationOutboxEvent.__table__, "after_create")
def _install_transformation_guards_after_create(_target, connection, **_kwargs):
    ensure_transformation_db_guards(connection)


__all__ = ["ensure_transformation_db_guards"]
