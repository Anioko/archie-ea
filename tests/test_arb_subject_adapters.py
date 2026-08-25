"""Behavior contracts for typed ARB subject adapters."""

from __future__ import annotations

import json
import uuid

import pytest

from app import db
from app.models.adr import ArchitectureDecisionRecord
from app.models.arb_submission_evidence import ARBSubmissionEvidenceSnapshot
from app.models.models import ArchitectureModel
from app.models.solution_models import Solution
from app.models.transformation_decision import (
    ARBSubjectEvidenceSnapshot,
)
from app.models.user import User
from app.modules.solutions_strategic.v2.services.arb_submission_service import (
    ARBReadinessResult,
)
from app.modules.transformation_room.domain import (
    ActorContext,
    BlockedByEvidence,
    BriefReadiness,
    CommandConflict,
    GateBlocker,
    GateResult,
    GovernedSubject,
    NotFound,
)
from app.modules.transformation_room.arb_adapters import (
    ADRARBAdapter,
    ArchitectureModelARBAdapter,
    DecisionBriefARBAdapter,
    SolutionARBAdapter,
    decision_brief_arb_readiness,
    get_arb_subject_adapter,
)
from tests.test_decision_brief_service import (
    _assertions as _brief_assertions,
    _freeze_brief,
    _freeze_options,
)
from tests.test_transformation_evidence_service import evidence_scope  # noqa: F401
from tests.test_transformation_option_service import decision_scope  # noqa: F401


def _actor(user, org) -> ActorContext:
    return ActorContext(
        user_id=user.id,
        organization_id=org.id,
        roles=frozenset({"enterprise_architect"}),
        request_id=f"arb-adapter-{uuid.uuid4().hex}",
    )


def _user(session, org):
    suffix = uuid.uuid4().hex[:10]
    row = User(
        email=f"adapter-{suffix}@example.test",
        first_name="Adapter",
        last_name="Tester",
        enterprise_role="enterprise_architect",
        organization_id=org.id,
    )
    session.add(row)
    session.flush()
    return row


def _gate(*, allowed=True, blockers=()):
    return GateResult(
        allowed=allowed,
        current_stage="options",
        target_stage="decision_ready",
        policy_version="transformation-room-gates-r1",
        blockers=tuple(blockers),
        warnings=(),
        evidence_ids=(31, 37),
    )


def test_registry_exposes_exact_supported_adapters_and_fails_closed():
    assert isinstance(get_arb_subject_adapter("decision_brief"), DecisionBriefARBAdapter)
    assert isinstance(get_arb_subject_adapter("solution"), SolutionARBAdapter)
    assert isinstance(
        get_arb_subject_adapter("architecture_model"), ArchitectureModelARBAdapter
    )
    assert isinstance(get_arb_subject_adapter("adr"), ADRARBAdapter)

    with pytest.raises(NotFound) as unsupported:
        get_arb_subject_adapter("application")
    with pytest.raises(NotFound) as malformed:
        get_arb_subject_adapter("")

    assert unsupported.value.reason == malformed.value.reason == "arb_subject_not_found"


def test_decision_brief_readiness_uses_server_gate_and_explicit_human_review_only():
    ready = BriefReadiness(True, _gate(), (7, 9), (31, 37))

    result = decision_brief_arb_readiness(
        ready,
        {"human_reviewed": True, "ready": True, "reason_codes": []},
    )
    incomplete = decision_brief_arb_readiness(ready, {"ready": True})

    assert result == ARBReadinessResult(
        ready=True,
        checks={
            "human_reviewed": True,
            "gate_policy_version": "transformation-room-gates-r1",
            "option_version_ids": [7, 9],
            "evidence_ids": [31, 37],
        },
        governance_result={
            "allowed": True,
            "current_stage": "options",
            "target_stage": "decision_ready",
            "policy_version": "transformation-room-gates-r1",
            "blockers": [],
            "warnings": [],
            "evidence_ids": [31, 37],
        },
    )
    assert incomplete.ready is False
    assert incomplete.reason_codes == ["human_review_required"]


