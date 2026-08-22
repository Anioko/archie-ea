"""PostgreSQL crash, replay, and stale-worker proof for transformation commands."""

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import db
from app.models.organization import Organization
from app.models.strategic import StrategicInitiative
from app.models.transformation_execution import (
    CommandIdempotencyRecord,
    OperationOutboxEvent,
    OperationResult,
)
from app.models.user import User
from app.modules.transformation_room.command_service import (
    CommandService,
    canonical_request_digest,
)
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    CommandResult,
    DomainMutationResult,
    KnownPreCommitTransient,
    NotAuthorised,
    StaleClaim,
)


@dataclass(frozen=True)
class CommandFixture:
    actor: ActorContext
    organization_id: int
    user_id: int
    domain_name: str


@pytest.fixture
def command_fixture(app, _schema):
    """Committed rows are required so independent workers see the same state."""
    suffix = uuid.uuid4().hex[:12]
    with app.app_context():
        db.session.remove()
        organization = Organization(
            name=f"Command Org {suffix}", slug=f"command-org-{suffix}"
        )
        db.session.add(organization)
        db.session.flush()
        user = User(
            email=f"command-{suffix}@example.test",
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

        original_lease = app.config.get("TRANSFORMATION_COMMAND_LEASE_SECONDS")
        app.config["TRANSFORMATION_COMMAND_LEASE_SECONDS"] = 0.12
        fixture = CommandFixture(
            actor=ActorContext(
                user_id=user_id,
                organization_id=organization_id,
                roles=frozenset({"enterprise_architect"}),
                request_id=f"request-{suffix}",
            ),
            organization_id=organization_id,
            user_id=user_id,
            domain_name=f"Programme {suffix}",
        )
        try:
            yield fixture
        finally:
            db.session.remove()
            if original_lease is None:
                app.config.pop("TRANSFORMATION_COMMAND_LEASE_SECONDS", None)
            else:
                app.config["TRANSFORMATION_COMMAND_LEASE_SECONDS"] = original_lease
            # Append-only guards intentionally block ordinary cleanup. The test
            # database owner disables triggers only for these recorded tenant IDs.
            with db.engine.begin() as connection:
                connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
                for table_name in (
                    "transformation_outbox_events",
                    "operation_results",
                    "command_idempotency_records",
                    "strategic_initiatives",
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


def _mutation(fixture: CommandFixture, *, events: int = 1):
    def handler(session, _claim):
        programme = StrategicInitiative(
            organization_id=fixture.organization_id,
            name=fixture.domain_name,
            record_kind="transformation_programme",
            description="Created by a fenced command",
        )
        session.add(programme)
        session.flush()
        return DomainMutationResult(
            object_ids={"programme_id": programme.id},
            response={"programme_id": programme.id, "name": programme.name},
            outbox_events=tuple(
                {
                    "event_type": "programme.created",
                    "payload": {"programme_id": programme.id, "ordinal": ordinal},
                }
                for ordinal in range(events)
            ),
        )

    return handler


def _execute(fixture: CommandFixture, *, key="same", payload=None, handler=None):
    return CommandService.execute(
        actor=fixture.actor,
        operation="programme.create",
        idempotency_key=key,
        payload=payload or {"name": fixture.domain_name, "scope": {"b": 2, "a": 1}},
        natural_key=f"programme-intake:{key}",
        handler=handler or _mutation(fixture),
    )


def _counts(fixture: CommandFixture):
    with Session(db.engine) as session:
        domain = session.scalar(
            select(db.func.count())
            .select_from(StrategicInitiative)
            .where(
                StrategicInitiative.organization_id == fixture.organization_id,
                StrategicInitiative.name == fixture.domain_name,
            )
        )
        results = session.scalar(
            select(db.func.count())
            .select_from(OperationResult)
            .where(OperationResult.organization_id == fixture.organization_id)
        )
        events = session.scalar(
            select(db.func.count())
            .select_from(OperationOutboxEvent)
            .where(OperationOutboxEvent.organization_id == fixture.organization_id)
        )
    return domain, results, events


def _receipt(fixture: CommandFixture, key="same"):
    with Session(db.engine) as session:
        return session.execute(
            select(CommandIdempotencyRecord).where(
                CommandIdempotencyRecord.organization_id == fixture.organization_id,
                CommandIdempotencyRecord.actor_id == fixture.user_id,
                CommandIdempotencyRecord.operation == "programme.create",
                CommandIdempotencyRecord.idempotency_key == key,
            )
        ).scalar_one()


def _wait_for_expiry(claim):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        with Session(db.engine) as session:
            expired = session.scalar(
                text(
                    "SELECT lease_expires_at <= clock_timestamp() "
                    "FROM command_idempotency_records WHERE id = :receipt_id"
                ),
                {"receipt_id": claim.receipt_id},
            )
        if expired:
            return
        time.sleep(0.02)
    raise AssertionError("command lease did not expire")


@contextmanager
def _deferred_result_failure(organization_id: int):
    suffix = uuid.uuid4().hex[:10]
    function = f"test_fail_result_commit_{suffix}"
    trigger = f"trg_test_fail_result_commit_{suffix}"
    with db.engine.begin() as connection:
        connection.exec_driver_sql(
            f"""
            CREATE FUNCTION {function}() RETURNS trigger
            LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
            BEGIN
                IF NEW.organization_id = {int(organization_id)} THEN
                    RAISE EXCEPTION 'simulated failure after operation result insert';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        connection.exec_driver_sql(
            f"""
            CREATE CONSTRAINT TRIGGER {trigger}
            AFTER INSERT ON operation_results
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION {function}()
            """
        )
    try:
        yield
    finally:
        db.session.remove()
        with db.engine.begin() as connection:
            connection.exec_driver_sql(
                f"DROP TRIGGER IF EXISTS {trigger} ON operation_results"
            )
            connection.exec_driver_sql(f"DROP FUNCTION IF EXISTS {function}()")


def test_canonical_digest_is_stable_for_equivalent_nested_json(command_fixture):
    """Catches request-key ordering being bound as a different command identity."""
    left = {"z": [3, {"b": False, "a": None}], "name": "é"}
    right = {"name": "é", "z": [3, {"a": None, "b": False}]}

    assert canonical_request_digest(left) == canonical_request_digest(right)
    assert len(canonical_request_digest(left)) == 64


def test_execute_owns_domain_transaction_after_request_identity_read(command_fixture):
    """Catches request user loading making the command transaction impossible to begin."""
    loaded_user_id = db.session.scalar(
        select(User.id).where(
            User.id == command_fixture.user_id,
            User.organization_id == command_fixture.organization_id,
        )
    )
    assert loaded_user_id == command_fixture.user_id
    assert db.session().in_transaction() is True

    result = _execute(command_fixture, key="request-read")

    assert result.created is True
    assert _counts(command_fixture) == (1, 1, 1)


def test_claim_then_crash_reclaims_only_after_expiry(command_fixture):
    """Catches an independent claim transaction becoming a permanent orphan."""
    digest = canonical_request_digest({"name": command_fixture.domain_name})
    claim = CommandService.claim_or_reconcile(
        actor=command_fixture.actor,
        operation="programme.create",
        idempotency_key="claim-crash",
        request_digest=digest,
        natural_key="programme-intake:claim-crash",
    )

    assert claim.generation == 1
    assert _receipt(command_fixture, "claim-crash").status == "in_progress"
    _wait_for_expiry(claim)

    result = _execute(
        command_fixture,
        key="claim-crash",
        payload={"name": command_fixture.domain_name},
    )

    assert result.created is True
    assert _receipt(command_fixture, "claim-crash").lease_generation == 2
    assert _counts(command_fixture) == (1, 1, 1)


def test_domain_insert_then_known_failure_rolls_back_and_recovers(command_fixture):
    """Catches domain writes escaping before a retryable failure is recorded."""
    attempts = 0

    def fail_after_insert(session, claim):
        nonlocal attempts
        attempts += 1
        _mutation(command_fixture)(session, claim)
        raise KnownPreCommitTransient("database_temporarily_unavailable")

    with pytest.raises(KnownPreCommitTransient):
        _execute(command_fixture, key="retryable", handler=fail_after_insert)

    receipt = _receipt(command_fixture, "retryable")
    assert receipt.status == "retryable_failure"
    assert receipt.operation_result_id is None
    assert receipt.attempt_count == 1
    assert receipt.last_error_class == "KnownPreCommitTransient"
    assert _counts(command_fixture) == (0, 0, 0)

    recovered = _execute(command_fixture, key="retryable")

    assert recovered.created is True
    assert attempts == 1
    assert _receipt(command_fixture, "retryable").lease_generation == 2
    assert _counts(command_fixture) == (1, 1, 1)


def test_authorisation_failure_is_terminal_and_never_replayed_as_success(
    command_fixture,
):
    """Catches known non-retryable denials being reclaimed and re-executed."""
    calls = 0

    def deny(_session, _claim):
        nonlocal calls
        calls += 1
        raise NotAuthorised("programme_create_not_authorised")

    with pytest.raises(NotAuthorised):
        _execute(command_fixture, key="denied", handler=deny)

    receipt = _receipt(command_fixture, "denied")
    assert receipt.status == "failed_non_retryable"
    assert receipt.operation_result_id is None
    assert receipt.lease_expires_at is None
    assert receipt.completed_at is not None
    assert receipt.last_error_class == "NotAuthorised"
    assert _counts(command_fixture) == (0, 0, 0)

    with pytest.raises(CommandConflict) as replay:
        _execute(command_fixture, key="denied", handler=deny)
    assert replay.value.reason == "failed_non_retryable"
    assert calls == 1
    assert _counts(command_fixture) == (0, 0, 0)


def test_result_then_deferred_commit_failure_is_atomic(command_fixture):
    """Catches a result/outbox/domain row surviving a failure at COMMIT."""
    with _deferred_result_failure(command_fixture.organization_id):
        with pytest.raises(Exception, match="simulated failure after operation result insert"):
            _execute(command_fixture, key="commit-failure", handler=_mutation(command_fixture, events=2))

    assert _counts(command_fixture) == (0, 0, 0)
    receipt = _receipt(command_fixture, "commit-failure")
    assert receipt.status == "in_progress"
    assert receipt.operation_result_id is None

    _wait_for_expiry(
        CommandService.claim_from_record(receipt)
    )
    recovered = _execute(command_fixture, key="commit-failure", handler=_mutation(command_fixture, events=2))

    assert recovered.created is True
    assert _counts(command_fixture) == (1, 1, 2)


def test_committed_result_replays_after_simulated_lost_response(command_fixture):
    """Catches a lost HTTP response causing duplicate committed effects."""
    committed = _execute(command_fixture, key="lost-response", handler=_mutation(command_fixture, events=2))
    # The transport loses ``committed`` here; the client repeats the same request.
    replayed = _execute(command_fixture, key="lost-response", handler=_mutation(command_fixture, events=2))

    assert committed.created is True and committed.idempotent is False
    assert replayed.created is False and replayed.idempotent is True
    assert replayed.operation_result_id == committed.operation_result_id
    assert replayed.object_ids == committed.object_ids
    assert replayed.response == committed.response
    assert _counts(command_fixture) == (1, 1, 2)
    with Session(db.engine) as session:
        event_ids = session.scalars(
            select(OperationOutboxEvent.event_id)
            .where(OperationOutboxEvent.organization_id == command_fixture.organization_id)
            .order_by(OperationOutboxEvent.ordinal)
        ).all()
    assert len(event_ids) == len(set(event_ids)) == 2
    assert all(uuid.UUID(event_id).version == 4 for event_id in event_ids)


def test_expired_lease_reconciles_existing_result_without_handler(command_fixture):
    """Catches reclaim re-executing after result commit but before receipt repair."""
    payload = {"name": command_fixture.domain_name}
    digest = canonical_request_digest(payload)
    claim = CommandService.claim_or_reconcile(
        actor=command_fixture.actor,
        operation="programme.create",
        idempotency_key="orphan-result",
        request_digest=digest,
        natural_key="programme-intake:orphan-result",
    )
    with Session(db.engine) as session, session.begin():
        programme = StrategicInitiative(
            organization_id=command_fixture.organization_id,
            name=command_fixture.domain_name,
            record_kind="transformation_programme",
        )
        session.add(programme)
        session.flush()
        persisted = OperationResult(
            organization_id=command_fixture.organization_id,
            actor_id=command_fixture.user_id,
            operation="programme.create",
            natural_key="programme-intake:orphan-result",
            request_digest=digest,
            receipt_id=claim.receipt_id,
            receipt_generation=claim.generation,
            object_ids={"programme_id": programme.id},
            response_json={"programme_id": programme.id, "name": programme.name},
        )
        session.add(persisted)
        session.flush()
        persisted_id = persisted.id
        session.add(
            OperationOutboxEvent(
                organization_id=command_fixture.organization_id,
                operation_result_id=persisted.id,
                event_id=str(uuid.uuid4()),
                ordinal=0,
                event_type="programme.created",
                payload_json={"programme_id": programme.id},
            )
        )
    _wait_for_expiry(claim)

    called = False

    def must_not_run(_session, _claim):
        nonlocal called
        called = True
        raise AssertionError("handler reran despite canonical operation result")

    result = _execute(
        command_fixture,
        key="orphan-result",
        payload=payload,
        handler=must_not_run,
    )

    assert isinstance(result, CommandResult)
    assert result.operation_result_id == persisted_id
    assert result.created is False and result.idempotent is True
    assert called is False
    assert _receipt(command_fixture, "orphan-result").status == "succeeded"
    assert _counts(command_fixture) == (1, 1, 1)


def test_damaged_receipt_reconciles_natural_key_and_exact_response(command_fixture):
    """Catches receipt damage causing a natural-key domain row to be duplicated."""
    first = _execute(command_fixture, key="damaged")
    receipt = _receipt(command_fixture, "damaged")
    with db.engine.begin() as connection:
        connection.exec_driver_sql("SET LOCAL session_replication_role = replica")
        connection.execute(
            text(
                """
                UPDATE command_idempotency_records
                SET status = 'in_progress', operation_result_id = NULL,
                    completed_at = NULL,
                    lease_expires_at = clock_timestamp() - interval '1 second'
                WHERE id = :receipt_id AND organization_id = :organization_id
                """
            ),
            {
                "receipt_id": receipt.id,
                "organization_id": command_fixture.organization_id,
            },
        )

    def must_not_run(_session, _claim):
        raise AssertionError("damaged receipt reran the natural-key mutation")

    replay = _execute(command_fixture, key="damaged", handler=must_not_run)

    assert replay.operation_result_id == first.operation_result_id
    assert replay.object_ids == first.object_ids
    assert replay.response == first.response
    assert replay.created is False and replay.idempotent is True
    assert _counts(command_fixture) == (1, 1, 1)


def test_same_key_changed_digest_conflicts_and_active_lease_has_retry_metadata(
    command_fixture,
):
    """Catches key rebinding and blind retries while another worker owns a lease."""
    payload = {"name": command_fixture.domain_name}
    digest = canonical_request_digest(payload)
    claim = CommandService.claim_or_reconcile(
        actor=command_fixture.actor,
        operation="programme.create",
        idempotency_key="active",
        request_digest=digest,
        natural_key="programme-intake:active",
    )

    with pytest.raises(CommandConflict) as active:
        CommandService.claim_or_reconcile(
            actor=command_fixture.actor,
            operation="programme.create",
            idempotency_key="active",
            request_digest=digest,
            natural_key="programme-intake:active",
        )
    assert active.value.reason == "active_lease"
    assert active.value.retry_after_seconds > 0
    assert active.value.receipt_id == claim.receipt_id
    assert active.value.generation == 1

    with pytest.raises(CommandConflict) as changed:
        CommandService.claim_or_reconcile(
            actor=command_fixture.actor,
            operation="programme.create",
            idempotency_key="active",
            request_digest=canonical_request_digest({"name": "different"}),
            natural_key="programme-intake:active",
        )
    assert changed.value.http_status == 409
    assert changed.value.reason == "idempotency_digest_mismatch"


def test_paused_stale_worker_cannot_write_after_reclaim(command_fixture, app):
    """Catches generation-one work committing after generation two succeeds."""
    payload = {"name": command_fixture.domain_name}
    digest = canonical_request_digest(payload)
    worker_a = CommandService.claim_or_reconcile(
        actor=command_fixture.actor,
        operation="programme.create",
        idempotency_key="race",
        request_digest=digest,
        natural_key="programme-intake:race",
    )
    paused = threading.Barrier(2)
    resume_worker_a = threading.Event()
    outcome = {}

    def stale_worker():
        with app.app_context():
            paused.wait(timeout=3)
            resume_worker_a.wait(timeout=3)
            try:
                CommandService.execute_claim(
                    actor=command_fixture.actor,
                    operation="programme.create",
                    claim=worker_a,
                    handler=_mutation(command_fixture),
                )
            except Exception as error:  # captured for assertion in the test thread
                outcome["error"] = error
            finally:
                db.session.remove()

    thread = threading.Thread(target=stale_worker, daemon=True)
    thread.start()
    paused.wait(timeout=3)
    _wait_for_expiry(worker_a)

    worker_b = _execute(command_fixture, key="race", payload=payload)
    resume_worker_a.set()
    thread.join(timeout=3)

    assert thread.is_alive() is False
    assert worker_b.created is True
    assert isinstance(outcome.get("error"), StaleClaim)
    assert _receipt(command_fixture, "race").lease_generation == 2
    assert _counts(command_fixture) == (1, 1, 1)


def test_supplied_receipt_id_is_still_tenant_and_actor_scoped(command_fixture):
    """Catches a warm/supplied receipt ID bypassing explicit tenant ownership."""
    payload = {"name": command_fixture.domain_name}
    claim = CommandService.claim_or_reconcile(
        actor=command_fixture.actor,
        operation="programme.create",
        idempotency_key="foreign-actor",
        request_digest=canonical_request_digest(payload),
        natural_key="programme-intake:foreign-actor",
    )
    forged = ActorContext(
        user_id=command_fixture.user_id,
        organization_id=command_fixture.organization_id + 1,
        roles=command_fixture.actor.roles,
        request_id="forged-request",
    )

    with pytest.raises(StaleClaim):
        CommandService.execute_claim(
            actor=forged,
            operation="programme.create",
            claim=claim,
            handler=_mutation(command_fixture),
        )
    assert _counts(command_fixture) == (0, 0, 0)
