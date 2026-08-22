"""Pure, versioned Transformation Room lifecycle policy and locked transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.models.benefit import Benefit
from app.models.implementation_migration import WorkPackage
from app.models.strategic import RoadmapItem, StrategicInitiative
from app.models.transformation_programme import (
    ISO_4217_CURRENCIES,
    MeasureDefinition,
    ProgrammeOutcomeCommitment,
    ProgrammeRoleAssignment,
    ProgrammeWorkstream,
)
from app.modules.transformation_room.command_service import CommandService, OperationAuthorizer
from app.modules.transformation_room.domain import (
    ActorContext,
    BlockedByEvidence,
    CommandConflict,
    CommandResult,
    DomainMutationResult,
    GateBlocker,
    GateResult,
    NotAuthorised,
    NotFound,
)
from app.modules.transformation_room.programme_service import (
    CREATE_ROLES,
    OBJECTIVE_ROLES,
    READ_ROLES,
    TransformationProgrammeService,
)


@dataclass(frozen=True)
class Transition:
    source: str
    target: str


@dataclass(frozen=True)
class PolicySnapshot:
    """All inputs to the r1.1 policy, including not-yet-installed resources."""

    programme: StrategicInitiative
    workstream: ProgrammeWorkstream
    role_assignments: tuple[ProgrammeRoleAssignment, ...]
    outcomes: tuple[ProgrammeOutcomeCommitment, ...]
    measures: tuple[MeasureDefinition, ...]
    accepted_candidates: tuple[object, ...]
    active_evidence_heads: tuple[object, ...]
    evidence_records: tuple[object, ...]
    evidence_requests: tuple[object, ...]
    evidence_waivers: tuple[object, ...]
    option_versions: tuple[object, ...]
    option_exceptions: tuple[object, ...]
    brief_versions: tuple[object, ...]
    arb_cycles: tuple[object, ...]
    arb_conditions: tuple[object, ...]
    approved_actions: tuple[object, ...]
    work_packages: tuple[WorkPackage, ...]
    roadmap_items: tuple[RoadmapItem, ...]
    benefits: tuple[Benefit, ...]
    delivery_records: tuple[object, ...]
    measurements: tuple[object, ...]
    outcome_reviews: tuple[object, ...]
    unavailable_resources: frozenset[str]


def _value(row: object, field: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(field, default)
    return getattr(row, field, default)


def _text(row: object, field: str) -> str:
    value = _value(row, field)
    return value.strip() if isinstance(value, str) else ""


def _finite(value: Any) -> bool:
    if value is None:
        return True
    try:
        return Decimal(str(value)).is_finite()
    except (InvalidOperation, ValueError, TypeError):
        return False


def _current(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, datetime):
        now = datetime.now(timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value > now
    return value >= date.today()


class TransformationGateService:
    POLICY_VERSION = "transformation-r1.1"
    TRANSITIONS = frozenset(
        {
            ("objective", "discover"),
            ("discover", "evidence"),
            ("evidence", "options"),
            ("options", "decision_ready"),
            ("decision_ready", "in_governance"),
            ("in_governance", "evidence"),
            ("in_governance", "options"),
            ("in_governance", "approved"),
            ("in_governance", "approved_with_conditions"),
            ("in_governance", "rejected"),
            ("approved_with_conditions", "approved"),
            ("approved", "execute"),
            ("execute", "outcomes"),
            ("outcomes", "completed"),
            ("outcomes", "execute"),
            ("rejected", "options"),
        }
    )
    NEXT_STAGE = {
        "objective": "discover", "discover": "evidence", "evidence": "options",
        "options": "decision_ready", "decision_ready": "in_governance",
        "in_governance": "approved", "approved_with_conditions": "approved",
        "approved": "execute", "rejected": "options", "execute": "outcomes",
        "outcomes": "completed",
    }
    TERMINAL_STAGES = frozenset({"completed"})
    REQUIRED_RESOURCES = {
        ("discover", "evidence"): frozenset({"candidates", "evidence"}),
        ("evidence", "options"): frozenset({"evidence"}),
        ("options", "decision_ready"): frozenset({"options"}),
        ("decision_ready", "in_governance"): frozenset({"briefs", "evidence", "options"}),
        ("in_governance", "evidence"): frozenset({"arb", "briefs"}),
        ("in_governance", "options"): frozenset({"arb", "briefs"}),
        ("in_governance", "approved"): frozenset({"arb", "briefs"}),
        ("in_governance", "approved_with_conditions"): frozenset({"arb", "briefs", "conditions"}),
        ("in_governance", "rejected"): frozenset({"arb", "briefs"}),
        ("approved_with_conditions", "approved"): frozenset({"arb", "conditions", "evidence"}),
        ("approved", "execute"): frozenset({"approved_actions"}),
        ("execute", "outcomes"): frozenset({"delivery", "evidence"}),
        ("outcomes", "completed"): frozenset({"measurements", "outcome_reviews"}),
        ("outcomes", "execute"): frozenset({"delivery"}),
        ("rejected", "options"): frozenset({"arb"}),
    }

    @classmethod
    def evaluate(cls, *, actor: ActorContext, workstream_id: int, target_stage: str) -> GateResult:
        snapshot = cls.load_policy_snapshot(actor=actor, workstream_id=workstream_id)
        transition = cls.require_valid_transition(snapshot.workstream.lifecycle_stage, target_stage)
        blockers, warnings, evidence_ids = cls.evaluate_requirements(snapshot, transition)
        return GateResult(
            not blockers, transition.source, transition.target, cls.POLICY_VERSION,
            tuple(blockers), tuple(warnings), tuple(sorted(evidence_ids)),
        )

    @classmethod
    def transition(cls, *, actor: ActorContext, workstream_id: int, target_stage: str,
                   expected_revision: int, command_key: str) -> CommandResult:
        request = {"workstream_id": workstream_id, "target_stage": target_stage,
                   "expected_revision": expected_revision}
        return CommandService.execute(
            actor=actor, operation="workstream.transition", idempotency_key=command_key,
            payload=request,
            natural_key=f"transition:{workstream_id}:{expected_revision}:{target_stage}",
            authorizer=cls.authorise_transition(workstream_id, target_stage, expected_revision),
            handler=lambda session, claim: cls._locked_transition(session, actor, request, claim),
        )

    @classmethod
    def load_policy_snapshot(cls, *, actor: ActorContext, workstream_id: int) -> PolicySnapshot:
        with Session(db.engine) as session:
            snapshot = cls._load_policy_snapshot(
                session=session, actor=actor, workstream_id=workstream_id, lock=False
            )
            session.expunge_all()
            return snapshot

    @classmethod
    def _load_policy_snapshot(cls, *, session, actor, workstream_id, lock) -> PolicySnapshot:
        scope = session.execute(
            select(ProgrammeWorkstream).where(
                ProgrammeWorkstream.id == workstream_id,
                ProgrammeWorkstream.organization_id == actor.organization_id,
            )
        ).scalar_one_or_none()
        if scope is None:
            raise NotFound("workstream_not_found")
        programme = cls._programme_statement(
            session, actor, scope.programme_id, lock=lock
        ).scalar_one_or_none()
        if programme is None:
            raise NotFound("programme_not_found")
        TransformationProgrammeService._require_active_programme(programme)
        TransformationProgrammeService._require_programme_authority(
            session, actor, programme.id, scope.id, READ_ROLES,
            "programme_read_not_authorised",
        )
        if lock:
            workstream = session.execute(
                select(ProgrammeWorkstream).where(
                    ProgrammeWorkstream.id == scope.id,
                    ProgrammeWorkstream.programme_id == programme.id,
                    ProgrammeWorkstream.organization_id == actor.organization_id,
                ).with_for_update()
            ).scalar_one()
        else:
            workstream = scope
        roles = tuple(session.scalars(select(ProgrammeRoleAssignment).where(
            ProgrammeRoleAssignment.organization_id == actor.organization_id,
            ProgrammeRoleAssignment.programme_id == programme.id,
        )).all())
        outcomes = tuple(session.scalars(select(ProgrammeOutcomeCommitment).where(
            ProgrammeOutcomeCommitment.organization_id == actor.organization_id,
            ProgrammeOutcomeCommitment.programme_id == programme.id,
            (ProgrammeOutcomeCommitment.workstream_id == workstream.id)
            | (ProgrammeOutcomeCommitment.workstream_id.is_(None)),
        )).all())
        outcome_ids = [row.id for row in outcomes]
        measures = tuple(session.scalars(select(MeasureDefinition).where(
            MeasureDefinition.organization_id == actor.organization_id,
            MeasureDefinition.outcome_commitment_id.in_(outcome_ids or [-1]),
        )).all())
        work_packages = tuple(session.scalars(select(WorkPackage).where(
            WorkPackage.organization_id == actor.organization_id,
            WorkPackage.programme_workstream_id == workstream.id,
        )).all())
        roadmap_items = tuple(session.scalars(select(RoadmapItem).where(
            RoadmapItem.organization_id == actor.organization_id,
            RoadmapItem.programme_workstream_id == workstream.id,
        )).all())
        benefits = tuple(session.scalars(select(Benefit).where(
            Benefit.organization_id == actor.organization_id,
            Benefit.programme_workstream_id == workstream.id,
        )).all())
        unavailable = frozenset({
            "candidates", "evidence", "options", "briefs", "arb", "conditions",
            "approved_actions", "delivery", "measurements", "outcome_reviews",
        })
        return PolicySnapshot(
            programme, workstream, roles, outcomes, measures, (), (), (), (), (),
            (), (), (), (), (), (), work_packages, roadmap_items, benefits, (), (),
            (), unavailable,
        )

    @staticmethod
    def _programme_statement(session, actor, programme_id, *, lock):
        statement = select(StrategicInitiative).where(
            StrategicInitiative.id == programme_id,
            StrategicInitiative.organization_id == actor.organization_id,
            StrategicInitiative.record_kind == "transformation_programme",
        )
        if lock:
            statement = statement.with_for_update()
        return session.execute(statement)

    @classmethod
    def require_valid_transition(cls, current_stage: str, target_stage: str) -> Transition:
        if (current_stage, target_stage) not in cls.TRANSITIONS:
            raise CommandConflict("invalid_lifecycle_transition",
                                  current_stage=current_stage, target_stage=target_stage)
        return Transition(current_stage, target_stage)

    @classmethod
    def evaluate_requirements(cls, snapshot, transition):
        blockers: list[GateBlocker] = []
        warnings: list[GateBlocker] = []
        evidence_ids: set[int] = set()
        workstream_id = snapshot.workstream.id
        room = f"/solutions/programmes/{snapshot.programme.id}/workstreams/{workstream_id}"
        edge = (transition.source, transition.target)

        def block(code, message, resource_type=None, resource_id=None, action_url=None):
            blockers.append(GateBlocker(code, message, resource_type, resource_id, action_url))

        missing = sorted(cls.REQUIRED_RESOURCES.get(edge, frozenset()) & snapshot.unavailable_resources)
        if missing:
            for resource in missing:
                block("policy_resource_unavailable",
                      f"The canonical {resource.replace('_', ' ')} resource is not installed.",
                      resource, workstream_id, None)
            return blockers, warnings, evidence_ids

        handlers = {
            ("objective", "discover"): cls._evaluate_objective,
            ("discover", "evidence"): cls._evaluate_discovery,
            ("evidence", "options"): cls._evaluate_evidence,
            ("options", "decision_ready"): cls._evaluate_options,
            ("decision_ready", "in_governance"): cls._evaluate_brief,
            ("approved_with_conditions", "approved"): cls._evaluate_conditions,
            ("approved", "execute"): cls._evaluate_execution,
            ("execute", "outcomes"): cls._evaluate_delivery,
            ("outcomes", "completed"): cls._evaluate_completion,
            ("rejected", "options"): cls._evaluate_reframe,
        }
        if transition.source == "in_governance":
            cls._evaluate_governance(snapshot, transition, block, room)
        elif edge == ("outcomes", "execute"):
            if not any(_value(row, "workstream_id") == workstream_id
                       and _value(row, "corrective_action_approved") is True
                       for row in snapshot.delivery_records):
                block("corrective_action_required", "Record an approved corrective delivery action.",
                      "workstream", workstream_id, f"{room}/outcomes")
        else:
            handlers[edge](snapshot, block, room)
        for head in snapshot.active_evidence_heads:
            current_id = _value(head, "current_record_id")
            if current_id is not None:
                evidence_ids.add(current_id)
        for evidence in snapshot.evidence_records:
            if _value(evidence, "status") == "accepted" and _value(evidence, "id") is not None:
                evidence_ids.add(_value(evidence, "id"))
        return blockers, warnings, evidence_ids

    @classmethod
    def _evaluate_objective(cls, snapshot, block, room):
        programme_id, workstream_id = snapshot.programme.id, snapshot.workstream.id
        if snapshot.programme.owner_id is None:
            block("programme_owner_required", "Assign a programme owner.", "programme", programme_id, f"{room}/objective")
        if snapshot.workstream.lead_id is None:
            block("workstream_owner_required", "Assign a workstream owner.", "workstream", workstream_id, f"{room}/objective")
        if not _text(snapshot.workstream, "objective"):
            block("objective_required", "Record the business objective.", "workstream", workstream_id, f"{room}/objective")
        valid_outcomes = {row.id for row in snapshot.outcomes
                          if _value(row, "owner_id") and _text(row, "statement")}
        if not snapshot.outcomes:
            block("outcome_commitment_required", "Record an accountable outcome commitment.", "workstream", workstream_id, f"{room}/objective")
        elif not valid_outcomes:
            block("outcome_owner_required", "Name an accountable outcome owner.", "workstream", workstream_id, f"{room}/objective")
        invalid_values = any(not _finite(_value(row, field)) for row in snapshot.measures
                             for field in ("baseline_amount", "baseline_value", "target_amount", "target_value"))
        if invalid_values:
            block("measure_value_invalid", "Measure values must be finite.", "workstream", workstream_id, f"{room}/objective")
        else:
            valid_measures = [row for row in snapshot.measures
                              if _value(row, "outcome_commitment_id") in valid_outcomes
                              and _text(row, "metric_name") and _text(row, "unit")
                              and (_value(row, "target_amount") is not None or _value(row, "target_value") is not None)
                              and (_value(row, "baseline_amount") is not None
                                   or _value(row, "baseline_value") is not None
                                   or _text(row, "unavailable_reason"))]
            if not valid_measures:
                block("measure_definition_required", "Define a valid outcome measure.", "workstream", workstream_id, f"{room}/objective")
        if not _value(snapshot.workstream, "scope_expression"):
            block("scope_required", "Define the workstream scope.", "workstream", workstream_id, f"{room}/objective")
        if _value(snapshot.workstream, "target_date") is None and not _text(snapshot.workstream, "target_date_unavailable_reason"):
            block("target_date_required", "Record a target date or why it is unavailable.", "workstream", workstream_id, f"{room}/objective")

    @classmethod
    def _valid_waiver(cls, row):
        authority = _value(row, "approver_id", _value(row, "waiver_authority_id"))
        reason = _text(row, "reason") or _text(row, "waiver_reason")
        expiry = _value(row, "expires_at", _value(row, "waiver_expires_at"))
        return bool(authority and reason and _current(expiry))

    @classmethod
    def _evaluate_discovery(cls, snapshot, block, room):
        workstream_id = snapshot.workstream.id
        candidates = [row for row in snapshot.accepted_candidates
                      if _value(row, "workstream_id") == workstream_id
                      and _value(row, "organization_id", snapshot.programme.organization_id) == snapshot.programme.organization_id
                      and _value(row, "inclusion_status") == "accepted"]
        if not candidates or any(_value(row, "subject_exists") is not True
                                 or _value(row, "duplicates_resolved") is not True
                                 for row in candidates):
            block("candidate_scope_incomplete", "Accept valid in-tenant candidates and resolve duplicates.", "workstream", workstream_id, f"{room}/discover")
            return
        for candidate in candidates:
            owner_evidence = any(_value(row, "candidate_id") == candidate.id
                                 and _value(row, "claim_key") == "application_owner"
                                 and _value(row, "status") == "accepted"
                                 and _value(row, "freshness_status") == "fresh"
                                 and _value(row, "conflict_resolved") is True
                                 for row in snapshot.evidence_records)
            owner_waiver = any(_value(row, "candidate_id") == candidate.id
                               and _value(row, "claim_key") == "application_owner"
                               and cls._valid_waiver(row) and _value(row, "interim_owner_id")
                               for row in snapshot.evidence_waivers)
            if not owner_evidence and not owner_waiver:
                block("application_owner_evidence_required", "Resolve application ownership with accepted evidence or a controlled waiver.", "candidate", candidate.id, f"{room}/evidence")

    @classmethod
    def _evaluate_evidence(cls, snapshot, block, room):
        workstream_id = snapshot.workstream.id
        required_claims = {"application_owner", "lifecycle", "cost", "business_criticality",
                           "capability_impact", "dependency_impact", "risk", "source_freshness"}
        candidates = [row for row in snapshot.accepted_candidates if _value(row, "workstream_id") == workstream_id]
        requests_complete = bool(snapshot.evidence_requests) and all(
            not _value(row, "required", False)
            or (_value(row, "status") == "accepted" and _value(row, "accepted_evidence_id"))
            or (_value(row, "status") in {"declined", "unavailable"} and _value(row, "acknowledgement_id"))
            or (_value(row, "status") == "expired"
                and any(_value(waiver, "id") == _value(row, "waiver_id")
                        and cls._valid_waiver(waiver) for waiver in snapshot.evidence_waivers))
            for row in snapshot.evidence_requests)
        if not requests_complete:
            block("required_evidence_incomplete", "Complete or explicitly acknowledge every required evidence request.", "workstream", workstream_id, f"{room}/evidence")
        for candidate in candidates:
            records = [row for row in snapshot.evidence_records if _value(row, "candidate_id") == candidate.id]
            claims = {_value(row, "claim_key") for row in records if _value(row, "status") == "accepted"}
            if "application_owner" not in claims:
                block("application_owner_evidence_required", "Resolve application ownership.", "candidate", candidate.id, f"{room}/evidence")
            if not required_claims.issubset(claims):
                block("evidence_dimension_incomplete", "Evaluate every required evidence dimension.", "candidate", candidate.id, f"{room}/evidence")
            if any(_value(row, "conflict_resolved") is not True for row in records):
                block("evidence_conflict_unresolved", "Resolve or explicitly govern evidence conflicts.", "candidate", candidate.id, f"{room}/evidence")
            if any(_value(row, "freshness_status") != "fresh" for row in records):
                block("evidence_freshness_invalid", "Refresh or acknowledge stale evidence.", "candidate", candidate.id, f"{room}/evidence")

    @classmethod
    def _evaluate_options(cls, snapshot, block, room):
        workstream_id = snapshot.workstream.id
        options = [row for row in snapshot.option_versions if _value(row, "workstream_id") == workstream_id]
        exception = any(_value(row, "workstream_id") == workstream_id and _text(row, "reason")
                        and _value(row, "authority_id") and _value(row, "constraint_type") in {"policy", "legal"}
                        for row in snapshot.option_exceptions)
        hashes = {_value(row, "content_hash") for row in options
                  if _value(row, "immutable") is True and _value(row, "content_hash")}
        if len(hashes) < 2 and not (len(hashes) == 1 and exception):
            block("viable_options_required", "Freeze two distinct options or a reasoned policy/legal exception.", "workstream", workstream_id, f"{room}/options")
        required_fields = ("assumptions", "risks", "dependencies", "reversibility",
                           "transition_approach", "affected_capability_ids",
                           "affected_value_stream_ids", "recommendation_rationale")
        if any(_value(row, "immutable") is not True or not _value(row, "content_hash")
               or any(not _value(row, field) for field in required_fields)
               or _value(row, "currency") not in ISO_4217_CURRENCIES
               or _value(row, "technology_required") is None
               or any(_value(row, field) is None for field in ("benefit_min", "benefit_max", "cost_min", "cost_max"))
               for row in options):
            block("option_contract_incomplete", "Complete every immutable option contract.", "workstream", workstream_id, f"{room}/options")
        if any(not _finite(_value(row, field)) for row in options
               for field in ("benefit_min", "benefit_max", "cost_min", "cost_max")):
            block("option_value_invalid", "Option values must be finite.", "workstream", workstream_id, f"{room}/options")
        elif any(_value(row, "benefit_min") > _value(row, "benefit_max")
                 or _value(row, "cost_min") > _value(row, "cost_max") for row in options):
            block("option_value_invalid", "Option ranges must be ordered.", "workstream", workstream_id, f"{room}/options")

    @classmethod
    def _valid_briefs(cls, snapshot):
        evidence_ids = {_value(row, "id") for row in snapshot.evidence_records}
        option_ids = {_value(row, "id") for row in snapshot.option_versions}
        return [row for row in snapshot.brief_versions
                if _value(row, "workstream_id") == snapshot.workstream.id
                and _value(row, "immutable") is True and _value(row, "content_hash")
                and _value(row, "policy_version") == cls.POLICY_VERSION
                and bool(_value(row, "cited_evidence_ids", ()))
                and set(_value(row, "cited_evidence_ids", ())).issubset(evidence_ids)
                and bool(_value(row, "option_version_ids", ()))
                and set(_value(row, "option_version_ids", ())).issubset(option_ids)]

    @classmethod
    def _evaluate_brief(cls, snapshot, block, room):
        workstream_id = snapshot.workstream.id
        briefs = cls._valid_briefs(snapshot)
        if not briefs:
            block("immutable_brief_required", "Freeze a current evidence-cited decision brief.", "workstream", workstream_id, f"{room}/decision")
            return
        brief = briefs[-1]
        if not _value(brief, "submitted_by_id") or _value(brief, "submitter_authorized") is not True:
            block("brief_submitter_not_authorised", "Record an authorised brief submitter.", "brief", brief.id, f"{room}/decision")
        if _value(brief, "human_reviewed_ai") is not True:
            block("human_review_required", "Record explicit human review of AI-authored material.", "brief", brief.id, f"{room}/decision")
        if not _value(brief, "decision_authority_id"):
            block("decision_authority_required", "Name the decision authority.", "brief", brief.id, f"{room}/decision")
        if _value(brief, "blockers_cleared") is not True:
            block("decision_blockers_open", "Clear all decision blockers.", "brief", brief.id, f"{room}/decision")
        if _value(brief, "unknowns_acknowledged") is not True:
            block("decision_unknowns_unacknowledged", "Acknowledge non-blocking unknowns.", "brief", brief.id, f"{room}/decision")

    @classmethod
    def _evaluate_governance(cls, snapshot, transition, block, room):
        workstream_id = snapshot.workstream.id
        briefs = cls._valid_briefs(snapshot)
        brief_ids = {_value(row, "id") for row in briefs}
        subject_ids = {_value(row, "decision_brief_id") for row in briefs}
        decisions = {"evidence": "returned_for_evidence", "options": "returned_for_options",
                     "approved": "approved", "approved_with_conditions": "approved_with_conditions",
                     "rejected": "rejected"}
        matching = [cycle for cycle in snapshot.arb_cycles
                    if _value(cycle, "workstream_id") == workstream_id
                    and _value(cycle, "subject_type") == "decision_brief"
                    and _value(cycle, "brief_version_id") in brief_ids
                    and _value(cycle, "decision_brief_version_id", _value(cycle, "brief_version_id"))
                    == _value(cycle, "brief_version_id")
                    and _value(cycle, "subject_id") in subject_ids
                    and _value(cycle, "decision_brief_id") == _value(cycle, "subject_id")
                    and _value(cycle, "status") in {"decided", "terminal"}
                    and _value(cycle, "decision") == decisions[transition.target]
                    and _value(cycle, "target_stage") == transition.target
                    and _value(cycle, "decision_maker_id") and _text(cycle, "rationale")
                    and _value(cycle, "decided_at")]
        if not matching:
            block("arb_decision_mismatch", "Record a terminal ARB decision for the submitted brief and target stage.", "workstream", workstream_id, f"{room}/governance")
            return
        linked = [row for row in snapshot.arb_conditions if _value(row, "arb_cycle_id") == matching[-1].id]
        if transition.target == "approved" and linked:
            block("arb_decision_mismatch", "A decision with conditions must project to approved with conditions.", "workstream", workstream_id, f"{room}/governance")
        if transition.target == "approved_with_conditions" and not linked:
            block("arb_decision_mismatch", "Conditional approval requires persisted conditions.", "workstream", workstream_id, f"{room}/governance")

    @classmethod
    def _evaluate_conditions(cls, snapshot, block, room):
        workstream_id = snapshot.workstream.id
        cycle_ids = {_value(row, "id") for row in snapshot.arb_cycles
                     if _value(row, "workstream_id") == workstream_id
                     and _value(row, "decision") == "approved_with_conditions"}
        conditions = [row for row in snapshot.arb_conditions if _value(row, "arb_cycle_id") in cycle_ids]
        resolved = bool(conditions) and all(
            (_value(row, "status") == "fulfilled" and _value(row, "accepted_evidence_id"))
            or (_value(row, "status") == "waived" and cls._valid_waiver(row))
            for row in conditions)
        if not resolved:
            block("arb_conditions_open", "Fulfil or authoritatively waive every ARB condition.", "workstream", workstream_id, f"{room}/governance")

    @classmethod
    def _evaluate_execution(cls, snapshot, block, room):
        workstream_id = snapshot.workstream.id
        approved_versions = {
            _value(row, "decision_brief_version_id", _value(row, "brief_version_id"))
            for row in snapshot.arb_cycles
            if _value(row, "workstream_id") == workstream_id
            and _value(row, "decision") == "approved"
            and _value(row, "status") in {"decided", "terminal"}
        }
        work_packages = {_value(row, "id"): row for row in snapshot.work_packages
                         if _value(row, "programme_workstream_id", _value(row, "workstream_id")) == workstream_id
                         and _value(row, "owner_id")
                         and _value(row, "decision_brief_version_id") in approved_versions}
        roadmap_ids = {_value(row, "id") for row in snapshot.roadmap_items
                       if _value(row, "programme_workstream_id") == workstream_id
                       and _value(row, "work_package_id") in work_packages
                       and _value(row, "decision_brief_version_id") in approved_versions}
        action_ok = bool(snapshot.approved_actions) and all(
            _value(row, "workstream_id") == workstream_id
            and _value(row, "decision_brief_version_id") in approved_versions
            and ((_value(row, "status") == "declined" and _text(row, "decline_reason"))
                 or (_value(row, "status") == "accepted" and _value(row, "owner_id")
                     and _value(row, "work_package_id") in work_packages
                     and (not _value(row, "scheduling_applicable", False)
                          or _value(row, "roadmap_item_id") in roadmap_ids)))
            for row in snapshot.approved_actions)
        if not action_ok:
            block("approved_action_unresolved", "Resolve every approved action into declined rationale or owned scheduled work.", "workstream", workstream_id, f"{room}/execute")
        outcome_ids = {_value(row, "id") for row in snapshot.outcomes}
        measure_ids = {_value(row, "id") for row in snapshot.measures
                       if _value(row, "outcome_commitment_id") in outcome_ids}
        benefit_outcomes = {_value(row, "outcome_commitment_id") for row in snapshot.benefits
                            if _value(row, "programme_workstream_id") == workstream_id
                            and _value(row, "decision_brief_version_id") in approved_versions
                            and _value(row, "owner_id")
                            and _value(row, "measure_definition_id") in measure_ids
                            and (_value(row, "baseline_value") is not None
                                 or _text(row, "baseline_unavailable_reason"))
                            and _value(row, "target_value") is not None
                            and _finite(_value(row, "target_value"))
                            and _text(row, "measurement_method")}
        if not outcome_ids or not outcome_ids.issubset(benefit_outcomes):
            block("benefit_contract_incomplete", "Link each outcome to a complete canonical Benefit measurement contract.", "workstream", workstream_id, f"{room}/outcomes")

    @classmethod
    def _evaluate_delivery(cls, snapshot, block, room):
        workstream_id = snapshot.workstream.id
        if not any(_value(row, "workstream_id") == workstream_id
                   and _value(row, "completion_evidence_id") and _text(row, "residual_risk")
                   and _value(row, "operational_owner_id") and _text(row, "measurement_schedule")
                   for row in snapshot.delivery_records):
            block("delivery_completion_required", "Accept delivery evidence, residual risk, operational ownership and a measurement schedule.", "workstream", workstream_id, f"{room}/execute")

    @classmethod
    def _evaluate_completion(cls, snapshot, block, room):
        workstream_id = snapshot.workstream.id
        outcome_ids = {_value(row, "id") for row in snapshot.outcomes}
        benefits = [row for row in snapshot.benefits
                    if _value(row, "programme_workstream_id") == workstream_id
                    and _value(row, "outcome_commitment_id") in outcome_ids]
        measured = {(_value(row, "benefit_id"), _value(row, "outcome_commitment_id"))
                    for row in snapshot.measurements
                    if _value(row, "valid") is True and _value(row, "observed_at")
                    and ((_value(row, "value") is not None and _finite(_value(row, "value")))
                         or (_value(row, "value") is None and _text(row, "unavailable_reason")))}
        expected = {(_value(row, "id"), _value(row, "outcome_commitment_id")) for row in benefits}
        if not expected or not expected.issubset(measured):
            block("outcome_measurement_required", "Record a valid actual or explicit not-measurable result for each Benefit.", "workstream", workstream_id, f"{room}/outcomes")
        reviewed = {_value(row, "outcome_commitment_id") for row in snapshot.outcome_reviews
                    if _value(row, "workstream_id") == workstream_id
                    and _value(row, "judgement") in {"realised", "not_realised"}
                    and _text(row, "lessons") and _text(row, "follow_up_decision")}
        if not outcome_ids.issubset(reviewed):
            block("outcome_review_required", "Record judgement, lessons and follow-up for each outcome.", "workstream", workstream_id, f"{room}/outcomes")

    @classmethod
    def _evaluate_reframe(cls, snapshot, block, room):
        workstream_id = snapshot.workstream.id
        if not any(_value(row, "workstream_id") == workstream_id
                   and _value(row, "decision") == "reframe_authorised"
                   and _value(row, "target_stage") == "options"
                   and _value(row, "decision_maker_id") and _text(row, "rationale")
                   and _value(row, "decided_at") for row in snapshot.arb_cycles):
            block("reframe_authorisation_required", "Record decision-authority approval to reframe rejected options.", "workstream", workstream_id, f"{room}/governance")

    @classmethod
    def authorise_transition(cls, workstream_id, target_stage, expected_revision) -> OperationAuthorizer:
        expected_key = f"transition:{workstream_id}:{expected_revision}:{target_stage}"

        def authorize(session, actor, operation, natural_key):
            if operation != "workstream.transition" or natural_key != expected_key:
                raise NotAuthorised("transition_command_mismatch")
            workstream = session.execute(select(ProgrammeWorkstream).where(
                ProgrammeWorkstream.id == workstream_id,
                ProgrammeWorkstream.organization_id == actor.organization_id,
            )).scalar_one_or_none()
            if workstream is None:
                raise NotFound("workstream_not_found")
            programme = cls._programme_statement(
                session, actor, workstream.programme_id, lock=False
            ).scalar_one_or_none()
            if programme is None:
                raise NotFound("programme_not_found")
            TransformationProgrammeService._require_active_programme(programme)
            TransformationProgrammeService._require_programme_authority(
                session, actor, workstream.programme_id, workstream.id,
                cls._transition_roles(workstream.lifecycle_stage, target_stage),
                "transition_not_authorised",
            )
        return authorize

    @classmethod
    def _transition_roles(cls, source, target):
        if source == "in_governance":
            return CREATE_ROLES | frozenset({"decision_authority", "arb_member"})
        if source in {"approved", "approved_with_conditions", "execute"}:
            return CREATE_ROLES | frozenset({"programme_owner", "delivery_lead", "workstream_lead"})
        if source == "outcomes":
            return CREATE_ROLES | frozenset({"programme_owner", "outcome_owner", "workstream_lead"})
        return OBJECTIVE_ROLES

    @classmethod
    def _locked_transition(cls, session, actor, request, claim):
        snapshot = cls._load_policy_snapshot(
            session=session, actor=actor, workstream_id=request["workstream_id"], lock=True
        )
        workstream = snapshot.workstream
        if workstream.revision != request["expected_revision"]:
            raise CommandConflict("stale_revision")
        transition = cls.require_valid_transition(workstream.lifecycle_stage, request["target_stage"])
        TransformationProgrammeService._require_programme_authority(
            session, actor, workstream.programme_id, workstream.id,
            cls._transition_roles(transition.source, transition.target), "transition_not_authorised",
        )
        blockers, warnings, evidence_ids = cls.evaluate_requirements(snapshot, transition)
        if blockers:
            raise BlockedByEvidence("gate_requirements_not_met", blockers=tuple(blockers),
                                    warnings=tuple(warnings), policy_version=cls.POLICY_VERSION)
        before_revision = workstream.revision
        workstream.lifecycle_stage = transition.target
        workstream.revision += 1
        session.flush()
        response = {"workstream_id": workstream.id, "lifecycle_stage": workstream.lifecycle_stage,
                    "revision": workstream.revision, "policy_version": cls.POLICY_VERSION}
        return DomainMutationResult(
            response, response,
            ({"event_type": "workstream.transitioned",
              "payload": {**response, "source_stage": transition.source,
                          "before_revision": before_revision,
                          "evidence_ids": sorted(evidence_ids)}},),
        )

    @classmethod
    def next_action(cls, *, actor: ActorContext, workstreams: Sequence[ProgrammeWorkstream]):
        for workstream in sorted(workstreams, key=lambda row: row.id):
            programme = getattr(workstream, "programme", None)
            if programme is not None and (getattr(programme, "status", None) == "archived"
                                          or getattr(programme, "archived_at", None) is not None):
                return None
            if workstream.lifecycle_stage in cls.TERMINAL_STAGES:
                continue
            target = cls.NEXT_STAGE.get(workstream.lifecycle_stage)
            if target is None:
                return GateBlocker("lifecycle_action_required", "Choose the next governed lifecycle action.",
                                   "workstream", workstream.id,
                                   f"/solutions/programmes/{workstream.programme_id}/workstreams/{workstream.id}/{workstream.lifecycle_stage}")
            gate = cls.evaluate(actor=actor, workstream_id=workstream.id, target_stage=target)
            if gate.blockers:
                return gate.blockers[0]
            return GateBlocker("transition_ready", f"Advance this workstream to {target.replace('_', ' ')}.",
                               "workstream", workstream.id,
                               f"/solutions/programmes/{workstream.programme_id}/workstreams/{workstream.id}/{workstream.lifecycle_stage}")
        return None


__all__ = ["PolicySnapshot", "TransformationGateService", "Transition"]