def test_decision_brief_readiness_preserves_server_blockers_despite_client_ready():
    blocker = GateBlocker(
        code="current_evidence_required",
        message="Current evidence is required",
        resource_type="evidence_request",
        resource_id=44,
        action_url="/solutions/programmes/3/workstreams/5/evidence",
    )
    blocked = BriefReadiness(False, _gate(allowed=False, blockers=(blocker,)), (), ())

    result = decision_brief_arb_readiness(
        blocked,
        {"human_reviewed": True, "ready": True},
    )

    assert result.ready is False
    assert result.reason_codes == ["current_evidence_required"]
    assert result.missing_evidence == [
        {
            "code": "current_evidence_required",
            "message": "Current evidence is required",
            "resource_type": "evidence_request",
            "resource_id": 44,
            "action_url": "/solutions/programmes/3/workstreams/5/evidence",
        }
    ]


@pytest.mark.parametrize(
    ("adapter", "wrong_type"),
    (
        (DecisionBriefARBAdapter(), "solution"),
        (SolutionARBAdapter(), "adr"),
        (ArchitectureModelARBAdapter(), "decision_brief"),
        (ADRARBAdapter(), "architecture_model"),
    ),
)
def test_adapter_operations_reject_mismatched_governed_subject(adapter, wrong_type):
    subject = GovernedSubject(wrong_type, 11, 13, "Wrong", None)
    actor = ActorContext(17, 13, frozenset(), "mismatch")
    readiness = ARBReadinessResult(ready=True)

    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.evaluate(actor, subject, {"human_reviewed": True})
    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.snapshot(actor, subject, readiness)
    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.canonical_url(subject)


def test_model_adapter_load_evaluate_snapshot_and_url_are_tenant_bound(
    db_session, make_org
):
    org, foreign_org = make_org("model-adapter"), make_org("model-adapter-foreign")
    actor_user, foreign_user = _user(db_session, org), _user(db_session, foreign_org)
    model = ArchitectureModel(
        organization_id=org.id,
        name="Payments target architecture",
        version="2.1",
        user_id=actor_user.id,
        model_data=json.dumps({"elements": ["Payment API"], "relationships": []}),
        is_default=False,
    )
    db_session.add(model)
    db_session.flush()
    adapter = ArchitectureModelARBAdapter()

    subject = adapter.load(_actor(actor_user, org), model.id)
    readiness = adapter.evaluate(
        _actor(actor_user, org), subject, {"human_reviewed": True, "ready": False}
    )
    evidence = adapter.snapshot(_actor(actor_user, org), subject, readiness)
    snapshot = db_session.get(ARBSubjectEvidenceSnapshot, evidence.evidence_id)

    assert subject == GovernedSubject(
        "architecture_model", model.id, org.id, model.name, None
    )
    assert readiness.ready is True
    assert adapter.canonical_url(subject) == "/architecture/models"
    assert evidence.evidence_type == "arb_subject_evidence_snapshot"
    assert evidence.content_hash == snapshot.content_hash == snapshot.recompute_content_hash()
    assert snapshot.subject_type == "architecture_model"
    assert snapshot.subject_id == snapshot.architecture_model_id == model.id
    assert snapshot.policy_version == "architecture-model-arb-r1"
    assert snapshot.captured_by_id == actor_user.id
    assert snapshot.payload == {
        "id": model.id,
        "organization_id": org.id,
        "name": "Payments target architecture",
        "version": "2.1",
        "user_id": actor_user.id,
        "model_data": json.dumps({"elements": ["Payment API"], "relationships": []}),
        "is_default": False,
        "solution_id": None,
        "technology_stack_id": None,
        "compliance_framework_id": None,
    }
    assert snapshot.citations == [
        {"resource_type": "architecture_model", "resource_id": model.id}
    ]

    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(_actor(foreign_user, foreign_org), model.id)
    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(_actor(foreign_user, org), model.id)


