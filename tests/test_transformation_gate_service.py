"""Versioned, pure lifecycle gate and transition tests."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.models.benefit import Benefit
from app.models.transformation_programme import ProgrammeWorkstream
from app.models.user import User
from app.modules.transformation_room.domain import (
    ActorContext,
    BlockedByEvidence,
    CommandConflict,
    NotAuthorised,
    NotFound,
)
from app.modules.transformation_room.gate_service import (
    PolicySnapshot,
    TransformationGateService,
)
from app.modules.transformation_room.programme_service import TransformationProgrammeService

from tests.test_transformation_programme_service import _intake, programme_fixture


def _row(**values):
    return SimpleNamespace(**values)


def _policy_snapshot(source: str, target: str, **changes):
    programme = _row(id=1, owner_id=7, status="active", archived_at=None, organization_id=10)
    workstream = _row(
        id=2,
        programme_id=1,
        lead_id=7,
        objective="Reduce avoidable run cost",
        scope_expression={"business_units": ["Retail"]},
        target_date=date(2027, 6, 30),
        target_date_unavailable_reason=None,
        lifecycle_stage=source,
    )
    outcome = _row(id=3, owner_id=7, statement="Reduce run cost")
    measure = _row(
        id=4,
        outcome_commitment_id=3,
        metric_name="Annual run cost",
        unit="GBP",
        baseline_amount=None,
        baseline_value=None,
        target_amount=Decimal("900000.00"),
        target_value=None,
        unavailable_reason="Finance baseline requested",
    )
    candidate = _row(
        id=11,
        workstream_id=2,
        organization_id=10,
        inclusion_status="accepted",
        subject_exists=True,
        duplicates_resolved=True,
    )
    evidence = tuple(
        _row(
            id=20 + offset,
            candidate_id=11,
            claim_key=claim_key,
            status="accepted",
            freshness_status="fresh",
            conflict_resolved=True,
        )
        for offset, claim_key in enumerate(
            (
                "application_owner",
                "lifecycle",
                "cost",
                "business_criticality",
                "capability_impact",
                "dependency_impact",
                "risk",
                "source_freshness",
            ),
            start=1,
        )
    )
    requests = tuple(
        _row(
            id=40 + offset,
            candidate_id=11,
            claim_key=row.claim_key,
            required=True,
            status="accepted",
            accepted_evidence_id=row.id,
            acknowledgement_id=None,
            waiver_id=None,
        )
        for offset, row in enumerate(evidence, start=1)
    )
    options = (
        _row(
            id=61,
            workstream_id=2,
            immutable=True,
            content_hash="a" * 64,
            assumptions=("Funding remains available",),
            benefit_min=Decimal("100.00"),
            benefit_max=Decimal("120.00"),
            cost_min=Decimal("40.00"),
            cost_max=Decimal("50.00"),
            currency="GBP",
            risks=("Delivery capacity",),
            dependencies=("Finance data",),
            reversibility="phased rollback",
            transition_approach="Incremental retirement",
            affected_capability_ids=(1,),
            affected_value_stream_ids=(2,),
            technology_required=False,
            recommendation_rationale="Best value with manageable risk",
        ),
        _row(
            id=62,
            workstream_id=2,
            immutable=True,
            content_hash="b" * 64,
            assumptions=("Supplier support continues",),
            benefit_min=Decimal("60.00"),
            benefit_max=Decimal("80.00"),
            cost_min=Decimal("20.00"),
            cost_max=Decimal("30.00"),
            currency="GBP",
            risks=("Supplier dependency",),
            dependencies=("Contract renewal",),
            reversibility="contract exit",
            transition_approach="Renew while alternatives are validated",
            affected_capability_ids=(1,),
            affected_value_stream_ids=(2,),
            technology_required=False,
            recommendation_rationale="Lower-cost comparator",
        ),
    )
    brief = _row(
        id=71,
        decision_brief_id=70,
        workstream_id=2,
        immutable=True,
        content_hash="c" * 64,
        cited_evidence_ids=tuple(row.id for row in evidence),
        option_version_ids=(61, 62),
        human_reviewed_ai=True,
        decision_authority_id=7,
        blockers_cleared=True,
        unknowns_acknowledged=True,
        policy_version="transformation-r1.1",
        submitted_by_id=7,
        submitter_authorized=True,
    )
    decision = {
        "approved": "approved",
        "approved_with_conditions": "approved_with_conditions",
        "rejected": "rejected",
        "evidence": "returned_for_evidence",
        "options": "returned_for_options",
    }.get(target, target)
    if source in {"approved", "execute", "outcomes"}:
        decision = "approved"
    if source == "approved_with_conditions" and target == "approved":
        decision = "approved_with_conditions"
    decision_target = target
    if decision == "approved":
        decision_target = "approved"
    elif decision == "approved_with_conditions":
        decision_target = "approved_with_conditions"
    cycle = _row(
        id=81,
        workstream_id=2,
        subject_type="decision_brief",
        subject_id=70,
        decision_brief_id=70,
        brief_version_id=71,
        decision_brief_version_id=71,
        status="decided",
        decision=decision,
        target_stage=decision_target,
        decision_maker_id=7,
        rationale="Decision grounded in the submitted brief",
        decided_at=datetime(2026, 8, 22, tzinfo=timezone.utc),
    )
    conditions = (
        _row(
            id=91,
            arb_cycle_id=81,
            status="fulfilled",
            accepted_evidence_id=21,
            waiver_authority_id=None,
            waiver_reason=None,
            waiver_expires_at=None,
        ),
    )
    if source == "in_governance" and target == "approved":
        conditions = ()
    work_package = _row(
        id=101, workstream_id=2, owner_id=7, status="planned",
        decision_brief_version_id=71,
    )
    roadmap = _row(
        id=111, programme_workstream_id=2, work_package_id=101,
        decision_brief_version_id=71,
    )
    action = _row(
        id=121,
        workstream_id=2,
        decision_brief_version_id=71,
        status="accepted",
        decline_reason=None,
        owner_id=7,
        work_package_id=101,
        scheduling_applicable=True,
        roadmap_item_id=111,
    )
    benefit = _row(
        id=131,
        strategic_initiative_id=1,
        programme_workstream_id=2,
        outcome_commitment_id=3,
        work_package_id=101,
        owner_id=7,
        measure="Annual run cost",
        unit="GBP",
        baseline_value=None,
        target_value=Decimal("900000.00"),
        measurement_method="Monthly finance ledger extract",
        measurement_frequency="monthly",
        decision_brief_version_id=71,
    )
    delivery = _row(
        id=141,
        workstream_id=2,
        completion_evidence_id=21,
        residual_risk="Low residual support risk",
        operational_owner_id=7,
        measurement_schedule="monthly",
        corrective_action_approved=target == "execute" and source == "outcomes",
    )
    measurement = _row(
        id=151,
        benefit_id=131,
        outcome_commitment_id=3,
        value=Decimal("890000.00"),
        unavailable_reason=None,
        observed_at=datetime(2027, 7, 1, tzinfo=timezone.utc),
        valid=True,
    )
    review = _row(
        id=161,
        workstream_id=2,
        outcome_commitment_id=3,
        judgement="realised",
        lessons="Start owner validation earlier",
        follow_up_decision="close",
    )
    values = {
        "programme": programme,
        "workstream": workstream,
        "role_assignments": (),
        "outcomes": (outcome,),
        "measures": (measure,),
        "accepted_candidates": (candidate,),
        "active_evidence_heads": (),
        "evidence_records": evidence,
        "evidence_requests": requests,
        "evidence_waivers": (),
        "option_versions": options,
        "option_exceptions": (),
        "brief_versions": (brief,),
        "arb_cycles": (cycle,),
        "arb_conditions": conditions,
        "approved_actions": (action,),
        "work_packages": (work_package,),
        "roadmap_items": (roadmap,),
        "benefits": (benefit,),
        "delivery_records": (delivery,),
        "measurements": (measurement,),
        "outcome_reviews": (review,),
        "unavailable_resources": frozenset(),
    }
    if source == "rejected" and target == "options":
        values["arb_cycles"] = (replace_namespace(cycle, decision="reframe_authorised", target_stage="options"),)
    values.update(changes)
    return PolicySnapshot(**values)


def replace_namespace(row, **changes):
    return _row(**{**vars(row), **changes})


def test_objective_gate_is_pure_and_transition_is_locked(programme_fixture):
    """Catches gate evaluation mutating state or transition bypassing revision/event handling."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="gate-ready",
        request=_intake(programme_fixture.owner_id),
    )
    workstream_id = created.object_ids["workstream_id"]

    evaluated = TransformationGateService.evaluate(
        actor=programme_fixture.actor,
        workstream_id=workstream_id,
        target_stage="discover",
    )
    with Session(db.engine) as session:
        unchanged = session.scalar(
            select(ProgrammeWorkstream).where(
                ProgrammeWorkstream.id == workstream_id,
                ProgrammeWorkstream.organization_id == programme_fixture.organization_id,
            )
        )
        assert unchanged.lifecycle_stage == "objective"
        assert unchanged.revision == 1

    transitioned = TransformationGateService.transition(
        actor=programme_fixture.actor,
        workstream_id=workstream_id,
        target_stage="discover",
        expected_revision=1,
        command_key="to-discover",
    )
    replayed = TransformationGateService.transition(
        actor=programme_fixture.actor,
        workstream_id=workstream_id,
        target_stage="discover",
        expected_revision=1,
        command_key="to-discover",
    )

    assert evaluated.allowed is True
    assert evaluated.policy_version == "transformation-r1.1"
    assert transitioned.response["lifecycle_stage"] == "discover"
    assert replayed.operation_result_id == transitioned.operation_result_id
    with Session(db.engine) as session:
        changed = session.get(ProgrammeWorkstream, workstream_id)
        assert changed.lifecycle_stage == "discover"
        assert changed.revision == 2


