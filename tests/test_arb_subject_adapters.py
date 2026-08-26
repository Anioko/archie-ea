"""Behavior contracts for typed ARB subject adapters."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.models.adr import ArchitectureDecisionRecord
from app.models.architecture_review_board import ARBGovernanceStandard, ARBReviewItem
from app.models.arb_submission_evidence import (
    ARBSubmissionEvidenceSnapshot,
    WorkbenchArtifactEvidence,
)
from app.models.audit_log import AuditLog
from app.models.models import ArchitectureModel
from app.models.solution_models import Solution
from app.models.solution_governance import SolutionNotification
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
from tests.test_transformation_evidence_service import (  # noqa: F401
    _record_named_source,
    evidence_scope,
)
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


def _mandatory_standard_entries(review_type, evidence_ids):
    rows = db.session.execute(
        db.select(ARBGovernanceStandard).where(
            ARBGovernanceStandard.status == "active",
            ARBGovernanceStandard.mandatory.is_(True),
        )
    ).scalars()
    entries = []
    for row in rows:
        applies = row.applies_to_review_types
        if not applies or review_type in applies:
            entries.append(
                {
                    "standard_id": row.id,
                    "standard_code": row.code,
                    "satisfied": True,
                    "evidence_ids": list(evidence_ids),
                }
            )
    return entries


def _server_evidence(org, label):
    """Persist a real, server-held, hash-bearing evidence row to cite."""
    row = WorkbenchArtifactEvidence.capture(
        organization_id=org.id,
        workspace_id=None,
        solution_id=None,
        name=f"arb-{label}-{uuid.uuid4().hex[:8]}"[:80],
        state="approved",
        payload={"label": label},
        actor_id=None,
    )
    db.session.flush()
    return row


def _governance_dossier(org, policy_version, review_type, *, label="doc", expires_at=None):
    expires_at = expires_at or datetime.now(timezone.utc) + timedelta(days=1)
    record = _server_evidence(org, label)
    return {
        "policy_version": policy_version,
        "standards": _mandatory_standard_entries(review_type, [record.id]),
        "evidence": [
            {
                "evidence_id": record.id,
                "evidence_type": "workbench_artifact_evidence",
                "content_hash": record.content_hash,
                "captured_at": "2026-08-24T09:30:00+00:00",
                "expires_at": expires_at.isoformat(),
            }
        ],
    }


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
    model_document = {
        "elements": ["Payment API"],
        "relationships": [],
        "arb_readiness": _governance_dossier(
            org, "architecture-model-arb-r2", "technology_selection"
        ),
    }
    model = ArchitectureModel(
        organization_id=org.id,
        name="Payments target architecture",
        version="2.1",
        user_id=actor_user.id,
        model_data=json.dumps(model_document),
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
    assert snapshot.policy_version == "architecture-model-arb-r2"
    assert snapshot.captured_by_id == actor_user.id
    assert snapshot.payload["subject"] == {
        "id": model.id,
        "organization_id": org.id,
        "name": "Payments target architecture",
        "version": "2.1",
        "user_id": actor_user.id,
        "model_data": json.dumps(model_document),
        "is_default": False,
        "solution_id": None,
        "technology_stack_id": None,
        "compliance_framework_id": None,
    }
    cited = model_document["arb_readiness"]["evidence"][0]
    assert snapshot.payload["readiness"]["evidence_ids"] == [cited["evidence_id"]]
    assert snapshot.citations == [
        {"resource_type": "architecture_model", "resource_id": model.id},
        {
            "resource_type": "workbench_artifact_evidence",
            "resource_id": cited["evidence_id"],
            "content_hash": cited["content_hash"],
            "captured_at": "2026-08-24T09:30:00+00:00",
            "expires_at": cited["expires_at"],
            "verified": True,
        },
    ]
    assert sorted(
        snapshot.payload["governance_result"]["mandatory_standards"],
        key=lambda entry: entry["standard_id"],
    ) == sorted(
        (
            {
                "standard_id": entry["standard_id"],
                "standard_code": entry["standard_code"],
                "satisfied": True,
                "verified_evidence_ids": [cited["evidence_id"]],
            }
            for entry in model_document["arb_readiness"]["standards"]
        ),
        key=lambda entry: entry["standard_id"],
    )

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
        governance_blob={
            "arb_readiness": _governance_dossier(
                org, "adr-arb-r2", "architecture_change", label="adr"
            )
        },
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
    assert adapter.canonical_url(subject) == f"/architecture/adrs/records/{adr.id}"
    assert evidence.content_hash == snapshot.content_hash == snapshot.recompute_content_hash()
    assert snapshot.subject_type == "adr"
    assert snapshot.subject_id == snapshot.adr_id == adr.id
    assert snapshot.policy_version == "adr-arb-r2"
    assert snapshot.payload["subject"]["adr_number"] == 42
    assert snapshot.payload["subject"]["context"] == adr.context
    assert snapshot.payload["subject"]["decision"] == adr.decision
    assert snapshot.payload["subject"]["rationale"] == adr.rationale
    assert snapshot.payload["subject"]["consequences"] == adr.consequences
    assert snapshot.payload["subject"]["created_at"] == adr.created_at.isoformat()
    adr_cited = adr.governance_blob["arb_readiness"]["evidence"][0]
    assert snapshot.payload["readiness"]["evidence_ids"] == [adr_cited["evidence_id"]]
    assert snapshot.citations[0] == {"resource_type": "adr", "resource_id": adr.id}
    assert snapshot.citations[1]["resource_id"] == adr_cited["evidence_id"]
    assert snapshot.citations[1]["verified"] is True

    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(_actor(foreign_user, foreign_org), adr.id)
    with pytest.raises(NotFound, match="arb_subject_not_found"):
        adapter.load(_actor(foreign_user, org), adr.id)


def test_adr_record_detail_route_reads_canonical_tenant_table(
    client, db_session, make_org, login_as
):
    org, foreign_org = make_org("adr-record-route"), make_org("adr-record-route-foreign")
    actor_user, foreign_user = _user(db_session, org), _user(db_session, foreign_org)
    actor_user.confirmed = foreign_user.confirmed = True
    adr = ArchitectureDecisionRecord(
        organization_id=org.id,
        adr_number=91,
        title="Canonical tenant ADR",
        status="proposed",
        context="Canonical route context",
        decision="Canonical route decision",
        rationale="Canonical route rationale",
        consequences="Canonical route consequences",
    )
    db_session.add(adr)
    db_session.flush()

    login_as(client, actor_user)
    own = client.get(f"/architecture/adrs/records/{adr.id}")
    login_as(client, foreign_user)
    foreign = client.get(f"/architecture/adrs/records/{adr.id}")

    assert own.status_code == 200
    assert b"Canonical tenant ADR" in own.data
    assert foreign.status_code == 404


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


def test_model_policy_rejects_invalid_json_and_absent_supporting_evidence(
    db_session, make_org
):
    org = make_org("invalid-model-policy")
    actor_user = _user(db_session, org)
    model = ArchitectureModel(
        organization_id=org.id,
        name="Invalid model dossier",
        version="1.0",
        user_id=actor_user.id,
        model_data="{not-json",
    )
    db_session.add(model)
    db_session.flush()
    adapter = ArchitectureModelARBAdapter()
    actor = _actor(actor_user, org)

    readiness = adapter.evaluate(actor, adapter.load(actor, model.id), {"human_reviewed": True})

    assert readiness.ready is False
    assert "architecture_model_json_invalid" in readiness.reason_codes
    assert "supporting_evidence_required" in readiness.reason_codes


def test_adr_policy_rejects_terminal_state_and_wrong_policy_version(db_session, make_org):
    org = make_org("invalid-adr-policy")
    actor_user = _user(db_session, org)
    dossier = _governance_dossier(org, "adr-arb-r1", "architecture_change", label="r1")
    adr = ArchitectureDecisionRecord(
        organization_id=org.id,
        adr_number=92,
        title="Already accepted ADR",
        status="accepted",
        context="Context",
        decision="Decision",
        rationale="Rationale",
        consequences="Consequences",
        governance_blob={"arb_readiness": dossier},
    )
    db_session.add(adr)
    db_session.flush()
    adapter = ADRARBAdapter()
    actor = _actor(actor_user, org)

    readiness = adapter.evaluate(actor, adapter.load(actor, adr.id), {"human_reviewed": True})

    assert readiness.ready is False
    assert "adr_state_not_submittable" in readiness.reason_codes
    assert "arb_policy_version_mismatch" in readiness.reason_codes


def test_subject_policy_requires_every_applicable_mandatory_standard(db_session, make_org):
    org = make_org("mandatory-standard-policy")
    actor_user = _user(db_session, org)
    standard = ARBGovernanceStandard(
        code=f"STD-TEST-{uuid.uuid4().hex[:10]}",
        name="Mandatory test standard",
        status="active",
        mandatory=True,
        applies_to_review_types=["technology_selection"],
        checklist_items=[{"item": "Evidence attached", "required": True}],
    )
    db_session.add(standard)
    db_session.flush()
    dossier = _governance_dossier(
        org, "architecture-model-arb-r2", "technology_selection", label="std"
    )
    dossier["standards"] = []
    model = ArchitectureModel(
        organization_id=org.id,
        name="Model missing a mandatory standard",
        version="1.0",
        user_id=actor_user.id,
        model_data=json.dumps({"elements": [], "relationships": [], "arb_readiness": dossier}),
    )
    db_session.add(model)
    db_session.flush()
    adapter = ArchitectureModelARBAdapter()
    actor = _actor(actor_user, org)

    readiness = adapter.evaluate(actor, adapter.load(actor, model.id), {"human_reviewed": True})

    assert readiness.ready is False
    assert "mandatory_standard_unsatisfied" in readiness.reason_codes
    # ARBGovernanceStandard is global reference data, not tenant-scoped, so every
    # active mandatory standard applicable to the review type is reported here --
    # including any already seeded in the database. Assert membership rather than
    # position, which would only hold against an empty standards table.
    assert standard.id in {
        entry["standard_id"] for entry in readiness.missing_evidence
    }


def _model_with_dossier(db_session, org, actor_user, dossier, name):
    model = ArchitectureModel(
        organization_id=org.id,
        name=name,
        version="1.0",
        user_id=actor_user.id,
        model_data=json.dumps(
            {"elements": [], "relationships": [], "arb_readiness": dossier}
        ),
    )
    db_session.add(model)
    db_session.flush()
    return model


def test_dossier_satisfied_claim_without_verified_evidence_never_satisfies_standard(
    db_session, make_org
):
    """A submitter-owned ``satisfied: true`` is a claim, not a verdict."""
    org = make_org("forged-standard")
    actor_user = _user(db_session, org)
    standard = ARBGovernanceStandard(
        code=f"STD-FORGE-{uuid.uuid4().hex[:10]}",
        name="Forgeable standard",
        status="active",
        mandatory=True,
        applies_to_review_types=["technology_selection"],
    )
    db_session.add(standard)
    db_session.flush()
    dossier = _governance_dossier(
        org, "architecture-model-arb-r2", "technology_selection", label="forge"
    )
    # Strip the server-verified backing while keeping the claim itself.
    for entry in dossier["standards"]:
        entry["evidence_ids"] = []
    model = _model_with_dossier(db_session, org, actor_user, dossier, "Forged claim")
    adapter = ArchitectureModelARBAdapter()
    actor = _actor(actor_user, org)

    readiness = adapter.evaluate(actor, adapter.load(actor, model.id), {"human_reviewed": True})

    assert readiness.ready is False
    assert "mandatory_standard_unverified" in readiness.reason_codes
    assert standard.id in {
        entry.get("standard_id") for entry in readiness.missing_evidence
    }
    assert all(
        entry["satisfied"] is False
        for entry in readiness.governance_result["mandatory_standards"]
    )
    with pytest.raises(BlockedByEvidence, match="arb_subject_not_ready"):
        adapter.snapshot(actor, adapter.load(actor, model.id), readiness)


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    (
        (
            lambda entry, org: entry.update({"evidence_id": 987654321}),
            "supporting_evidence_unresolved",
        ),
        (
            lambda entry, org: entry.update({"content_hash": "b" * 64}),
            "supporting_evidence_hash_mismatch",
        ),
        (
            lambda entry, org: entry.update({"evidence_type": "arb_supporting_document"}),
            "supporting_evidence_unverifiable",
        ),
    ),
)
def test_citation_must_resolve_to_a_server_held_evidence_record(
    db_session, make_org, mutate, expected_code
):
    org = make_org("unresolvable-evidence")
    actor_user = _user(db_session, org)
    dossier = _governance_dossier(
        org, "architecture-model-arb-r2", "technology_selection", label="unresolvable"
    )
    mutate(dossier["evidence"][0], org)
    model = _model_with_dossier(db_session, org, actor_user, dossier, "Unresolvable cite")
    adapter = ArchitectureModelARBAdapter()
    actor = _actor(actor_user, org)

    readiness = adapter.evaluate(actor, adapter.load(actor, model.id), {"human_reviewed": True})

    assert readiness.ready is False
    assert expected_code in readiness.reason_codes
    assert readiness.checks["evidence_citations"] == []
    assert readiness.governance_result["supporting_evidence_count"] == 0
    assert "mandatory_standard_unverified" in readiness.reason_codes


def test_citation_to_another_tenants_evidence_is_indistinguishable_from_missing(
    db_session, make_org
):
    """NotFound and NotAuthorised deliberately collapse into one reason code."""
    org, foreign_org = make_org("cite-own"), make_org("cite-foreign")
    actor_user = _user(db_session, org)
    foreign_record = _server_evidence(foreign_org, "foreign")
    dossier = _governance_dossier(
        org, "architecture-model-arb-r2", "technology_selection", label="crossorg"
    )
    dossier["evidence"][0]["evidence_id"] = foreign_record.id
    dossier["evidence"][0]["content_hash"] = foreign_record.content_hash
    for entry in dossier["standards"]:
        entry["evidence_ids"] = [foreign_record.id]
    model = _model_with_dossier(db_session, org, actor_user, dossier, "Cross-org cite")
    adapter = ArchitectureModelARBAdapter()
    actor = _actor(actor_user, org)

    readiness = adapter.evaluate(actor, adapter.load(actor, model.id), {"human_reviewed": True})

    assert readiness.ready is False
    assert "supporting_evidence_unresolved" in readiness.reason_codes
    assert "supporting_evidence_unverifiable" not in readiness.reason_codes


def test_legitimate_server_backed_dossier_still_reaches_a_pinned_snapshot(
    db_session, make_org
):
    org = make_org("legitimate-dossier")
    actor_user = _user(db_session, org)
    dossier = _governance_dossier(
        org, "architecture-model-arb-r2", "technology_selection", label="legit"
    )
    model = _model_with_dossier(db_session, org, actor_user, dossier, "Legitimate model")
    adapter = ArchitectureModelARBAdapter()
    actor = _actor(actor_user, org)
    subject = adapter.load(actor, model.id)

    readiness = adapter.evaluate(actor, subject, {"human_reviewed": True})
    evidence = adapter.snapshot(actor, subject, readiness)
    snapshot = db_session.get(ARBSubjectEvidenceSnapshot, evidence.evidence_id)

    assert readiness.ready is True
    assert readiness.reason_codes == []
    assert readiness.checks["evidence_citations"][0]["verified"] is True
    assert snapshot.content_hash == snapshot.recompute_content_hash()
    assert all(
        entry["verified_evidence_ids"]
        for entry in snapshot.payload["governance_result"]["mandatory_standards"]
    )


@pytest.mark.parametrize("subject_kind", ("architecture_model", "adr"))
def test_subject_snapshot_rejects_forged_and_changed_readiness(
    db_session, make_org, subject_kind
):
    org = make_org(f"stale-{subject_kind}")
    actor_user = _user(db_session, org)
    actor = _actor(actor_user, org)
    if subject_kind == "architecture_model":
        adapter = ArchitectureModelARBAdapter()
        dossier = _governance_dossier(
            org, "architecture-model-arb-r2", "technology_selection", label="stale-model"
        )
        row = ArchitectureModel(
            organization_id=org.id,
            name="Mutable model readiness",
            version="1.0",
            user_id=actor_user.id,
            model_data=json.dumps(
                {"elements": ["A"], "relationships": [], "arb_readiness": dossier}
            ),
        )
    else:
        adapter = ADRARBAdapter()
        dossier = _governance_dossier(
            org, "adr-arb-r2", "architecture_change", label="stale-adr"
        )
        row = ArchitectureDecisionRecord(
            organization_id=org.id,
            adr_number=93,
            title="Mutable ADR readiness",
            status="proposed",
            context="Context",
            decision="Decision",
            rationale="Rationale",
            consequences="Consequences",
            governance_blob={"arb_readiness": dossier},
        )
    db_session.add(row)
    db_session.flush()
    subject = adapter.load(actor, row.id)
    readiness = adapter.evaluate(actor, subject, {"human_reviewed": True})
    forged = ARBReadinessResult(
        ready=True,
        checks={"human_reviewed": True, "policy_version": adapter.policy_version},
    )

    with pytest.raises(CommandConflict, match="arb_readiness_stale"):
        adapter.snapshot(actor, subject, forged)

    dossier["evidence"][0]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    if subject_kind == "architecture_model":
        document = json.loads(row.model_data)
        document["arb_readiness"] = dossier
        row.model_data = json.dumps(document)
    else:
        row.governance_blob = {"arb_readiness": dossier}
    db_session.flush()

    with pytest.raises(CommandConflict, match="arb_readiness_stale"):
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
    assert snapshot.review_item_id is None
    assert db_session.scalar(
        db.select(db.func.count()).select_from(ARBReviewItem).where(
            ARBReviewItem.organization_id == org.id,
            ARBReviewItem.solution_id == solution.id,
        )
    ) == 0
    assert db_session.scalar(
        db.select(db.func.count()).select_from(SolutionNotification).where(
            SolutionNotification.solution_id == solution.id
        )
    ) == 0
    assert db_session.scalar(
        db.select(db.func.count()).select_from(AuditLog).where(
            AuditLog.organization_id == org.id,
            AuditLog.table_name == "arb_review_items",
        )
    ) == 0
    db_session.refresh(solution)
    assert solution.governance_status == "draft"
    assert solution.arb_submission_date is None
    assert solution.arb_review_item_id is None
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

    forged = ARBReadinessResult(
        ready=True,
        checks={
            "human_reviewed": True,
            "gate_policy_version": readiness.checks["gate_policy_version"],
        },
    )
    with pytest.raises(CommandConflict, match="arb_readiness_stale"):
        adapter.snapshot(decision_scope.actor, subject, forged)

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

    _record_named_source(
        decision_scope,
        candidate_id=decision_scope.candidate_id,
        adapter_key=f"adapter-stale-{uuid.uuid4().hex[:8]}",
        source_identity=f"external:adapter-stale:{uuid.uuid4().hex}",
        value="New evidence after adapter evaluation",
    )
    with pytest.raises(CommandConflict, match="arb_readiness_stale"):
        adapter.snapshot(decision_scope.actor, subject, readiness)

    # Re-evaluate so the readiness passed below reflects the named source recorded
    # above. Without this the staleness guard fires first and the hash-integrity
    # guard below is never reached.
    current_readiness = adapter.evaluate(
        decision_scope.actor, subject, {"human_reviewed": True, "ready": False}
    )
    assert current_readiness.ready is True

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
        adapter.snapshot(decision_scope.actor, subject, current_readiness)