def test_adr_adapter_load_evaluate_snapshot_and_url_are_tenant_bound(
    db_session, make_org
):
    org, foreign_org = make_org("adr-adapter"), make_org("adr-adapter-foreign")
    actor_user, foreign_user = _user(db_session, org), _user(db_session, foreign_org)
    adr = ArchitectureDecisionRecord(
        organization_id=org.id,
        adr_number=42,
        title="Adopt event-driven integration",
        status="proposed",
        context="Services need reliable asynchronous integration.",
        decision="Use durable domain events through the enterprise broker.",
        rationale="This isolates producers and consumers while preserving delivery.",
        consequences="Teams must own event schemas and compatibility.",
        alternatives_considered="[\"point-to-point APIs\"]",
        risks="[\"schema drift\"]",
        created_by=actor_user.email,
    )
    db_session.add(adr)
    db_session.flush()
    adapter = ADRARBAdapter()

    subject = adapter.load(_actor(actor_user, org), adr.id)
    readiness = adapter.evaluate(_actor(actor_user, org), subject, {"human_reviewed": True})
    evidence = adapter.snapshot(_actor(actor_user, org), subject, readiness)
    snapshot = db_session.get(ARBSubjectEvidenceSnapshot, evidence.evidence_id)

    assert subject == GovernedSubject("adr", adr.id, org.id, adr.title, None)
    assert readiness.ready is True
    assert adapter.canonical_url(subject) == f"/architecture/adrs/{adr.id}"
    assert evidence.content_hash == snapshot.content_hash == snapshot.recompute_content_hash()
    assert snapshot.subject_type == "adr"
    assert snapshot.subject_id == snapshot.adr_id == adr.id
    assert snapshot.policy_version == "adr-arb-r1"
    assert snapshot.payload["adr_number"] == 42
    assert snapshot.payload["context"] == adr.context
    assert snapshot.payload["decision"] == adr.decision
    assert snapshot.payload["rationale"] == adr.rationale
    assert snapshot.payload["consequences"] == adr.consequences
    assert snapshot.payload["created_at"] == adr.created_at.isoformat()
    assert snapshot.citations == [{"resource_type": "adr", "resource_id": adr.id}]

    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(_actor(foreign_user, foreign_org), adr.id)
    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(_actor(foreign_user, org), adr.id)


@pytest.mark.parametrize(
    ("adapter", "row_factory", "expected_code"),
    (
        (
            ArchitectureModelARBAdapter(),
            lambda org, user: ArchitectureModel(
                organization_id=org.id,
                name="Incomplete model",
                version=None,
                user_id=user.id,
                model_data=None,
            ),
            "architecture_model_version_required",
        ),
        (
            ADRARBAdapter(),
            lambda org, user: ArchitectureDecisionRecord(
                organization_id=org.id,
                adr_number=7,
                title="Incomplete ADR",
                status="proposed",
                context="Context",
                decision="Decision",
                rationale="Rationale",
                consequences="",
            ),
            "adr_consequences_required",
        ),
    ),
)
def test_model_and_adr_policies_block_incomplete_evidence(
    db_session, make_org, adapter, row_factory, expected_code
):
    org = make_org("incomplete-adapter")
    actor_user = _user(db_session, org)
    row = row_factory(org, actor_user)
    db_session.add(row)
    db_session.flush()
    actor = _actor(actor_user, org)
    subject = adapter.load(actor, row.id)

    readiness = adapter.evaluate(actor, subject, {"human_reviewed": True})

    assert readiness.ready is False
    assert expected_code in readiness.reason_codes
    with pytest.raises(BlockedByEvidence, match="arb_subject_not_ready"):
        adapter.snapshot(actor, subject, readiness)