def test_objective_gate_returns_stable_blockers_and_denial_does_not_mutate(programme_fixture):
    """Catches an incomplete objective advancing or returning transient prose-only errors."""
    request = replace(
        _intake(programme_fixture.owner_id),
        scope_expression={},
        target_date=None,
        target_date_unavailable_reason="Date depends on portfolio review",
    )
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="gate-blocked",
        request=request,
    )
    workstream_id = created.object_ids["workstream_id"]

    gate = TransformationGateService.evaluate(
        actor=programme_fixture.actor,
        workstream_id=workstream_id,
        target_stage="discover",
    )
    assert gate.allowed is False
    assert {blocker.code for blocker in gate.blockers} == {"scope_required"}

    with pytest.raises(BlockedByEvidence) as denied:
        TransformationGateService.transition(
            actor=programme_fixture.actor,
            workstream_id=workstream_id,
            target_stage="discover",
            expected_revision=1,
            command_key="blocked-transition",
        )
    assert [item.code for item in denied.value.blockers] == ["scope_required"]
    with Session(db.engine) as session:
        unchanged = session.get(ProgrammeWorkstream, workstream_id)
        assert unchanged.lifecycle_stage == "objective"
        assert unchanged.revision == 1


def test_gate_load_is_explicitly_tenant_scoped(programme_fixture):
    """Catches a valid foreign workstream ID revealing readiness across tenants."""
    foreign_actor = ActorContext(
        programme_fixture.foreign_owner_id,
        programme_fixture.foreign_organization_id,
        frozenset(),
        "foreign-create",
    )
    created = TransformationProgrammeService.create_programme(
        actor=foreign_actor,
        command_key="foreign-gate",
        request=_intake(programme_fixture.foreign_owner_id),
    )
    with pytest.raises(NotFound, match="workstream_not_found"):
        TransformationGateService.evaluate(
            actor=programme_fixture.actor,
            workstream_id=created.object_ids["workstream_id"],
            target_stage="discover",
        )


