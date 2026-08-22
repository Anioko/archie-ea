"""PostgreSQL append-only and fenced-transition guards for command records."""

from __future__ import annotations

from sqlalchemy import event

from app.models.transformation_execution import (
    CommandIdempotencyRecord,
    OperationOutboxEvent,
    OperationResult,
)


TRANSFORMATION_RUNTIME_ROLE = "archie_runtime"


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
             AND result.actor_id = NEW.actor_id
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


_FUNCTION_SPECS = (
    (
        "archie_reject_transformation_mutation",
        _IMMUTABILITY_FUNCTION_SQL,
    ),
    ("archie_guard_transformation_receipt", _RECEIPT_FUNCTION_SQL),
)

_TRIGGER_SPECS = (
    (
        "operation_results",
        "trg_transformation_result_immutable",
        "archie_reject_transformation_mutation",
    ),
    (
        "transformation_outbox_events",
        "trg_transformation_outbox_immutable",
        "archie_reject_transformation_mutation",
    ),
    (
        "command_idempotency_records",
        "trg_transformation_receipt_guard",
        "archie_guard_transformation_receipt",
    ),
)


def _normalise_function_body(body: str) -> str:
    return "\n".join(line.rstrip() for line in body.strip().splitlines())


def _expected_function_body(create_sql: str) -> str:
    return _normalise_function_body(create_sql.split("AS $$", 1)[1].rsplit("$$", 1)[0])


def inspect_transformation_db_guards(connection) -> list[str]:
    """Return semantic guard drift without changing database state."""
    if connection.dialect.name != "postgresql":
        return []
    drift: list[str] = []
    for function_name, create_sql in _FUNCTION_SPECS:
        row = connection.exec_driver_sql(
            """
            SELECT proc.prosrc, proc.prosecdef, proc.proconfig
            FROM pg_proc proc
            JOIN pg_namespace namespace ON namespace.oid = proc.pronamespace
            WHERE namespace.nspname = 'public'
              AND proc.proname = %s
              AND proc.pronargs = 0
              AND proc.prorettype = 'trigger'::regtype
            """,
            (function_name,),
        ).first()
        if row is None:
            drift.append(f"function_missing:{function_name}")
            continue
        if _normalise_function_body(row.prosrc) != _expected_function_body(create_sql):
            drift.append(f"function_body:{function_name}")
        if row.prosecdef is not True:
            drift.append(f"function_security:{function_name}")
        if "search_path=pg_catalog, public" not in (row.proconfig or []):
            drift.append(f"function_search_path:{function_name}")

    for table_name, trigger_name, function_name in _TRIGGER_SPECS:
        table_present = connection.exec_driver_sql(
            f"SELECT to_regclass('public.{table_name}') IS NOT NULL"
        ).scalar()
        if not table_present:
            continue
        row = connection.exec_driver_sql(
            """
            SELECT trigger.tgenabled, trigger.tgtype,
                   namespace.nspname AS function_schema,
                   proc.proname AS function_name
            FROM pg_trigger trigger
            JOIN pg_proc proc ON proc.oid = trigger.tgfoid
            JOIN pg_namespace namespace ON namespace.oid = proc.pronamespace
            WHERE trigger.tgname = %s
              AND trigger.tgrelid = to_regclass(%s)
              AND NOT trigger.tgisinternal
            """,
            (trigger_name, f"public.{table_name}"),
        ).first()
        if row is None:
            drift.append(f"trigger_missing:{trigger_name}")
            continue
        if row.tgenabled != "O":
            drift.append(f"trigger_disabled:{trigger_name}")
        if row.function_schema != "public" or row.function_name != function_name:
            drift.append(f"trigger_function:{trigger_name}")
        # PostgreSQL tgtype: ROW(1) | BEFORE(2) | DELETE(8) | UPDATE(16).
        if row.tgtype != 27:
            drift.append(f"trigger_shape:{trigger_name}")
    return drift


