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
    )
    assert reclaimed.generation == claim.generation + 1
    assert reclaimed.claim_token != claim.claim_token
    with pytest.raises(StaleClaim):
        CommandService.heartbeat(actor=guard_fixture.actor, claim=claim)


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