@pytest.mark.parametrize("source,target", sorted(TransformationGateService.TRANSITIONS))
def test_approved_r11_transition_table_accepts_only_complete_matching_snapshots(source, target):
    """Catches any approved lifecycle edge retaining a permanent or shallow blocker."""
    snapshot = _policy_snapshot(source, target)
    transition = TransformationGateService.require_valid_transition(source, target)
    blockers, _warnings, _evidence_ids = TransformationGateService.evaluate_requirements(
        snapshot, transition
    )
    assert blockers == []


def test_governance_decision_must_match_subject_brief_target_and_terminal_projection():
    """Catches an unrelated ARB row advancing a governed workstream."""
    snapshot = _policy_snapshot("in_governance", "approved")
    wrong_cycle = replace_namespace(
        snapshot.arb_cycles[0],
        brief_version_id=999,
        subject_id=999,
        target_stage="rejected",
    )
    blockers, _, _ = TransformationGateService.evaluate_requirements(
        replace(snapshot, arb_cycles=(wrong_cycle,)),
        TransformationGateService.require_valid_transition("in_governance", "approved"),
    )
    assert {row.code for row in blockers} == {"arb_decision_mismatch"}


def test_execute_gate_rejects_orphaned_actions_work_and_benefit_contracts():
    """Catches unrelated work/benefit rows satisfying Approved-to-Execute readiness."""
    snapshot = _policy_snapshot("approved", "execute")
    bad_action = replace_namespace(snapshot.approved_actions[0], owner_id=None, work_package_id=999)
    bad_benefit = replace_namespace(
        snapshot.benefits[0], outcome_commitment_id=999, measurement_method=None
    )
    blockers, _, _ = TransformationGateService.evaluate_requirements(
        replace(snapshot, approved_actions=(bad_action,), benefits=(bad_benefit,)),
        TransformationGateService.require_valid_transition("approved", "execute"),
    )
    assert {row.code for row in blockers} == {
        "approved_action_unresolved",
        "benefit_contract_incomplete",
    }


