"""Immutable Transformation Room decision-brief contracts."""

from __future__ import annotations

import threading
import time
from dataclasses import replace

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.transformation_decision import (
    DecisionBrief,
    DecisionBriefEvidenceCitation,
    DecisionBriefOptionCitation,
    DecisionBriefVersion,
    DecisionEvent,
    TransformationOption,
)
from app.models.transformation_evidence import EvidenceClaimHead, EvidenceRecord
from app.models.user import User
from app.modules.transformation_room.decision_service import (
    DecisionBriefService,
    TransformationOptionService,
)
from app.modules.transformation_room.domain import (
    BlockedByEvidence,
    CommandConflict,
    HumanAssertions,
    NotAuthorised,
)

from tests.test_transformation_evidence_service import (
    EvidenceScope,
    _record_inventory,
    evidence_scope,
)
from tests.test_transformation_option_service import DecisionScope, decision_scope


def _freeze_options(scope: DecisionScope):
    return tuple(
        TransformationOptionService.freeze_version(
            actor=scope.actor,
            option_id=option_id,
            expected_revision=1,
            command_key=f"brief-option-{ordinal}",
        ).object_ids["option_version_id"]
        for ordinal, option_id in enumerate(scope.option_ids, start=1)
    )


def _assertions(scope: DecisionScope, *, superseded=()):
    return HumanAssertions(
        reviewed_ai_material=True,
        acknowledged_unknown_codes=("cost_source_unknown",),
        acknowledged_superseded_evidence_ids=tuple(superseded),
        rationale="A human reviewed the cited facts, unknowns and recommendation.",
    )


def _freeze_brief(
    scope: DecisionScope,
    option_version_ids,
    *,
    evidence_ids=None,
    assertions=None,
    key="brief-freeze",
    revision=1,
    actor=None,
):
    return DecisionBriefService.freeze(
        actor=actor or scope.actor,
        brief_id=scope.brief_id,
        option_version_ids=option_version_ids,
        evidence_ids=evidence_ids or (scope.evidence_id,),
        assertions=assertions or _assertions(scope),
        expected_revision=revision,
        command_key=key,
    )


def test_evaluate_and_freeze_pin_exact_current_graph_and_verify_hash(decision_scope):
    """Catches a brief omitting exact options, evidence, outcomes, measures or assertions."""
    scope = decision_scope
    option_version_ids = _freeze_options(scope)
    readiness = DecisionBriefService.evaluate(actor=scope.actor, brief_id=scope.brief_id)
    assert readiness.ready is True
    assert tuple(readiness.option_version_ids) == option_version_ids
    assert tuple(readiness.evidence_ids) == (scope.evidence_id,)

    result = _freeze_brief(scope, option_version_ids)
    with Session(db.engine) as session:
        version = session.get(
            DecisionBriefVersion,
            result.object_ids["decision_brief_version_id"],
        )
        option_citations = session.scalars(
            select(DecisionBriefOptionCitation).where(
                DecisionBriefOptionCitation.organization_id == scope.organization_id,
                DecisionBriefOptionCitation.brief_version_id == version.id,
            )
        ).all()
        evidence_citations = session.scalars(
            select(DecisionBriefEvidenceCitation).where(
                DecisionBriefEvidenceCitation.organization_id == scope.organization_id,
                DecisionBriefEvidenceCitation.brief_version_id == version.id,
            )
        ).all()
        event_row = session.scalar(
            select(DecisionEvent).where(
                DecisionEvent.organization_id == scope.organization_id,
                DecisionEvent.brief_version_id == version.id,
            )
        )
        brief = session.get(DecisionBrief, scope.brief_id)

        assert DecisionBriefService.verify_hash(version) is True
        assert version.version == 1
        assert version.policy_version == "transformation-r1.1"
        assert version.recommendation_option_version_id == option_version_ids[1]
        assert tuple(version.option_version_ids) == option_version_ids
        assert tuple(version.cited_evidence_ids) == (scope.evidence_id,)
        assert tuple(version.outcome_ids) == (scope.outcome_id,)
        assert tuple(version.measure_ids) == (scope.measure_id,)
        assert version.human_reviewed_ai is True
        assert version.unknowns_acknowledged is True
        assert version.blockers_cleared is True
        assert version.frozen_payload["human_assertions"]["rationale"].startswith(
            "A human reviewed"
        )
        assert version.frozen_payload["objective"]
        assert len(version.content_hash) == 64
        assert brief.status == "frozen" and brief.revision == 2
        assert {row.option_version_id for row in option_citations} == set(option_version_ids)
        assert len(evidence_citations) == 1
        assert evidence_citations[0].evidence_record_id == scope.evidence_id
        assert evidence_citations[0].was_current is True
        assert evidence_citations[0].acknowledged is False
        assert event_row.event_type == "brief.version_frozen"
        assert event_row.command_receipt_id is not None

        version.frozen_payload["objective"] = "Altered after load"
        assert DecisionBriefService.verify_hash(version) is False


