"""Real PostgreSQL evidence-head compare-and-swap races."""

from __future__ import annotations

import threading
import time

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.transformation_evidence import EvidenceClaimHead, EvidenceHeadEvent, EvidenceRecord
from app.modules.transformation_room.domain import CommandConflict
from app.modules.transformation_room.evidence_service import TransformationEvidenceService

from tests.test_transformation_evidence_service import EvidenceScope, evidence_scope


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
