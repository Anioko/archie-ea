"""Canonical execution contracts for approved Transformation Room decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models.archimate_core import ArchiMateElement
from app.models.architecture_review_board import ARBReviewCycle, ARBReviewItem
from app.models.benefit import Benefit
from app.models.implementation_migration import WorkPackage
from app.models.solution_models import Solution
from app.models.strategic import RoadmapItem, StrategicInitiative
from app.models.transformation_decision import (
    DecisionBrief,
    DecisionBriefVersion,
    TransformationOption,
    TransformationOptionVersion,
)
from app.models.transformation_execution import DeliveryExportAttempt
from app.models.transformation_programme import (
    MeasureDefinition,
    ProgrammeOutcomeCommitment,
    ProgrammeRoleAssignment,
    ProgrammeWorkstream,
)
from app.models.user import User
from app.modules.transformation_room.command_service import canonical_request_digest
from app.modules.transformation_room.domain import (
    ActorContext,
    ApprovedAction,
    CommandClaim,
    CommandConflict,
    CommandResult,
    NotFound,
)
from app.modules.transformation_room.execution_service import (
    TransformationExecutionService,
)


@dataclass(frozen=True)
class ExecutionScope:
    actor: ActorContext
    foreign_actor: ActorContext
    programme_id: int
    workstream_id: int
    decision_brief_version_id: int
    option_version_id: int
    action: ApprovedAction


def _user(session, organization_id, role):
    suffix = uuid4().hex
    row = User(
        organization_id=organization_id,
        email=f"task9-{suffix}@example.test",
        first_name="Task",
        last_name="Nine",
        enterprise_role=role,
        confirmed=True,
    )
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def make_execution_scope(db_session, make_org):
    def make(*, technology_required=False):
        organization = make_org("execution")
        foreign_organization = make_org("execution-foreign")
        delivery_lead = _user(db_session, organization.id, "application_architect")
        outcome_owner = _user(db_session, organization.id, "business_architect")
        foreign_user = _user(
            db_session, foreign_organization.id, "application_architect"
        )
        programme = StrategicInitiative(
            organization_id=organization.id,
            name="Application estate transformation",
            description="Governed programme context",
            record_kind="transformation_programme",
            status="in_progress",
            owner_id=delivery_lead.id,
        )
        db_session.add(programme)
        db_session.flush()
        workstream = ProgrammeWorkstream(
            organization_id=organization.id,
            programme_id=programme.id,
            workstream_type="application_rationalisation",
            objective="Retire avoidable estate cost without service interruption",
            scope_expression={"application_ids": [41]},
            lifecycle_stage="approved",
            lead_id=delivery_lead.id,
        )
        db_session.add(workstream)
        db_session.flush()
        db_session.add(
            ProgrammeRoleAssignment(
                organization_id=organization.id,
                programme_id=programme.id,
                workstream_id=workstream.id,
                user_id=delivery_lead.id,
                role="delivery_lead",
                effective_from=date.today() - timedelta(days=1),
                assigned_by_id=delivery_lead.id,
            )
        )
        outcome = ProgrammeOutcomeCommitment(
            organization_id=organization.id,
            programme_id=programme.id,
            workstream_id=workstream.id,
            statement="Reduce annual run cost",
            owner_id=outcome_owner.id,
            improvement_direction="decrease",
            target_date=date.today() + timedelta(days=180),
            lifecycle="committed",
        )
        db_session.add(outcome)
        db_session.flush()
        measure = MeasureDefinition(
            organization_id=organization.id,
            outcome_commitment_id=outcome.id,
            metric_name="Annual run cost",
            unit="GBP/year",
            currency="GBP",
            aggregation="latest",
            baseline_amount="1000.00",
            target_amount="750.00",
            baseline_date=date.today(),
            target_date=outcome.target_date,
            cadence="quarterly",
            source_adapter="finance-ledger",
            source_key="run-cost",
        )
        option = TransformationOption(
            organization_id=organization.id,
            workstream_id=workstream.id,
            title="Controlled consolidation",
            action_type="consolidate",
            description="Consolidate the cited application estate",
            assumptions=["Service owners approve the cutover window"],
            dependencies=["Accepted service continuity evidence"],
            impacts=["Lower run cost"],
            risks=["Cutover interruption"],
            reversibility="Rollback during the controlled window",
            transition_approach="Phased consolidation",
            affected_capability_ids=[17],
            affected_value_stream_ids=[23],
            recommendation_rationale="Best evidence-backed value and risk balance",
            cost_min="100.00",
            cost_max="200.00",
            benefit_min="250.00",
            benefit_max="300.00",
            risk_min="0.10",
            risk_max="0.20",
            currency="GBP",
            technology_required=technology_required,
        )
        db_session.add_all([measure, option])
        db_session.flush()
        option_version = TransformationOptionVersion(
            organization_id=organization.id,
            option_id=option.id,
            workstream_id=workstream.id,
            version=1,
            source_revision=1,
            content_json={
                "title": option.title,
                "action_type": option.action_type,
                "description": option.description,
                "assumptions": list(option.assumptions),
                "dependencies": list(option.dependencies),
                "impacts": list(option.impacts),
                "risks": list(option.risks),
                "transition_approach": option.transition_approach,
            },
            cost_min="100.00",
            cost_max="200.00",
            benefit_min="250.00",
            benefit_max="300.00",
            risk_min="0.10",
            risk_max="0.20",
            currency="GBP",
            technology_required=technology_required,
            captured_by_id=delivery_lead.id,
            content_hash="a" * 64,
        )
        db_session.add(option_version)
        db_session.flush()
        brief = DecisionBrief(
            organization_id=organization.id,
            workstream_id=workstream.id,
            title="Consolidation decision",
            recommendation_option_id=option.id,
            decision_authority_id=delivery_lead.id,
            unknown_codes=[],
            conflicts=["Cutover window remains a governed constraint"],
            expected_impacts=["Lower run cost"],
            status="frozen",
        )
        db_session.add(brief)
        db_session.flush()
        frozen_payload = {
            "programme_id": programme.id,
            "workstream_id": workstream.id,
            "objective": workstream.objective,
            "scope_expression": workstream.scope_expression,
            "conflicts": list(brief.conflicts),
            "option_exception": None,
            "evidence": [{"id": 701, "claim_key": "service_continuity"}],
            "outcomes": [{"id": outcome.id, "statement": outcome.statement}],
            "measures": [{"id": measure.id, "metric_name": measure.metric_name}],
        }
        version = DecisionBriefVersion(
            organization_id=organization.id,
            brief_id=brief.id,
            workstream_id=workstream.id,
            version=1,
            source_revision=1,
            frozen_payload=frozen_payload,
            recommendation_option_version_id=option_version.id,
            option_version_ids=[option_version.id],
            cited_evidence_ids=[701],
            outcome_ids=[outcome.id],
            measure_ids=[measure.id],
            policy_version="transformation-r1.1",
            created_by_id=delivery_lead.id,
            content_hash="b" * 64,
            canonical_document="{}",
            submitted_by_id=delivery_lead.id,
            submitter_authorized=True,
            decision_authority_id=delivery_lead.id,
            human_reviewed_ai=True,
            blockers_cleared=True,
            unknowns_acknowledged=True,
        )
        db_session.add(version)
        db_session.flush()
        review_number = f"TR-{uuid4().hex[:12]}"
        cycle = ARBReviewCycle(
            organization_id=organization.id,
            subject_type="decision_brief",
            subject_id=brief.id,
            decision_brief_id=brief.id,
            decision_brief_version_id=version.id,
            review_number=review_number,
            cycle_number=1,
            status="approved",
            closed_at=datetime.now(timezone.utc),
            terminal_outcome="approved",
        )
        db_session.add(cycle)
        db_session.flush()
        review = ARBReviewItem(
            organization_id=organization.id,
            review_number=review_number,
            title=brief.title,
            description="Frozen decision review",
            review_type="architecture_change",
            subject_type="decision_brief",
            subject_id=brief.id,
            decision_brief_id=brief.id,
            decision_brief_version_id=version.id,
            review_cycle_id=cycle.id,
            status="approved",
            submitter_id=outcome_owner.id,
            submitted_at=datetime.now(),
            decision="approved",
            decision_rationale="Approved from the frozen evidence",
            decision_date=datetime.now(),
            decided_by_id=delivery_lead.id,
        )
        db_session.add(review)
        db_session.flush()
        actor = ActorContext(
            delivery_lead.id, organization.id, frozenset(), f"req-{uuid4().hex}"
        )
        foreign_actor = ActorContext(
            foreign_user.id,
            foreign_organization.id,
            frozenset(),
            f"req-{uuid4().hex}",
        )
        action = ApprovedAction(
            action_key="consolidate-cited-estate",
            option_version_id=option_version.id,
            title="Consolidate cited application estate",
            owner_id=delivery_lead.id,
            start_date=date.today() + timedelta(days=7),
            target_date=date.today() + timedelta(days=90),
            scheduling_applicable=True,
        )
        return ExecutionScope(
            actor,
            foreign_actor,
            programme.id,
            workstream.id,
            version.id,
            option_version.id,
            action,
        )

    return make


def _install_command_harness(monkeypatch, session):
    cache = {}

    def execute(**kwargs):
        key = (
            kwargs["operation"],
            kwargs["natural_key"],
            canonical_request_digest(kwargs["payload"]),
        )
        kwargs["authorizer"](
            session,
            kwargs["actor"],
            kwargs["operation"],
            kwargs["natural_key"],
        )
        if key in cache:
            prior = cache[key]
            return CommandResult(
                False,
                True,
                prior.operation_result_id,
                prior.object_ids,
                prior.response,
            )
        claim = CommandClaim(
            1, 1, "c" * 64, key[2], kwargs["natural_key"], "{}", "d" * 64
        )
        with session.begin_nested():
            mutation = kwargs["handler"](session, claim)
            session.flush()
        result = CommandResult(
            True,
            False,
            len(cache) + 1,
            mutation.object_ids,
            mutation.response,
        )
        cache[key] = result
        return result

    monkeypatch.setattr(
        "app.modules.transformation_room.execution_service.CommandService.execute",
        execute,
    )


def test_materialise_creates_one_canonical_set_replays_and_never_implies_solution(
    db_session, monkeypatch, make_execution_scope
):
    scope = make_execution_scope(technology_required=False)
    _install_command_harness(monkeypatch, db_session)

    first = TransformationExecutionService.materialise(
        actor=scope.actor,
        decision_brief_version_id=scope.decision_brief_version_id,
        actions=(scope.action,),
        command_key="materialise-1",
    )
    replay = TransformationExecutionService.materialise(
        actor=scope.actor,
        decision_brief_version_id=scope.decision_brief_version_id,
        actions=(scope.action,),
        command_key="materialise-2",
    )

    work_packages = db_session.scalars(
        select(WorkPackage).where(
            WorkPackage.organization_id == scope.actor.organization_id,
            WorkPackage.decision_brief_version_id == scope.decision_brief_version_id,
        )
    ).all()
    roadmap_items = db_session.scalars(
        select(RoadmapItem).where(
            RoadmapItem.organization_id == scope.actor.organization_id,
            RoadmapItem.decision_brief_version_id == scope.decision_brief_version_id,
        )
    ).all()
    benefits = db_session.scalars(
        select(Benefit).where(
            Benefit.organization_id == scope.actor.organization_id,
            Benefit.decision_brief_version_id == scope.decision_brief_version_id,
        )
    ).all()
    solutions = db_session.scalar(
        select(func.count()).select_from(Solution).where(
            Solution.organization_id == scope.actor.organization_id,
            Solution.workstream_id == scope.workstream_id,
        )
    )
    workstream = db_session.get(ProgrammeWorkstream, scope.workstream_id)

    assert first.created is True and replay.idempotent is True
    assert replay.object_ids == first.object_ids
    assert len(work_packages) == len(roadmap_items) == len(benefits) == 1
    assert solutions == 0
    assert work_packages[0].enterprise_initiative_id is None
    assert work_packages[0].strategic_initiative_id == scope.programme_id
    assert roadmap_items[0].work_package_id == work_packages[0].id
    assert benefits[0].work_package_id == work_packages[0].id
    assert benefits[0].legacy_enterprise_initiative_id is None
    assert work_packages[0].archimate_element_id is not None
    assert (
        db_session.get(ArchiMateElement, work_packages[0].archimate_element_id).type
        == "WorkPackage"
    )
    assert workstream.lifecycle_stage == "execute"

    workstream.lifecycle_stage = "completed"
    db_session.flush()
    assert db_session.scalar(
        select(func.count()).select_from(Solution).where(
            Solution.organization_id == scope.actor.organization_id,
            Solution.workstream_id == scope.workstream_id,
        )
    ) == 0


def test_governance_gate_blocks_conditional_and_expired_waiver_but_accepts_fulfilment():
    now = datetime.now(timezone.utc)
    review = SimpleNamespace(
        status="approved_with_conditions", decision="approved_with_conditions"
    )
    cycle = SimpleNamespace(
        status="approved_with_conditions",
        terminal_outcome="approved_with_conditions",
    )
    pending = SimpleNamespace(status="pending", waiver_expires_at=None)
    with pytest.raises(CommandConflict, match="execution_not_approved"):
        TransformationExecutionService._assert_governance_ready(
            cycle, review, (pending,), now
        )

    cycle.status = review.status = "approved"
    fulfilled = SimpleNamespace(status="fulfilled", waiver_expires_at=None)
    TransformationExecutionService._assert_governance_ready(
        cycle, review, (fulfilled,), now
    )

    expired = SimpleNamespace(
        status="waived", waiver_expires_at=now - timedelta(seconds=1)
    )
    with pytest.raises(CommandConflict, match="execution_conditions_unresolved"):
        TransformationExecutionService._assert_governance_ready(
            cycle, review, (expired,), now
        )


def test_solution_requires_true_technology_flag_and_explicit_command(
    db_session, monkeypatch, make_execution_scope
):
    non_technology = make_execution_scope(technology_required=False)
    _install_command_harness(monkeypatch, db_session)
    with pytest.raises(CommandConflict, match="technology_solution_not_required"):
        TransformationExecutionService.create_technology_solution(
            actor=non_technology.actor,
            decision_brief_version_id=non_technology.decision_brief_version_id,
            option_version_id=non_technology.option_version_id,
            command_key="no-technology-solution",
        )


def test_explicit_technology_solution_is_single_and_inherits_only_frozen_context(
    db_session, monkeypatch, make_execution_scope
):
    scope = make_execution_scope(technology_required=True)
    _install_command_harness(monkeypatch, db_session)

    first = TransformationExecutionService.create_technology_solution(
        actor=scope.actor,
        decision_brief_version_id=scope.decision_brief_version_id,
        option_version_id=scope.option_version_id,
        command_key="technology-solution-1",
    )
    replay = TransformationExecutionService.create_technology_solution(
        actor=scope.actor,
        decision_brief_version_id=scope.decision_brief_version_id,
        option_version_id=scope.option_version_id,
        command_key="technology-solution-2",
    )
    rows = db_session.scalars(
        select(Solution).where(
            Solution.organization_id == scope.actor.organization_id,
            Solution.workstream_id == scope.workstream_id,
        )
    ).all()

    assert first.object_ids == replay.object_ids and replay.idempotent is True
    assert len(rows) == 1
    solution = rows[0]
    assert solution.initiative_id == scope.programme_id
    assert solution.workstream_id == scope.workstream_id
    assert solution.journey_state == {
        "source": "transformation_room",
        "decision_brief_version_id": scope.decision_brief_version_id,
        "option_version_id": scope.option_version_id,
        "constraints": ["Cutover window remains a governed constraint"],
        "cited_evidence_ids": [701],
        "scope_expression": {"application_ids": [41]},
    }


def test_cross_tenant_decision_identifier_is_not_found(
    monkeypatch, db_session, make_execution_scope
):
    scope = make_execution_scope()
    _install_command_harness(monkeypatch, db_session)
    with pytest.raises(NotFound, match="decision_brief_version_not_found"):
        TransformationExecutionService.materialise(
            actor=scope.foreign_actor,
            decision_brief_version_id=scope.decision_brief_version_id,
            actions=(scope.action,),
            command_key="foreign-materialise",
        )


def test_subordinate_write_failure_rolls_back_the_whole_materialisation(
    db_session, monkeypatch, make_execution_scope
):
    scope = make_execution_scope()
    _install_command_harness(monkeypatch, db_session)

    def fail_roadmap(*_args, **_kwargs):
        raise RuntimeError("forced subordinate write failure")

    monkeypatch.setattr(
        TransformationExecutionService, "_create_roadmap_item", fail_roadmap
    )
    with pytest.raises(RuntimeError, match="forced subordinate write failure"):
        TransformationExecutionService.materialise(
            actor=scope.actor,
            decision_brief_version_id=scope.decision_brief_version_id,
            actions=(scope.action,),
            command_key="rollback-materialise",
        )

    assert db_session.scalar(
        select(func.count()).select_from(WorkPackage).where(
            WorkPackage.organization_id == scope.actor.organization_id,
            WorkPackage.decision_brief_version_id == scope.decision_brief_version_id,
        )
    ) == 0
    assert db_session.scalar(
        select(func.count()).select_from(ArchiMateElement).where(
            ArchiMateElement.organization_id == scope.actor.organization_id,
            ArchiMateElement.type == "WorkPackage",
        )
    ) == 0


def test_partial_unique_key_rejects_a_concurrent_duplicate(
    db_session, monkeypatch, make_execution_scope
):
    scope = make_execution_scope()
    _install_command_harness(monkeypatch, db_session)
    result = TransformationExecutionService.materialise(
        actor=scope.actor,
        decision_brief_version_id=scope.decision_brief_version_id,
        actions=(scope.action,),
        command_key="race-winner",
    )
    winner = db_session.get(WorkPackage, result.object_ids["work_package_ids"][0])

    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            WorkPackage(
                organization_id=scope.actor.organization_id,
                name="Concurrent duplicate",
                strategic_initiative_id=scope.programme_id,
                programme_workstream_id=scope.workstream_id,
                decision_brief_version_id=scope.decision_brief_version_id,
                materialisation_key=winner.materialisation_key,
            )
        )
        db_session.flush()


def test_export_failure_preserves_pending_work_and_completed_attempt_is_immutable(
    db_session, monkeypatch, make_execution_scope
):
    scope = make_execution_scope()
    _install_command_harness(monkeypatch, db_session)
    materialised = TransformationExecutionService.materialise(
        actor=scope.actor,
        decision_brief_version_id=scope.decision_brief_version_id,
        actions=(scope.action,),
        command_key="materialise-for-export",
    )
    work_package_id = materialised.object_ids["work_package_ids"][0]

    def unavailable(_work_package, _request):
        raise ConnectionError("provider unavailable")

    exported = TransformationExecutionService.export_work_package(
        actor=scope.actor,
        work_package_id=work_package_id,
        provider_key="delivery-provider",
        request={"project": "ARCH"},
        exporter=unavailable,
        command_key="export-failure",
    )
    work_package = db_session.get(WorkPackage, work_package_id)
    attempt = db_session.get(
        DeliveryExportAttempt, exported.object_ids["delivery_export_attempt_id"]
    )

    assert exported.response["exported"] is False
    assert exported.response["status"] == "failed"
    assert work_package.status == "planned"
    assert attempt.status == "failed" and attempt.completed_at is not None
    with pytest.raises(
        DBAPIError, match="completed delivery export attempts are immutable"
    ), db_session.begin_nested():
        db_session.execute(
            text(
                "UPDATE delivery_export_attempts SET error_message = :message "
                "WHERE id = :attempt_id AND organization_id = :organization_id"
            ),
            {
                "message": "rewritten outside the service",
                "attempt_id": attempt.id,
                "organization_id": scope.actor.organization_id,
            },
        )
    db_session.expire(attempt)
    with pytest.raises(
        ValueError, match="completed delivery export attempts are immutable"
    ), db_session.begin_nested():
        attempt.error_message = "rewritten"
        db_session.flush()

    retried = TransformationExecutionService.export_work_package(
        actor=scope.actor,
        work_package_id=work_package_id,
        provider_key="delivery-provider",
        request={"project": "ARCH"},
        exporter=lambda _work_package, _request: {"external_key": "ARCH-42"},
        command_key="export-successful-retry",
        predecessor_attempt_id=attempt.id,
    )
    retry = db_session.get(
        DeliveryExportAttempt,
        retried.object_ids["delivery_export_attempt_id"],
    )
    db_session.refresh(attempt)

    assert retried.response["exported"] is True
    assert retry.predecessor_attempt_id == attempt.id
    assert retry.status == "succeeded"
    assert retry.external_key == "ARCH-42"
    assert attempt.status == "failed"