def test_freeze_rejects_duplicate_ids_client_totals_and_unreviewed_ai(decision_scope):
    """Catches ambiguous citations, client-derived totals or absent human review."""
    scope = decision_scope
    option_version_ids = _freeze_options(scope)
    with pytest.raises(ValueError, match="duplicate option_version_ids"):
        _freeze_brief(
            scope,
            (option_version_ids[0], option_version_ids[0]),
            key="brief-duplicate-options",
        )
    with pytest.raises(ValueError, match="duplicate evidence_ids"):
        _freeze_brief(
            scope,
            option_version_ids,
            evidence_ids=(scope.evidence_id, scope.evidence_id),
            key="brief-duplicate-evidence",
        )
    with pytest.raises(ValueError, match="client totals"):
        DecisionBriefService.build_freeze_request(
            scope.actor,
            scope.brief_id,
            option_version_ids,
            (scope.evidence_id,),
            {
                "reviewed_ai_material": True,
                "acknowledged_unknown_codes": ("cost_source_unknown",),
                "acknowledged_superseded_evidence_ids": (),
                "rationale": "Human rationale",
                "client_totals": {"cost_min": "0"},
            },
            1,
        )
    with pytest.raises(BlockedByEvidence, match="human_ai_review_required"):
        _freeze_brief(
            scope,
            option_version_ids,
            assertions=replace(_assertions(scope), reviewed_ai_material=False),
            key="brief-unreviewed-ai",
        )


def test_single_option_requires_persisted_named_policy_or_legal_exception(decision_scope):
    """Catches a one-option brief with an ephemeral or unnamed exception."""
    scope = decision_scope
    one_version = (
        TransformationOptionService.freeze_version(
            actor=scope.actor,
            option_id=scope.option_ids[0],
            expected_revision=1,
            command_key="single-option-version",
        ).object_ids["option_version_id"],
    )
    with pytest.raises(BlockedByEvidence) as blocked:
        _freeze_brief(scope, one_version, key="single-option-no-exception")
    assert any(
        item.code == "viable_options_required"
        for item in blocked.value.details.get("blockers", ())
    )

    with Session(db.engine) as session, session.begin():
        brief = session.get(DecisionBrief, scope.brief_id)
        brief.option_exception_type = "legal"
        brief.option_exception_name = "Contractual exit restriction"
        brief.option_exception_reason = "The current contract legally prohibits migration."
        brief.option_exception_authority_id = scope.actor_id
        brief.recommendation_option_id = scope.option_ids[0]

    result = _freeze_brief(
        scope, one_version, key="single-option-with-exception", revision=2
    )
    with Session(db.engine) as session:
        version = session.get(
            DecisionBriefVersion,
            result.object_ids["decision_brief_version_id"],
        )
    assert version.frozen_payload["option_exception"] == {
        "authority_id": scope.actor_id,
        "name": "Contractual exit restriction",
        "reason": "The current contract legally prohibits migration.",
        "type": "legal",
    }


def test_superseded_global_head_citation_blocks_without_exact_acknowledgement(
    decision_scope,
):
    """Catches a brief silently citing a stale global evidence leaf."""
    scope = decision_scope
    option_version_ids = _freeze_options(scope)
    with Session(db.engine) as session, session.begin():
        application = session.get(ApplicationComponent, scope.application_id)
        application.application_owner = "Changed canonical owner"
    evidence_scope = EvidenceScope(
        scope.organization_id,
        0,
        scope.actor_id,
        0,
        scope.workstream_id,
        scope.candidate_id,
        scope.application_id,
        0,
        scope.actor,
        scope.actor,
    )
    corrected = _record_inventory(
        evidence_scope,
        expected_revision=1,
        key="brief-evidence-correction",
    )
    corrected_id = corrected.object_ids["evidence_record_id"]

    with pytest.raises(BlockedByEvidence, match="evidence_acknowledgement_required"):
        _freeze_brief(
            scope,
            option_version_ids,
            evidence_ids=(scope.evidence_id,),
            key="brief-stale-unacknowledged",
        )

    result = _freeze_brief(
        scope,
        option_version_ids,
        evidence_ids=(scope.evidence_id,),
        assertions=_assertions(scope, superseded=(scope.evidence_id,)),
        key="brief-stale-acknowledged",
    )
    with Session(db.engine) as session:
        citation = session.scalar(
            select(DecisionBriefEvidenceCitation).where(
                DecisionBriefEvidenceCitation.organization_id == scope.organization_id,
                DecisionBriefEvidenceCitation.brief_version_id
                == result.object_ids["decision_brief_version_id"],
            )
        )
    assert citation.was_current is False and citation.acknowledged is True
    assert citation.current_record_id_at_freeze == corrected_id


