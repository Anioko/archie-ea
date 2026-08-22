"""Direct-driver proof for transformation command database guards."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import db
from app.models.organization import Organization
from app.models.transformation_db_guards import ensure_transformation_db_guards
from app.models.transformation_execution import (
    CommandIdempotencyRecord,
    OperationOutboxEvent,
    OperationResult,
)
from app.models.user import User
from app.modules.transformation_room.command_service import CommandService
from app.modules.transformation_room.domain import ActorContext, DomainMutationResult, StaleClaim


@dataclass(frozen=True)
class GuardFixture:
    actor: ActorContext
    organization_id: int
    receipt_id: int
    result_id: int
    outbox_id: int
    idempotency_key: str
    payload: dict
    natural_key: str


def _allow_command(_session, _actor, _operation, _natural_key):
    return None


@pytest.fixture
def guard_fixture(app, _schema):
    suffix = uuid.uuid4().hex[:12]
    with app.app_context():
        with db.engine.begin() as connection:
            ensure_transformation_db_guards(connection)
            ensure_transformation_db_guards(connection)

        db.session.remove()
        organization = Organization(name=f"Guard Org {suffix}", slug=f"guard-org-{suffix}")
        db.session.add(organization)
        db.session.flush()
        user = User(
            email=f"guard-{suffix}@example.test",
            organization_id=organization.id,
            confirmed=True,
            enterprise_role="enterprise_architect",
        )
        db.session.add(user)
        db.session.flush()
        organization_id = organization.id
        user_id = user.id
        db.session.commit()
        db.session.remove()

        actor = ActorContext(
            user_id=user_id,
            organization_id=organization_id,
            roles=frozenset({"enterprise_architect"}),
            request_id=f"guard-request-{suffix}",
        )
        key = f"guard-{suffix}"
        payload = {"name": f"guard object {suffix}"}
        natural_key = f"guard:{suffix}"

        def mutation(_session, _claim):
            return DomainMutationResult(
                object_ids={"guard_id": organization_id},
                response={"guard_id": organization_id},
                outbox_events=(
                    {
                        "event_type": "guard.created",
                        "payload": {"guard_id": organization_id},
                    },
                ),
            )

        result = CommandService.execute(
            actor=actor,
            operation="guard.create",
            idempotency_key=key,
            payload=payload,
            natural_key=natural_key,
            authorizer=_allow_command,
            handler=mutation,
        )
        with Session(db.engine) as session:
            receipt = session.execute(
                select(CommandIdempotencyRecord).where(
                    CommandIdempotencyRecord.organization_id == organization_id,
                    CommandIdempotencyRecord.actor_id == user_id,
                    CommandIdempotencyRecord.operation == "guard.create",
                    CommandIdempotencyRecord.idempotency_key == key,
                )
            ).scalar_one()
            outbox = session.execute(
                select(OperationOutboxEvent).where(
                    OperationOutboxEvent.organization_id == organization_id,
                    OperationOutboxEvent.operation_result_id == result.operation_result_id,
                )
            ).scalar_one()
            fixture = GuardFixture(
                actor=actor,
                organization_id=organization_id,
                receipt_id=receipt.id,
                result_id=result.operation_result_id,
                outbox_id=outbox.id,
                idempotency_key=key,
                payload=payload,
                natural_key=natural_key,
            )
        try:
            yield fixture
        finally:
            db.session.remove()
            with db.engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
                for table_name in (
                    "transformation_outbox_events",
                    "operation_results",
                    "command_idempotency_records",
                    "users",
                ):
                    connection.execute(
                        text(
                            f'DELETE FROM "{table_name}" '
                            "WHERE organization_id = :organization_id"
                        ),
                        {"organization_id": organization_id},
                    )
                connection.execute(
                    text("DELETE FROM organizations WHERE id = :organization_id"),
                    {"organization_id": organization_id},
                )


def _direct_driver_execute(statement, parameters):
    connection = db.engine.raw_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(statement, parameters)
            connection.commit()
        finally:
            cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def test_guard_installation_is_idempotent_and_functions_fix_search_path(guard_fixture):
    """Catches duplicate triggers or SECURITY DEFINER search-path hijacking."""
    with db.engine.connect() as connection:
        triggers = connection.execute(
            text(
                """
                SELECT tg.tgname, cls.relname
                FROM pg_trigger tg
                JOIN pg_class cls ON cls.oid = tg.tgrelid
                WHERE NOT tg.tgisinternal
                  AND tg.tgname IN (
                    'trg_transformation_result_immutable',
                    'trg_transformation_outbox_immutable',
                    'trg_transformation_receipt_guard'
                  )
                ORDER BY tg.tgname
                """
            )
        ).all()
        functions = connection.execute(
            text(
                """
                SELECT proname, prosecdef, proconfig
                FROM pg_proc
                WHERE proname IN (
                    'archie_reject_transformation_mutation',
                    'archie_guard_transformation_receipt'
                )
                ORDER BY proname
                """
            )
        ).all()

    assert triggers == [
        ("trg_transformation_outbox_immutable", "transformation_outbox_events"),
        ("trg_transformation_receipt_guard", "command_idempotency_records"),
        ("trg_transformation_result_immutable", "operation_results"),
    ]
    assert len(functions) == 2
    assert all(row.prosecdef is True for row in functions)
    assert all("search_path=pg_catalog, public" in row.proconfig for row in functions)


@pytest.mark.parametrize(
    ("statement", "id_field"),
    (
        (
            "/* comment-prefixed */ UPDATE public.operation_results "
            "SET response_json = '{}'::json WHERE id = %s AND organization_id = %s",
            "result_id",
        ),
        (
            "WITH target AS (SELECT id FROM public.operation_results "
            "WHERE id = %s AND organization_id = %s) "
            "DELETE FROM public.operation_results r USING target "
            "WHERE r.id = target.id",
            "result_id",
        ),
        (
            "UPDATE public.transformation_outbox_events "
            "SET payload_json = '{}'::json WHERE id = %s AND organization_id = %s",
            "outbox_id",
        ),
        (
            "WITH target AS (SELECT id FROM public.transformation_outbox_events "
            "WHERE id = %s AND organization_id = %s) "
            "DELETE FROM public.transformation_outbox_events e USING target "
            "WHERE e.id = target.id",
            "outbox_id",
        ),
    ),
)
def test_direct_driver_cannot_update_or_delete_results_and_outbox(
    guard_fixture, statement, id_field
):
    """Catches lexical SQL variants bypassing append-only enforcement."""
    with pytest.raises(Exception, match="append-only"):
        _direct_driver_execute(
            statement,
            (getattr(guard_fixture, id_field), guard_fixture.organization_id),
        )


@pytest.mark.parametrize(
    ("assignment", "value"),
    (
        ("actor_id = %s", 999999999),
        ("operation = %s", "changed.operation"),
        ("idempotency_key = %s", "changed-key"),
        ("request_digest = %s", "0" * 64),
        ("natural_key = %s", "changed-natural-key"),
        ("operation_result_id = %s", None),
    ),
)
def test_receipt_identity_digest_natural_key_and_terminal_result_are_immutable(
    guard_fixture, assignment, value
):
    """Catches a direct client rebinding or erasing a completed command."""
    statement = (
        f"/* direct mutation */ UPDATE public.command_idempotency_records SET {assignment} "
        "WHERE id = %s AND organization_id = %s"
    )
    with pytest.raises(Exception, match="immutable"):
        _direct_driver_execute(
            statement,
            (value, guard_fixture.receipt_id, guard_fixture.organization_id),
        )


def test_direct_driver_cannot_delete_receipt(guard_fixture):
    """Catches command identity and its terminal result pointer being erased."""
    with pytest.raises(Exception, match="immutable"):
        _direct_driver_execute(
            "DELETE FROM public.command_idempotency_records "
            "WHERE id = %s AND organization_id = %s",
            (guard_fixture.receipt_id, guard_fixture.organization_id),
        )


def test_outbox_delivery_metadata_advances_without_mutating_event(guard_fixture):
    """Catches append-only protection making at-least-once delivery impossible."""
    _direct_driver_execute(
        "UPDATE public.transformation_outbox_events "
        "SET delivery_attempts = delivery_attempts + 1, "
        "published_at = clock_timestamp() "
        "WHERE id = %s AND organization_id = %s",
        (guard_fixture.outbox_id, guard_fixture.organization_id),
    )

    with Session(db.engine) as session:
        event = session.execute(
            select(OperationOutboxEvent).where(
                OperationOutboxEvent.id == guard_fixture.outbox_id,
                OperationOutboxEvent.organization_id == guard_fixture.organization_id,
            )
        ).scalar_one()
    assert event.delivery_attempts == 1
    assert event.published_at is not None
    assert event.event_type == "guard.created"
    assert event.payload_json == {"guard_id": guard_fixture.organization_id}


def test_fencing_trigger_rejects_invalid_generation_and_old_worker(guard_fixture, app):
    """Catches token reuse, generation skipping, and post-reclaim heartbeat."""
    key = f"lease-{uuid.uuid4().hex[:8]}"
    payload = {"name": key}
    claim = CommandService.claim_or_reconcile(
        actor=guard_fixture.actor,
        operation="guard.lease",
        idempotency_key=key,
        request_digest=CommandService.request_digest(payload),
        natural_key=f"guard-lease:{key}",
        authorizer=_allow_command,
    )
    extended = CommandService.heartbeat(actor=guard_fixture.actor, claim=claim)
    assert extended.claim_token == claim.claim_token
    assert extended.generation == claim.generation

    with pytest.raises(Exception, match="invalid command receipt transition"):
        _direct_driver_execute(
            "UPDATE public.command_idempotency_records "
            "SET lease_generation = lease_generation + 2, claim_token = %s, "
            "lease_expires_at = clock_timestamp() + interval '1 minute' "
            "WHERE id = %s AND organization_id = %s",
            (str(uuid.uuid4()), claim.receipt_id, guard_fixture.organization_id),
        )

    with db.engine.begin() as connection:
        connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
        connection.execute(
            text(
                "UPDATE command_idempotency_records "
                "SET lease_expires_at = clock_timestamp() - interval '1 second' "
                "WHERE id = :receipt_id AND organization_id = :organization_id"
            ),
            {
                "receipt_id": claim.receipt_id,
                "organization_id": guard_fixture.organization_id,
            },
        )

    reclaimed = CommandService.claim_or_reconcile(
        actor=guard_fixture.actor,
        operation="guard.lease",
        idempotency_key=key,
        request_digest=CommandService.request_digest(payload),
        natural_key=f"guard-lease:{key}",
        authorizer=_allow_command,
    )
    assert reclaimed.generation == claim.generation + 1
    assert reclaimed.claim_token != claim.claim_token
    with pytest.raises(StaleClaim):
        CommandService.heartbeat(actor=guard_fixture.actor, claim=claim)


def test_receipt_guard_rejects_result_owned_by_another_actor(guard_fixture):
    """Catches direct receipt repair binding actor B to actor A's result."""
    suffix = uuid.uuid4().hex[:12]
    second_user = User(
        email=f"guard-second-{suffix}@example.test",
        organization_id=guard_fixture.organization_id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db.session.add(second_user)
    db.session.commit()
    second_actor = ActorContext(
        user_id=second_user.id,
        organization_id=guard_fixture.organization_id,
        roles=guard_fixture.actor.roles,
        request_id=f"guard-second-request-{suffix}",
    )
    claim = CommandService.claim_or_reconcile(
        actor=second_actor,
        operation="guard.create",
        idempotency_key=f"guard-second-{suffix}",
        request_digest=CommandService.request_digest(guard_fixture.payload),
        natural_key=guard_fixture.natural_key,
        authorizer=_allow_command,
    )

    with pytest.raises(Exception, match="invalid command receipt transition"):
        _direct_driver_execute(
            "UPDATE public.command_idempotency_records "
            "SET status = 'succeeded', operation_result_id = %s, "
            "lease_expires_at = NULL, completed_at = clock_timestamp() "
            "WHERE id = %s AND organization_id = %s AND actor_id = %s",
            (
                guard_fixture.result_id,
                claim.receipt_id,
                guard_fixture.organization_id,
                second_actor.user_id,
            ),
        )


def test_reconciliation_guard_can_be_reinstalled_without_changing_success(
    guard_fixture,
):
    """Catches guard replacement corrupting an existing canonical replay."""
    with db.engine.begin() as connection:
        ensure_transformation_db_guards(connection)

    replay = CommandService.execute(
        actor=guard_fixture.actor,
        operation="guard.create",
        idempotency_key=guard_fixture.idempotency_key,
        payload=guard_fixture.payload,
        natural_key=guard_fixture.natural_key,
        authorizer=_allow_command,
        handler=lambda _session, _claim: pytest.fail("replay executed handler"),
    )

    assert replay.created is False and replay.idempotent is True
    assert replay.operation_result_id == guard_fixture.result_id


def test_schema_reconciliation_restores_missing_guard_idempotently(guard_fixture):
    """Catches long-lived databases missing Task 3 guards after deployment."""
    from app.commands.reconcile_schema import _reconcile

    with db.engine.begin() as connection:
        connection.exec_driver_sql(
            "DROP TRIGGER trg_transformation_result_immutable ON operation_results"
        )

    _added, first_failed, _missing, _blocking = _reconcile(dry_run=False)
    assert first_failed == []
    _added, second_failed, _missing, _blocking = _reconcile(dry_run=False)
    assert second_failed == []

    with db.engine.connect() as connection:
        trigger_count = connection.scalar(
            text(
                """
                SELECT count(*) FROM pg_trigger
                WHERE tgname = 'trg_transformation_result_immutable'
                  AND tgrelid = 'operation_results'::regclass
                  AND NOT tgisinternal
                """
            )
        )
    assert trigger_count == 1


def test_schema_dry_run_reports_disabled_guard_without_mutating_it(guard_fixture):
    """Catches a same-name disabled trigger being treated as installed."""
    from app.commands.reconcile_schema import _reconcile

    with db.engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE operation_results "
            "DISABLE TRIGGER trg_transformation_result_immutable"
        )
    try:
        _added, failed, _missing, _blocking = _reconcile(dry_run=True)
        assert any(
            "trg_transformation_result_immutable" in item and "disabled" in item
            for item in failed
        )
        with db.engine.connect() as connection:
            assert connection.scalar(
                text(
                    "SELECT tgenabled FROM pg_trigger "
                    "WHERE tgname = 'trg_transformation_result_immutable' "
                    "AND tgrelid = 'operation_results'::regclass"
                )
            ) == "D"

        _added, repaired_failed, _missing, _blocking = _reconcile(dry_run=False)
        assert repaired_failed == []
        with db.engine.connect() as connection:
            assert connection.scalar(
                text(
                    "SELECT tgenabled FROM pg_trigger "
                    "WHERE tgname = 'trg_transformation_result_immutable' "
                    "AND tgrelid = 'operation_results'::regclass"
                )
            ) == "O"
    finally:
        with db.engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE operation_results "
                "ENABLE TRIGGER trg_transformation_result_immutable"
            )


