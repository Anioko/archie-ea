"""Pure, versioned Transformation Room lifecycle policy and locked transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.models.benefit import Benefit
from app.models.implementation_migration import WorkPackage
from app.models.strategic import RoadmapItem, StrategicInitiative
from app.models.transformation_programme import (
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
    TransformationProgrammeService,
)


@dataclass(frozen=True)
class Transition:
    source: str
    target: str


@dataclass(frozen=True)
class PolicySnapshot:
    programme: StrategicInitiative
    workstream: ProgrammeWorkstream
    role_assignments: tuple[ProgrammeRoleAssignment, ...]
    outcomes: tuple[ProgrammeOutcomeCommitment, ...]
    measures: tuple[MeasureDefinition, ...]
    accepted_candidates: tuple[object, ...]
    active_evidence_heads: tuple[object, ...]
    evidence_requests: tuple[object, ...]
    evidence_waivers: tuple[object, ...]
    option_versions: tuple[object, ...]
    brief_versions: tuple[object, ...]
    arb_cycles: tuple[object, ...]
    arb_conditions: tuple[object, ...]
    work_packages: tuple[WorkPackage, ...]
    roadmap_items: tuple[RoadmapItem, ...]
    benefits: tuple[Benefit, ...]
    measurements: tuple[object, ...]


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
        "objective": "discover",
        "discover": "evidence",
        "evidence": "options",
        "options": "decision_ready",
        "decision_ready": "in_governance",
        "in_governance": "approved",
        "approved_with_conditions": "approved",
        "approved": "execute",
        "rejected": "options",
        "execute": "outcomes",
        "outcomes": "completed",
    }
    TERMINAL_STAGES = frozenset({"completed"})

    @classmethod
    def evaluate(cls, *, actor: ActorContext, workstream_id: int, target_stage: str) -> GateResult:
        snapshot = cls.load_policy_snapshot(actor=actor, workstream_id=workstream_id)
        transition = cls.require_valid_transition(snapshot.workstream.lifecycle_stage, target_stage)
        blockers, warnings, evidence_ids = cls.evaluate_requirements(snapshot, transition)
        return GateResult(
            not blockers,
            transition.source,
            transition.target,
            cls.POLICY_VERSION,
            tuple(blockers),
            tuple(warnings),
            tuple(sorted(evidence_ids)),
        )

    @classmethod
    def transition(
        cls,
        *,
        actor: ActorContext,
        workstream_id: int,
        target_stage: str,
        expected_revision: int,
        command_key: str,
    ) -> CommandResult:
        request = {
            "workstream_id": workstream_id,
            "target_stage": target_stage,
            "expected_revision": expected_revision,
        }
        return CommandService.execute(
            actor=actor,
            operation="workstream.transition",
            idempotency_key=command_key,
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
        statement = select(ProgrammeWorkstream).where(
            ProgrammeWorkstream.id == workstream_id,
            ProgrammeWorkstream.organization_id == actor.organization_id,
        )
        if lock:
            statement = statement.with_for_update()
        workstream = session.execute(statement).scalar_one_or_none()
        if workstream is None:
            raise NotFound("workstream_not_found")
        programme = session.execute(
            select(StrategicInitiative).where(
                StrategicInitiative.id == workstream.programme_id,
                StrategicInitiative.organization_id == actor.organization_id,
                StrategicInitiative.record_kind == "transformation_programme",
            )
        ).scalar_one_or_none()
        if programme is None:
            raise NotFound("programme_not_found")
        roles = tuple(
            session.scalars(
                select(ProgrammeRoleAssignment).where(
                    ProgrammeRoleAssignment.organization_id == actor.organization_id,
                    ProgrammeRoleAssignment.programme_id == programme.id,
                )
            ).all()
        )
        outcomes = tuple(
            session.scalars(
                select(ProgrammeOutcomeCommitment).where(
                    ProgrammeOutcomeCommitment.organization_id == actor.organization_id,
                    ProgrammeOutcomeCommitment.programme_id == programme.id,
                    (ProgrammeOutcomeCommitment.workstream_id == workstream.id)
                    | (ProgrammeOutcomeCommitment.workstream_id.is_(None)),
                )
            ).all()
        )
        outcome_ids = [row.id for row in outcomes]
        measures = tuple(
            session.scalars(
                select(MeasureDefinition).where(
                    MeasureDefinition.organization_id == actor.organization_id,
                    MeasureDefinition.outcome_commitment_id.in_(outcome_ids or [-1]),
                )
            ).all()
        )
        work_packages = tuple(
            session.scalars(
                select(WorkPackage).where(
                    WorkPackage.organization_id == actor.organization_id,
                    WorkPackage.programme_workstream_id == workstream.id,
                )
            ).all()
        )
        roadmap_items = tuple(
            session.scalars(
                select(RoadmapItem).where(
                    RoadmapItem.organization_id == actor.organization_id,
                    RoadmapItem.programme_workstream_id == workstream.id,
                )
            ).all()
        )
        benefits = tuple(
            session.scalars(
                select(Benefit).where(
                    Benefit.organization_id == actor.organization_id,
                    Benefit.programme_workstream_id == workstream.id,
                )
            ).all()
        )
        # Tasks 5-9 add the remaining persisted policy resources. Keeping the
        # fields explicit here makes gate defaults fail closed until those
        # canonical rows exist and lets those tasks replace only their loaders.
        return PolicySnapshot(
            programme,
            workstream,
            roles,
            outcomes,
            measures,
            (),
            (),
            (),
            (),
            (),
            (),
            (),
            (),
            work_packages,
            roadmap_items,
            benefits,
            (),
        )

    @classmethod
    def require_valid_transition(cls, current_stage: str, target_stage: str) -> Transition:
        if (current_stage, target_stage) not in cls.TRANSITIONS:
            raise CommandConflict(
                "invalid_lifecycle_transition",
                current_stage=current_stage,
                target_stage=target_stage,
            )
        return Transition(current_stage, target_stage)

    @classmethod
    def evaluate_requirements(cls, snapshot, transition):
        blockers: list[GateBlocker] = []
        warnings: list[GateBlocker] = []
        evidence_ids: set[int] = set()

        def block(code, message, resource_type=None, resource_id=None, action_url=None):
            blockers.append(GateBlocker(code, message, resource_type, resource_id, action_url))

        programme_id = snapshot.programme.id
        workstream_id = snapshot.workstream.id
        room = f"/solutions/programmes/{programme_id}/workstreams/{workstream_id}"
        edge = (transition.source, transition.target)
        if edge == ("objective", "discover"):
            if snapshot.programme.owner_id is None:
                block("programme_owner_required", "Assign a programme owner.", "programme", programme_id, f"{room}/objective")
            if snapshot.workstream.lead_id is None:
                block("workstream_owner_required", "Assign a workstream owner.", "workstream", workstream_id, f"{room}/objective")
            if not (snapshot.workstream.objective or "").strip():
                block("objective_required", "Record the business objective.", "workstream", workstream_id, f"{room}/objective")
            if not snapshot.outcomes:
                block("outcome_commitment_required", "Record an accountable outcome commitment.", "workstream", workstream_id, f"{room}/objective")
            valid_outcomes = {row.id for row in snapshot.outcomes if row.owner_id and (row.statement or "").strip()}
            if snapshot.outcomes and not valid_outcomes:
                block("outcome_owner_required", "Name an accountable outcome owner.", "workstream", workstream_id, f"{room}/objective")
            valid_measures = [
                row
                for row in snapshot.measures
                if row.outcome_commitment_id in valid_outcomes
                and (row.metric_name or "").strip()
                and (row.unit or "").strip()
                and (row.target_amount is not None or row.target_value is not None)
                and (row.baseline_amount is not None or row.baseline_value is not None or (row.unavailable_reason or "").strip())
            ]
            if not valid_measures:
                block("measure_definition_required", "Define a valid outcome measure.", "workstream", workstream_id, f"{room}/objective")
            if not snapshot.workstream.scope_expression:
                block("scope_required", "Define the workstream scope.", "workstream", workstream_id, f"{room}/objective")
            if snapshot.workstream.target_date is None and not (
                snapshot.workstream.target_date_unavailable_reason or ""
            ).strip():
                block("target_date_required", "Record a target date or why it is unavailable.", "workstream", workstream_id, f"{room}/objective")
        elif edge == ("discover", "evidence"):
            if not snapshot.accepted_candidates:
                block("accepted_candidate_required", "Accept at least one in-tenant candidate.", "workstream", workstream_id, f"{room}/discover")
        elif edge == ("evidence", "options"):
            block("required_evidence_incomplete", "Complete or explicitly waive required evidence.", "workstream", workstream_id, f"{room}/evidence")
        elif edge == ("options", "decision_ready"):
            if len(snapshot.option_versions) < 2:
                block("viable_options_required", "Freeze at least two distinct options or an authorised exception.", "workstream", workstream_id, f"{room}/options")
        elif edge == ("decision_ready", "in_governance"):
            if not snapshot.brief_versions:
                block("immutable_brief_required", "Freeze an evidence-cited decision brief.", "workstream", workstream_id, f"{room}/decision")
        elif transition.source == "in_governance":
            if not snapshot.arb_cycles:
                block("arb_decision_required", "Record the canonical ARB decision.", "workstream", workstream_id, f"{room}/governance")
        elif edge == ("approved_with_conditions", "approved"):
            block("arb_conditions_open", "Fulfil or authoritatively waive every ARB condition.", "workstream", workstream_id, f"{room}/governance")
        elif edge == ("approved", "execute"):
            if not snapshot.work_packages:
                block("execution_plan_required", "Create owned execution work.", "workstream", workstream_id, f"{room}/execute")
            if len(snapshot.benefits) < len(snapshot.outcomes):
                block("benefit_plan_required", "Link every outcome to a canonical Benefit.", "workstream", workstream_id, f"{room}/outcomes")
        elif edge == ("execute", "outcomes"):
            block("delivery_completion_required", "Accept delivery completion evidence and measurement ownership.", "workstream", workstream_id, f"{room}/execute")
        elif edge == ("outcomes", "completed"):
            if not snapshot.measurements:
                block("outcome_measurement_required", "Record an actual measurement or explicit not-measurable outcome.", "workstream", workstream_id, f"{room}/outcomes")

        for head in snapshot.active_evidence_heads:
            current_id = getattr(head, "current_record_id", None)
            if current_id is not None:
                evidence_ids.add(current_id)
        return blockers, warnings, evidence_ids

    @classmethod
    def authorise_transition(cls, workstream_id, target_stage, expected_revision) -> OperationAuthorizer:
        expected_key = f"transition:{workstream_id}:{expected_revision}:{target_stage}"

        def authorize(session, actor, operation, natural_key):
            if operation != "workstream.transition" or natural_key != expected_key:
                raise NotAuthorised("transition_command_mismatch")
            workstream = session.execute(
                select(ProgrammeWorkstream).where(
                    ProgrammeWorkstream.id == workstream_id,
                    ProgrammeWorkstream.organization_id == actor.organization_id,
                )
            ).scalar_one_or_none()
            if workstream is None:
                raise NotFound("workstream_not_found")
            programme = session.scalar(
                select(StrategicInitiative.id).where(
                    StrategicInitiative.id == workstream.programme_id,
                    StrategicInitiative.organization_id == actor.organization_id,
                    StrategicInitiative.record_kind == "transformation_programme",
                )
            )
            if programme is None:
                raise NotFound("programme_not_found")
            TransformationProgrammeService._require_programme_authority(
                session,
                actor,
                workstream.programme_id,
                workstream.id,
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
            session=session,
            actor=actor,
            workstream_id=request["workstream_id"],
            lock=True,
        )
        workstream = snapshot.workstream
        if workstream.revision != request["expected_revision"]:
            raise CommandConflict("stale_revision")
        transition = cls.require_valid_transition(workstream.lifecycle_stage, request["target_stage"])
        TransformationProgrammeService._require_programme_authority(
            session,
            actor,
            workstream.programme_id,
            workstream.id,
            cls._transition_roles(transition.source, transition.target),
            "transition_not_authorised",
        )
        blockers, warnings, evidence_ids = cls.evaluate_requirements(snapshot, transition)
        if blockers:
            raise BlockedByEvidence(
                "gate_requirements_not_met",
                blockers=tuple(blockers),
                warnings=tuple(warnings),
                policy_version=cls.POLICY_VERSION,
            )
        before_revision = workstream.revision
        workstream.lifecycle_stage = transition.target
        workstream.revision += 1
        session.flush()
        response = {
            "workstream_id": workstream.id,
            "lifecycle_stage": workstream.lifecycle_stage,
            "revision": workstream.revision,
            "policy_version": cls.POLICY_VERSION,
        }
        return DomainMutationResult(
            response,
            response,
            (
                {
                    "event_type": "workstream.transitioned",
                    "payload": {
                        **response,
                        "source_stage": transition.source,
                        "before_revision": before_revision,
                        "evidence_ids": sorted(evidence_ids),
                    },
                },
            ),
        )

    @classmethod
    def next_action(cls, *, actor: ActorContext, workstreams: Sequence[ProgrammeWorkstream]):
        for workstream in sorted(workstreams, key=lambda row: row.id):
            if workstream.lifecycle_stage in cls.TERMINAL_STAGES:
                continue
            target = cls.NEXT_STAGE.get(workstream.lifecycle_stage)
            if target is None:
                return GateBlocker(
                    "lifecycle_action_required",
                    "Choose the next governed lifecycle action.",
                    "workstream",
                    workstream.id,
                    f"/solutions/programmes/{workstream.programme_id}/workstreams/{workstream.id}/{workstream.lifecycle_stage}",
                )
            gate = cls.evaluate(actor=actor, workstream_id=workstream.id, target_stage=target)
            if gate.blockers:
                return gate.blockers[0]
            return GateBlocker(
                f"advance_to_{target}",
                f"Advance this workstream to {target.replace('_', ' ')}.",
                "workstream",
                workstream.id,
                f"/solutions/programmes/{workstream.programme_id}/workstreams/{workstream.id}/{workstream.lifecycle_stage}",
            )
        return None


__all__ = ["PolicySnapshot", "TransformationGateService", "Transition"]