def test_replay_reauthorizes_before_returning_persisted_brief_result(decision_scope):
    """Catches Task 3 replay returning a frozen brief after current authority is revoked."""
    scope = decision_scope
    option_version_ids = _freeze_options(scope)
    result = _freeze_brief(scope, option_version_ids, key="brief-replay-authority")
    with Session(db.engine) as session, session.begin():
        user = session.get(User, scope.actor_id)
        user.enterprise_role = "portfolio_manager"

    with pytest.raises(NotAuthorised, match="brief_freeze_not_authorised"):
        _freeze_brief(scope, option_version_ids, key="brief-replay-authority")
    with Session(db.engine) as session:
        assert session.scalar(
            select(func.count())
            .select_from(DecisionBriefVersion)
            .where(DecisionBriefVersion.organization_id == scope.organization_id)
        ) == 1
        assert result.operation_result_id is not None


def test_locked_brief_handler_rechecks_role_revoked_after_command_authorization(
    app, decision_scope
):
    """Catches receipt-time authority being reused after a real committed revocation."""
    scope = decision_scope
    option_version_ids = _freeze_options(scope)
    engine = db.engine
    handler_has_brief_lock = threading.Event()
    release_handler = threading.Event()
    errors = []

    def pause_handler(_conn, _cursor, statement, _params, _context, _many):
        if (
            threading.current_thread().name == "brief-authority-worker"
            and statement.lstrip().upper().startswith("SELECT")
            and "decision_briefs" in statement.lower()
            and "for update" in statement.lower()
        ):
            handler_has_brief_lock.set()
            if not release_handler.wait(timeout=10):
                raise TimeoutError("brief authority pause was not released")

    def freeze():
        with app.app_context():
            try:
                _freeze_brief(
                    scope,
                    option_version_ids,
                    key="brief-authority-race",
                    actor=replace(scope.actor, request_id="brief-authority-race"),
                )
            except Exception as error:  # asserted after worker finishes
                errors.append(error)
            finally:
                db.session.remove()

    event.listen(engine, "after_cursor_execute", pause_handler)
    worker = threading.Thread(
        target=freeze,
        name="brief-authority-worker",
        daemon=True,
    )
    try:
        worker.start()
        assert handler_has_brief_lock.wait(timeout=10)
        with Session(engine) as session, session.begin():
            user = session.get(User, scope.actor_id)
            user.enterprise_role = "portfolio_manager"
    finally:
        release_handler.set()
        worker.join(timeout=10)
        event.remove(engine, "after_cursor_execute", pause_handler)

    assert worker.is_alive() is False
    assert len(errors) == 1 and isinstance(errors[0], NotAuthorised)
    assert errors[0].reason == "brief_freeze_not_authorised"
    with Session(engine) as session:
        assert session.scalar(
            select(func.count())
            .select_from(DecisionBriefVersion)
            .where(DecisionBriefVersion.organization_id == scope.organization_id)
        ) == 0
        assert session.scalar(
            select(func.count())
            .select_from(DecisionEvent)
            .where(DecisionEvent.organization_id == scope.organization_id)
        ) == 0


def test_concurrent_same_revision_brief_freeze_serializes_one_snapshot(app, decision_scope):
    """Catches two immutable brief versions escaping one logical draft revision."""
    scope = decision_scope
    option_version_ids = _freeze_options(scope)
    engine = db.engine
    first_has_lock = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()
    results = []
    errors = []

    def pause_first(_conn, _cursor, statement, _params, _context, _many):
        if (
            threading.current_thread().name == "brief-version-first"
            and statement.lstrip().upper().startswith("SELECT")
            and "decision_briefs" in statement.lower()
            and "for update" in statement.lower()
        ):
            first_has_lock.set()
            if not release_first.wait(timeout=10):
                raise TimeoutError("brief version race pause was not released")

    def freeze(key, entered=None):
        with app.app_context():
            if entered is not None:
                entered.set()
            try:
                results.append(
                    _freeze_brief(
                        scope,
                        option_version_ids,
                        key=key,
                        actor=replace(scope.actor, request_id=key),
                    )
                )
            except Exception as error:  # asserted after workers finish
                errors.append(error)
            finally:
                db.session.remove()

    event.listen(engine, "after_cursor_execute", pause_first)
    first = threading.Thread(
        target=freeze,
        args=("brief-race-first",),
        name="brief-version-first",
        daemon=True,
    )
    second = threading.Thread(
        target=freeze,
        args=("brief-race-second", second_entered),
        name="brief-version-second",
        daemon=True,
    )
    try:
        first.start()
        assert first_has_lock.wait(timeout=10)
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
    assert errors[0].reason == "stale_revision"
    with Session(engine) as session:
        assert session.scalar(
            select(func.count())
            .select_from(DecisionBriefVersion)
            .where(DecisionBriefVersion.organization_id == scope.organization_id)
        ) == 1
        assert session.scalar(
            select(func.count())
            .select_from(DecisionEvent)
            .where(DecisionEvent.organization_id == scope.organization_id)
        ) == 1
        brief = session.get(DecisionBrief, scope.brief_id)
    assert brief.revision == 2