def test_solution_adapter_preserves_existing_evaluator_and_snapshot_shape(
    db_session, make_org, tenant_ctx, monkeypatch
):
    org, foreign_org = make_org("solution-adapter"), make_org("solution-adapter-foreign")
    actor_user = _user(db_session, org)
    foreign_user = _user(db_session, foreign_org)
    solution = Solution(
        organization_id=org.id,
        name="Governed payments solution",
        description="A governed solution",
        created_by_id=actor_user.id,
        governance_status="draft",
    )
    db_session.add(solution)
    db_session.flush()
    assertions = {
        "human_reviewed": True,
        "direct_route_evidence": {
            name: {"passed": True, "evidence": f"{name} checked"}
            for name in (
                "design_reviewed",
                "security_impact_reviewed",
                "data_impact_reviewed",
            )
        },
    }
    monkeypatch.setattr(
        "app.modules.solutions_strategic.v2.services.arb_submission_service.check_gate",
        lambda _solution_id, gate_name: {
            "passed": True,
            "failures": [],
            "gate_name": gate_name,
        },
    )
    actor = _actor(actor_user, org)
    adapter = SolutionARBAdapter()

    with tenant_ctx(org.id):
        subject = adapter.load(actor, solution.id)
        readiness = adapter.evaluate(actor, subject, assertions)
        evidence = adapter.snapshot(actor, subject, readiness)

    snapshot = db_session.get(ARBSubmissionEvidenceSnapshot, evidence.evidence_id)
    assert subject == GovernedSubject("solution", solution.id, org.id, solution.name, None)
    assert readiness.ready is True
    assert evidence.evidence_type == "solution_evidence_snapshot"
    assert evidence.content_hash == snapshot.content_hash == snapshot.recompute_content_hash()
    assert snapshot.solution_id == solution.id
    assert snapshot.actor_id == actor_user.id
    assert snapshot.request_assertions == assertions
    assert adapter.canonical_url(subject) == f"/solutions/{solution.id}?tab=governance"
    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(_actor(foreign_user, foreign_org), solution.id)
    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(_actor(foreign_user, org), solution.id)


def test_decision_brief_adapter_load_evaluate_snapshot_url_and_hash_tamper(
    decision_scope, monkeypatch
):
    option_version_ids = _freeze_options(decision_scope)
    frozen = _freeze_brief(
        decision_scope,
        option_version_ids,
        assertions=_brief_assertions(decision_scope),
        key=f"adapter-freeze-{uuid.uuid4().hex}",
    )
    adapter = DecisionBriefARBAdapter()
    subject = adapter.load(decision_scope.actor, decision_scope.brief_id)
    readiness = adapter.evaluate(
        decision_scope.actor, subject, {"human_reviewed": True, "ready": False}
    )
    evidence = adapter.snapshot(decision_scope.actor, subject, readiness)

    from app.models.transformation_programme import ProgrammeWorkstream
    from app.modules.transformation_room.decision_service import DecisionBriefService

    workstream = db.session.get(ProgrammeWorkstream, decision_scope.workstream_id)
    assert subject.logical_version_id == frozen.object_ids["decision_brief_version_id"]
    assert readiness.ready is True
    assert evidence.evidence_type == "decision_brief_version"
    assert evidence.evidence_id == frozen.object_ids["decision_brief_version_id"]
    assert evidence.content_hash == frozen.response["content_hash"]
    assert adapter.canonical_url(subject) == (
        f"/solutions/programmes/{workstream.programme_id}/workstreams/"
        f"{workstream.id}/decision"
    )
    foreign_actor = ActorContext(
        user_id=decision_scope.actor.user_id,
        organization_id=decision_scope.organization_id + 1_000_000,
        roles=decision_scope.actor.roles,
        request_id="foreign-decision-brief",
    )
    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(foreign_actor, decision_scope.brief_id)
    non_member = ActorContext(
        user_id=decision_scope.actor.user_id + 1_000_000,
        organization_id=decision_scope.organization_id,
        roles=decision_scope.actor.roles,
        request_id="non-member-decision-brief",
    )
    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(non_member, decision_scope.brief_id)

    version = DecisionBriefService.require_version_for_tenant(
        decision_scope.actor, subject.logical_version_id
    )
    version.frozen_payload = {**version.frozen_payload, "title": "Tampered brief"}
    monkeypatch.setattr(
        DecisionBriefService,
        "require_version_for_tenant",
        classmethod(lambda _cls, _actor, _version_id: version),
    )

    with pytest.raises(CommandConflict, match="decision_brief_hash_mismatch"):
        adapter.snapshot(decision_scope.actor, subject, readiness)
