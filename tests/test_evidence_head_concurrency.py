"""Real PostgreSQL evidence-head compare-and-swap races."""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.transformation_evidence import EvidenceClaimHead, EvidenceHeadEvent, EvidenceRecord
from app.models.transformation_execution import CommandIdempotencyRecord
from app.models.user import User
from app.modules.transformation_room.domain import CommandConflict, TypedEvidenceValue
from app.modules.transformation_room.evidence_service import TransformationEvidenceService

from tests.test_transformation_evidence_service import (
    EvidenceScope,
    _grant_decision_authority,
    _record_inventory,
    evidence_scope,
)


@pytest.mark.parametrize("starting_revision", [0, 1])
def test_concurrent_root_or_correction_creates_one_record_head_move_and_event(
    app, evidence_scope: EvidenceScope, starting_revision
):
    """Catches duplicate roots or an orphan loser after same-revision corrections."""
    scope = evidence_scope
    if starting_revision:
        TransformationEvidenceService.record_observation(
            actor=scope.actor,
            candidate_id=scope.candidate_id,
            claim_key="race_claim",
            adapter_key="application-inventory",
            source_key=str(scope.application_id),
            expected_head_revision=0,
            command_key="race-seed",
        )
        with Session(db.engine) as session, session.begin():
            application = session.get(ApplicationComponent, scope.application_id)
            application.application_owner = "Corrected owner"

    engine = db.engine
    first_has_head_lock = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    results = []
    errors = []

    def pause_first(_connection, _cursor, statement, _parameters, _context, _executemany):
        if (
            threading.current_thread().name == "evidence-race-first"
            and statement.lstrip().upper().startswith("SELECT")
            and "evidence_claim_heads" in statement.lower()
            and "for update" in statement.lower()
        ):
            first_has_head_lock.set()
            if not release_first.wait(timeout=10):
                raise TimeoutError("evidence head race pause was not released")

    def write(command_key, entered=None):
        with app.app_context():
            if entered is not None:
                entered.set()
            try:
                results.append(
                    TransformationEvidenceService.record_observation(
                        actor=scope.actor,
                        candidate_id=scope.candidate_id,
                        claim_key="race_claim",
                        adapter_key="application-inventory",
                        source_key=str(scope.application_id),
                        expected_head_revision=starting_revision,
                        command_key=command_key,
                    )
                )
            except Exception as error:  # asserted after workers finish
                errors.append(error)
            finally:
                db.session.remove()

    event.listen(engine, "after_cursor_execute", pause_first)
    first = threading.Thread(
        target=write, args=("race-first",), name="evidence-race-first", daemon=True
    )
    second = threading.Thread(
        target=write,
        args=("race-second", second_entered),
        name="evidence-race-second",
        daemon=True,
    )
    try:
        first.start()
        assert first_has_head_lock.wait(timeout=10)
        second.start()
        assert second_entered.wait(timeout=5)
        time.sleep(0.2)
        assert second.is_alive() is True
    finally:
        release_first.set()
        first.join(timeout=10)
        second.join(timeout=10)
        event.remove(engine, "after_cursor_execute", pause_first)

    assert first.is_alive() is False and second.is_alive() is False
    assert len(results) == 1
    assert len(errors) == 1 and isinstance(errors[0], CommandConflict)
    assert errors[0].reason == "stale_head_revision"
    with Session(engine) as session:
        head = session.scalar(
            select(EvidenceClaimHead).where(
                EvidenceClaimHead.organization_id == scope.organization_id,
                EvidenceClaimHead.claim_key == "race_claim",
                EvidenceClaimHead.source_identity == f"application:{scope.application_id}",
            )
        )
        record_count = session.scalar(
            select(func.count())
            .select_from(EvidenceRecord)
            .where(
                EvidenceRecord.organization_id == scope.organization_id,
                EvidenceRecord.claim_key == "race_claim",
            )
        )
        event_count = session.scalar(
            select(func.count())
            .select_from(EvidenceHeadEvent)
            .where(
                EvidenceHeadEvent.organization_id == scope.organization_id,
                EvidenceHeadEvent.head_id == head.id,
            )
        )
    assert head.revision == starting_revision + 1
    assert record_count == starting_revision + 1
    assert event_count == starting_revision + 1