def _repair_triggers(connection) -> None:
    for table_name, trigger_name, function_name in _TRIGGER_SPECS:
        table_present = connection.exec_driver_sql(
            f"SELECT to_regclass('public.{table_name}') IS NOT NULL"
        ).scalar()
        if not table_present:
            continue
        row = connection.exec_driver_sql(
            """
            SELECT trigger.tgenabled, trigger.tgtype,
                   namespace.nspname AS function_schema,
                   proc.proname AS function_name
            FROM pg_trigger trigger
            JOIN pg_proc proc ON proc.oid = trigger.tgfoid
            JOIN pg_namespace namespace ON namespace.oid = proc.pronamespace
            WHERE trigger.tgname = %s
              AND trigger.tgrelid = to_regclass(%s)
              AND NOT trigger.tgisinternal
            """,
            (trigger_name, f"public.{table_name}"),
        ).first()
        correct = (
            row is not None
            and row.tgenabled == "O"
            and row.tgtype == 27
            and row.function_schema == "public"
            and row.function_name == function_name
        )
        if correct:
            continue
        connection.exec_driver_sql(
            f"DROP TRIGGER IF EXISTS {trigger_name} ON public.{table_name}"
        )
        connection.exec_driver_sql(
            f"CREATE TRIGGER {trigger_name} "
            f"BEFORE UPDATE OR DELETE ON public.{table_name} "
            "FOR EACH ROW "
            f"EXECUTE FUNCTION public.{function_name}()"
        )


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
    runtime_role_exists = connection.exec_driver_sql(
        "SELECT EXISTS (SELECT 1 FROM pg_roles "
        f"WHERE rolname = '{TRANSFORMATION_RUNTIME_ROLE}')"
    ).scalar()
    if runtime_role_exists:
        connection.exec_driver_sql(
            "REVOKE ALL ON FUNCTION "
            "public.archie_reject_transformation_mutation() "
            f"FROM {TRANSFORMATION_RUNTIME_ROLE}"
        )
        connection.exec_driver_sql(
            "REVOKE ALL ON FUNCTION public.archie_guard_transformation_receipt() "
            f"FROM {TRANSFORMATION_RUNTIME_ROLE}"
        )
    _repair_triggers(connection)
    # The runtime role gets only the columns required by the service protocol.
    # It never owns these objects and has no DELETE or TRUNCATE privilege.
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
                f"REVOKE ALL ON TABLE public.{table_name} FROM PUBLIC"
            )
    if runtime_role_exists:
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
                    f"REVOKE ALL ON TABLE public.{table_name} "
                    f"FROM {TRANSFORMATION_RUNTIME_ROLE}"
                )
                connection.exec_driver_sql(
                    f"GRANT SELECT, INSERT ON TABLE public.{table_name} "
                    f"TO {TRANSFORMATION_RUNTIME_ROLE}"
                )
        if connection.exec_driver_sql(
            "SELECT to_regclass('public.transformation_outbox_events') IS NOT NULL"
        ).scalar():
            connection.exec_driver_sql(
                "GRANT UPDATE (delivery_attempts, published_at) ON TABLE "
                "public.transformation_outbox_events "
                f"TO {TRANSFORMATION_RUNTIME_ROLE}"
            )
        if connection.exec_driver_sql(
            "SELECT to_regclass('public.command_idempotency_records') IS NOT NULL"
        ).scalar():
            connection.exec_driver_sql(
                "GRANT UPDATE (status, lease_generation, claim_token, "
                "claimant_request_id, lease_expires_at, operation_result_id, "
                "attempt_count, last_error_class, updated_at, completed_at) "
                "ON TABLE public.command_idempotency_records "
                f"TO {TRANSFORMATION_RUNTIME_ROLE}"
            )
    remaining_drift = inspect_transformation_db_guards(connection)
    if remaining_drift:
        raise RuntimeError(
            "transformation database guard repair incomplete: "
            + ", ".join(remaining_drift)
        )


@event.listens_for(CommandIdempotencyRecord.__table__, "after_create")
@event.listens_for(OperationResult.__table__, "after_create")
@event.listens_for(OperationOutboxEvent.__table__, "after_create")
def _install_transformation_guards_after_create(_target, connection, **_kwargs):
    ensure_transformation_db_guards(connection)


__all__ = [
    "TRANSFORMATION_RUNTIME_ROLE",
    "ensure_transformation_db_guards",
    "inspect_transformation_db_guards",
]