def test_guard_installation_replaces_miswired_same_name_trigger(guard_fixture):
    """Catches trigger-name-only reconciliation accepting the wrong function."""
    with db.engine.begin() as connection:
        connection.exec_driver_sql(
            "DROP TRIGGER trg_transformation_result_immutable ON operation_results"
        )
        connection.exec_driver_sql(
            "CREATE TRIGGER trg_transformation_result_immutable "
            "BEFORE UPDATE OR DELETE ON operation_results FOR EACH ROW "
            "EXECUTE FUNCTION public.archie_guard_transformation_receipt()"
        )
    try:
        with db.engine.begin() as connection:
            ensure_transformation_db_guards(connection)
        with db.engine.connect() as connection:
            function_name = connection.scalar(
                text(
                    "SELECT proc.proname FROM pg_trigger trigger "
                    "JOIN pg_proc proc ON proc.oid = trigger.tgfoid "
                    "WHERE trigger.tgname = 'trg_transformation_result_immutable' "
                    "AND trigger.tgrelid = 'operation_results'::regclass"
                )
            )
        assert function_name == "archie_reject_transformation_mutation"
    finally:
        with db.engine.begin() as connection:
            connection.exec_driver_sql(
                "DROP TRIGGER IF EXISTS trg_transformation_result_immutable "
                "ON operation_results"
            )
            connection.exec_driver_sql(
                "CREATE TRIGGER trg_transformation_result_immutable "
                "BEFORE UPDATE OR DELETE ON operation_results FOR EACH ROW "
                "EXECUTE FUNCTION public.archie_reject_transformation_mutation()"
            )