@pytest.mark.parametrize(
    "cycle_change",
    (
        {"subject_id": 999, "decision_brief_id": 999},
        {"status": "open", "decided_at": None},
    ),
)
def test_conditional_projection_requires_matching_terminal_governed_cycle(cycle_change):
    """Catches unrelated or pending conditional decisions releasing conditions."""
    snapshot = _policy_snapshot("approved_with_conditions", "approved")
    wrong_cycle = replace_namespace(snapshot.arb_cycles[0], **cycle_change)
    blockers, _, _ = TransformationGateService.evaluate_requirements(
        replace(snapshot, arb_cycles=(wrong_cycle,)),
        TransformationGateService.require_valid_transition(
            "approved_with_conditions", "approved"
        ),
    )
    assert {row.code for row in blockers} == {"arb_decision_mismatch"}


def test_execute_accepts_resolved_conditional_cycle_and_real_benefit_shape(app):
    """Catches execution excluding a correctly projected conditional approval."""
    snapshot = _policy_snapshot("approved", "execute")
    conditional_cycle = replace_namespace(
        snapshot.arb_cycles[0],
        decision="approved_with_conditions",
        target_stage="approved_with_conditions",
    )
    canonical_benefit = Benefit(
        id=131,
        organization_id=10,
        name="Reduce annual run cost",
        strategic_initiative_id=1,
        programme_workstream_id=2,
        outcome_commitment_id=3,
        work_package_id=101,
        decision_brief_version_id=71,
        owner_id=7,
        measure="Annual run cost",
        unit="GBP",
        baseline_value=None,
        target_value=Decimal("900000.00"),
        measurement_method="Monthly finance ledger extract",
        measurement_frequency="monthly",
    )
    blockers, _, _ = TransformationGateService.evaluate_requirements(
        replace(
            snapshot,
            arb_cycles=(conditional_cycle,),
            benefits=(canonical_benefit,),
        ),
        TransformationGateService.require_valid_transition("approved", "execute"),
    )
    assert blockers == []


def test_missing_option_numeric_bound_returns_stable_contract_blocker():
    """Catches an incomplete range raising TypeError instead of a policy blocker."""
    snapshot = _policy_snapshot("options", "decision_ready")
    incomplete = replace_namespace(snapshot.option_versions[0], cost_min=None)
    blockers, _, _ = TransformationGateService.evaluate_requirements(
        replace(snapshot, option_versions=(incomplete, snapshot.option_versions[1])),
        TransformationGateService.require_valid_transition("options", "decision_ready"),
    )
    assert {row.code for row in blockers} == {"option_contract_incomplete"}