@pytest.mark.parametrize("first_operation", ["resolution", "advancement"])
def test_conflict_resolution_serializes_with_governing_source_advance(
    app, evidence_scope: EvidenceScope, first_operation
):
    """Catches a resolution committing after its selected source leaf was superseded."""
    scope = evidence_scope
    observed = _record_inventory(scope, key=f"race-governing-root-{first_operation}")
    submitted = TransformationEvidenceService.submit_attestation(
        actor=scope.actor,
        request_id=scope.request_id,
        value=TypedEvidenceValue("string", "Disputed owner", None, None),
        expected_head_revision=0,
        command_key=f"race-governing-attestation-{first_operation}",
    )
    conflict_id = submitted.object_ids["conflict_evidence_id"]
    _grant_decision_authority(scope)
    source_identity = f"application:{scope.application_id}"
    source_digest = hashlib.sha256(source_identity.encode("utf-8")).hexdigest()
    claim_token = uuid.uuid4().hex + uuid.uuid4().hex
    with Session(db.engine) as session, session.begin():
        source_actor_id = session.execute(
            User.__table__.insert()
            .values(
                organization_id=scope.organization_id,
                email=f"governing-race-{uuid.uuid4().hex}@example.test",
                confirmed=True,
                enterprise_role="portfolio_manager",
            )
            .returning(User.id)
        ).scalar_one()
        receipt = CommandIdempotencyRecord(
            organization_id=scope.organization_id,
            actor_id=source_actor_id,
            operation="evidence.observe",
            idempotency_key=f"governing-race-direct-advance-{first_operation}",
            request_digest="a" * 64,
            natural_key=(
                f"evidence:{scope.candidate_id}:application_owner:{source_digest}:2"
            ),
            status="in_progress",
            lease_generation=1,
            claim_token=claim_token,
            claimant_request_id=f"governing-race-{first_operation}",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            attempt_count=1,
        )
        session.add(receipt)
        session.flush()
        correction_receipt_id = receipt.id
        root = session.get(EvidenceRecord, observed.object_ids["evidence_record_id"])
        values = {
            column.name: getattr(root, column.name)
            for column in EvidenceRecord.__table__.columns
            if column.name not in {"id", "created_at"}
        }
        values.update(
            supersedes_id=root.id,
            created_by_id=source_actor_id,
            source_version=f"governing-race-correction-{first_operation}",
            collected_at=datetime.now(timezone.utc),
            observed_at=datetime.now(timezone.utc),
        )
        correction = EvidenceRecord(**values)
        session.add(correction)
        session.flush()
        correction_record_id = correction.id

    engine = db.engine
    first_has_lock = threading.Event()
    release_first = threading.Event()
    second_attempting_lock = threading.Event()
    second_done = threading.Event()
    results = {}
    errors = {}
    completion_order = []

    def is_head_lock(statement):
        lowered = statement.lower()
        return (
            statement.lstrip().upper().startswith("SELECT")
            and "evidence_claim_heads" in lowered
            and "for update" in lowered
        )

    def is_direct_source_advance(context):
        return context.execution_options.get("evidence_test_source_advance", False)

    def pause_first(_connection, _cursor, statement, _parameters, context, _executemany):
        if threading.current_thread().name != "governing-race-first":
            return
        if first_operation == "resolution":
            is_target = context.execution_options.get(
                "evidence_conflict_resolution_head_lock", False
            )
        else:
            is_target = is_direct_source_advance(context)
        if is_target:
            first_has_lock.set()
            if not release_first.wait(timeout=10):
                raise TimeoutError("governing evidence race pause was not released")

    def mark_second_attempt(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ):
        if threading.current_thread().name == "governing-race-second" and (
            is_head_lock(statement) or is_direct_source_advance(_context)
        ):
            second_attempting_lock.set()

    def advance_source_directly():
        with Session(engine) as session, session.begin():
            revision = session.scalar(
                text(
                    "SELECT public.archie_advance_evidence_head("
                    ":head_id, :record_id, 1, :actor_id, :receipt_id, 1, :token)"
                ).execution_options(evidence_test_source_advance=True),
                {
                    "head_id": observed.object_ids["evidence_head_id"],
                    "record_id": correction_record_id,
                    "actor_id": source_actor_id,
                    "receipt_id": correction_receipt_id,
                    "token": claim_token,
                },
            )
            return {
                "evidence_record_id": correction_record_id,
                "head_revision": revision,
            }

    def perform(operation, *, first):
        with app.app_context():
            try:
                if operation == "resolution":
                    results[operation] = TransformationEvidenceService.resolve_conflict(
                        actor=scope.actor,
                        conflict_evidence_id=conflict_id,
                        governing_evidence_id=observed.object_ids["evidence_record_id"],
                        rationale="Select only the source leaf current under lock.",
                        command_key=f"governing-race-resolution-{first_operation}",
                    )
                else:
                    results[operation] = advance_source_directly()
                completion_order.append(operation)
            except Exception as error:  # asserted after both workers finish
                errors[operation] = error
                completion_order.append(f"{operation}_error")
            finally:
                if not first:
                    second_done.set()
                db.session.remove()

    second_operation = "advancement" if first_operation == "resolution" else "resolution"
    event.listen(engine, "after_cursor_execute", pause_first)
    event.listen(engine, "before_cursor_execute", mark_second_attempt)
    first = threading.Thread(
        target=perform,
        kwargs={"operation": first_operation, "first": True},
        name="governing-race-first",
        daemon=True,
    )
    second = threading.Thread(
        target=perform,
        kwargs={"operation": second_operation, "first": False},
        name="governing-race-second",
        daemon=True,
    )
    try:
        first.start()
        assert first_has_lock.wait(timeout=10)
        second.start()
        assert second_attempting_lock.wait(timeout=10), repr(errors)
        assert second_done.wait(timeout=0.2) is False, repr(errors)
    finally:
        release_first.set()
        first.join(timeout=10)
        second.join(timeout=10)
        event.remove(engine, "before_cursor_execute", mark_second_attempt)
        event.remove(engine, "after_cursor_execute", pause_first)

    assert first.is_alive() is False and second.is_alive() is False
    with Session(engine) as session:
        source_head = session.scalar(
            select(EvidenceClaimHead).where(
                EvidenceClaimHead.organization_id == scope.organization_id,
                EvidenceClaimHead.subject_type == "application",
                EvidenceClaimHead.subject_id == scope.application_id,
                EvidenceClaimHead.claim_key == "application_owner",
                EvidenceClaimHead.source_identity
                == f"application:{scope.application_id}",
            )
        )
        resolutions = session.scalars(
            select(EvidenceRecord).where(
                EvidenceRecord.organization_id == scope.organization_id,
                EvidenceRecord.source_identity == f"resolution:conflict:{conflict_id}",
            )
        ).all()

    assert source_head.revision == 2
    assert source_head.current_record_id != observed.object_ids["evidence_record_id"]
    if first_operation == "resolution":
        assert errors == {}
        assert completion_order == ["resolution", "advancement"]
        assert len(resolutions) == 1
        assert resolutions[0].value_json["governing_evidence_id"] == (
            observed.object_ids["evidence_record_id"]
        )
    else:
        assert set(results) == {"advancement"}
        assert isinstance(errors.get("resolution"), CommandConflict)
        assert errors["resolution"].reason == "governing_evidence_not_current"
        assert completion_order == ["advancement", "resolution_error"]
        assert resolutions == []