@pytest.mark.parametrize(
    ("trigger_clause", "drift_marker", "definition_marker"),
    (
        (
            "BEFORE UPDATE OR DELETE ON operation_results FOR EACH ROW "
            "WHEN (false)",
            "trigger_when",
            "WHEN (false)",
        ),
        (
            "BEFORE UPDATE OF created_at OR DELETE ON operation_results "
            "FOR EACH ROW",
            "trigger_columns",
            "UPDATE OF created_at",
        ),
    ),
)
def test_schema_reconciliation_repairs_conditional_or_column_limited_guard(
    guard_fixture,
    trigger_clause,
    drift_marker,
    definition_marker,
):
    """Catches a correct-name/function trigger whose predicate disables updates."""
    from app.commands.reconcile_schema import _reconcile

    with db.engine.begin() as connection:
        connection.exec_driver_sql(
            "DROP TRIGGER trg_transformation_result_immutable "
            "ON operation_results"
        )
        connection.exec_driver_sql(
            "CREATE TRIGGER trg_transformation_result_immutable "
            f"{trigger_clause} "
            "EXECUTE FUNCTION public.archie_reject_transformation_mutation()"
        )
    try:
        _added, failed, _missing, _blocking = _reconcile(dry_run=True)
        assert any(
            drift_marker in item
            and "trg_transformation_result_immutable" in item
            for item in failed
        )
        with db.engine.connect() as connection:
            tampered_definition = connection.scalar(
                text(
                    "SELECT pg_get_triggerdef(oid) FROM pg_trigger "
                    "WHERE tgname = 'trg_transformation_result_immutable' "
                    "AND tgrelid = 'operation_results'::regclass"
                )
            )
        assert definition_marker in tampered_definition

        _added, repaired_failed, _missing, _blocking = _reconcile(dry_run=False)
        assert repaired_failed == []
        with db.engine.connect() as connection:
            repaired_definition = connection.scalar(
                text(
                    "SELECT pg_get_triggerdef(oid) FROM pg_trigger "
                    "WHERE tgname = 'trg_transformation_result_immutable' "
                    "AND tgrelid = 'operation_results'::regclass"
                )
            )
        assert definition_marker not in repaired_definition
        with pytest.raises(Exception, match="append-only"):
            _direct_driver_execute(
                "UPDATE operation_results SET request_digest = %s "
                "WHERE id = %s AND organization_id = %s",
                (
                    "e" * 64,
                    guard_fixture.result_id,
                    guard_fixture.organization_id,
                ),
            )
    finally:
        with db.engine.begin() as connection:
            ensure_transformation_db_guards(connection)