def test_completed_gate_requires_measurement_for_each_relevant_benefit_and_outcome_review():
    """Catches a valid but unrelated measurement projecting the workstream Completed."""
    snapshot = _policy_snapshot("outcomes", "completed")
    unrelated = replace_namespace(snapshot.measurements[0], benefit_id=999, outcome_commitment_id=999)
    blockers, _, _ = TransformationGateService.evaluate_requirements(
        replace(snapshot, measurements=(unrelated,)),
        TransformationGateService.require_valid_transition("outcomes", "completed"),
    )
    assert {row.code for row in blockers} == {"outcome_measurement_required"}


def test_non_finite_persisted_measure_cannot_make_objective_gate_ready():
    """Catches PostgreSQL Numeric NaN being treated as a valid target measurement contract."""
    snapshot = _policy_snapshot("objective", "discover")
    bad_measure = replace_namespace(snapshot.measures[0], target_amount=Decimal("NaN"))
    blockers, _, _ = TransformationGateService.evaluate_requirements(
        replace(snapshot, measures=(bad_measure,)),
        TransformationGateService.require_valid_transition("objective", "discover"),
    )
    assert {row.code for row in blockers} == {"measure_value_invalid"}


def test_missing_later_task_resource_is_explicitly_unavailable_and_fail_closed():
    """Catches absent future persistence being mistaken for an ordinary empty, satisfiable set."""
    snapshot = _policy_snapshot(
        "discover",
        "evidence",
        unavailable_resources=frozenset({"candidates", "evidence"}),
    )
    blockers, _, _ = TransformationGateService.evaluate_requirements(
        snapshot,
        TransformationGateService.require_valid_transition("discover", "evidence"),
    )
    assert [(row.code, row.resource_type) for row in blockers] == [
        ("policy_resource_unavailable", "candidates"),
        ("policy_resource_unavailable", "evidence"),
    ]


def test_gate_read_reloads_persisted_actor_and_rejects_forged_actor_roles(programme_fixture):
    """Catches gate reads trusting caller-supplied ActorContext roles without portfolio access."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="gate-read-auth",
        request=_intake(programme_fixture.owner_id),
    )
    outsider = User(
        email=f"gate-outsider-{uuid.uuid4().hex[:10]}@example.test",
        organization_id=programme_fixture.organization_id,
        confirmed=True,
        enterprise_role="application_manager",
    )
    db.session.add(outsider)
    db.session.commit()
    outsider_id = outsider.id
    forged = ActorContext(
        outsider_id,
        programme_fixture.organization_id,
        frozenset({"enterprise_architect", "programme_owner"}),
        "forged-gate-read",
    )
    with pytest.raises(NotAuthorised, match="programme_read_not_authorised"):
        TransformationGateService.evaluate(
            actor=forged,
            workstream_id=created.object_ids["workstream_id"],
            target_stage="discover",
        )


def test_archived_programme_cannot_be_evaluated_or_transitioned(programme_fixture):
    """Catches archived workstreams continuing to advertise or execute next actions."""
    created = TransformationProgrammeService.create_programme(
        actor=programme_fixture.actor,
        command_key="archived-gate",
        request=_intake(programme_fixture.owner_id),
    )
    TransformationProgrammeService.archive(
        actor=programme_fixture.actor,
        programme_id=created.object_ids["programme_id"],
        expected_revision=1,
        command_key="archive-for-gate",
    )
    with pytest.raises(CommandConflict, match="programme_archived"):
        TransformationGateService.evaluate(
            actor=programme_fixture.actor,
            workstream_id=created.object_ids["workstream_id"],
            target_stage="discover",
        )
    with pytest.raises(CommandConflict, match="programme_archived"):
        TransformationGateService.transition(
            actor=programme_fixture.actor,
            workstream_id=created.object_ids["workstream_id"],
            target_stage="discover",
            expected_revision=1,
            command_key="archived-transition",
        )