def test_schema_dry_run_reports_tampered_guard_function_then_apply_repairs_it(
    guard_fixture,
):
    """Catches a correct function name hiding a replaced permissive body."""
    from app.commands.reconcile_schema import _reconcile

    with db.engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE OR REPLACE FUNCTION public.archie_reject_transformation_mutation()
            RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
            SET search_path = pg_catalog, public AS $$
            BEGIN
                RETURN NEW;
            END;
            $$
            """
        )
    try:
        _added, failed, _missing, _blocking = _reconcile(dry_run=True)
        assert any(
            "archie_reject_transformation_mutation" in item
            and "function_body" in item
            for item in failed
        )
        with db.engine.connect() as connection:
            before_body = connection.scalar(
                text(
                    "SELECT prosrc FROM pg_proc proc "
                    "JOIN pg_namespace ns ON ns.oid = proc.pronamespace "
                    "WHERE ns.nspname = 'public' "
                    "AND proc.proname = 'archie_reject_transformation_mutation'"
                )
            )
        assert "RETURN NEW" in before_body

        _added, repaired_failed, _missing, _blocking = _reconcile(dry_run=False)
        assert repaired_failed == []
        with pytest.raises(Exception, match="append-only"):
            _direct_driver_execute(
                "UPDATE public.operation_results SET request_digest = %s "
                "WHERE id = %s AND organization_id = %s",
                ("f" * 64, guard_fixture.result_id, guard_fixture.organization_id),
            )
    finally:
        with db.engine.begin() as connection:
            ensure_transformation_db_guards(connection)
