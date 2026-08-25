"""Tenant-safe adapters from governed subjects to immutable ARB evidence."""

from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping, Protocol, runtime_checkable

from app import db
from app.models.adr import ArchitectureDecisionRecord
from app.models.arb_submission_evidence import ARBSubmissionEvidenceSnapshot
from app.models.models import ArchitectureModel
from app.models.solution_models import Solution
from app.models.transformation_decision import ARBSubjectEvidenceSnapshot
from app.models.user import User
from app.modules.solutions_strategic.v2.services.arb_submission_service import (
    ARBReadinessResult,
    ARBSubmissionService,
)
from app.modules.transformation_room.decision_service import DecisionBriefService
from app.modules.transformation_room.domain import (
    ActorContext,
    BlockedByEvidence,
    BriefReadiness,
    CommandConflict,
    GovernedSubject,
    NotAuthorised,
    NotFound,
    PinnedEvidence,
)


@runtime_checkable
class ARBSubjectAdapter(Protocol):
    """Operations every typed ARB subject must implement."""

    subject_type: str

    def load(self, actor: ActorContext, subject_id: int) -> GovernedSubject: ...

    def evaluate(
        self,
        actor: ActorContext,
        subject: GovernedSubject,
        assertions: Mapping[str, Any],
    ) -> ARBReadinessResult: ...

    def snapshot(
        self,
        actor: ActorContext,
        subject: GovernedSubject,
        readiness: ARBReadinessResult,
    ) -> PinnedEvidence: ...

    def canonical_url(self, subject: GovernedSubject) -> str: ...


def _not_found() -> NotFound:
    # One response for unsupported, malformed, mismatched, and foreign subjects
    # prevents the adapter boundary from becoming an existence oracle.
    return NotFound("arb_subject_not_found")


def _require_subject(subject: GovernedSubject, subject_type: str) -> None:
    if (
        not isinstance(subject, GovernedSubject)
        or subject.subject_type != subject_type
        or isinstance(subject.subject_id, bool)
        or not isinstance(subject.subject_id, int)
        or subject.subject_id <= 0
        or isinstance(subject.organization_id, bool)
        or not isinstance(subject.organization_id, int)
        or subject.organization_id <= 0
    ):
        raise _not_found()


def _require_actor_membership(actor: ActorContext) -> None:
    user_id = getattr(actor, "user_id", None)
    organization_id = getattr(actor, "organization_id", None)
    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or user_id <= 0
        or isinstance(organization_id, bool)
        or not isinstance(organization_id, int)
        or organization_id <= 0
    ):
        raise _not_found()
    membership = db.session.execute(
        db.select(User.id).where(
            User.id == user_id,
            User.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise _not_found()


def _blocker_document(blocker) -> dict[str, Any]:
    return {
        "code": blocker.code,
        "message": blocker.message,
        "resource_type": blocker.resource_type,
        "resource_id": blocker.resource_id,
        "action_url": blocker.action_url,
    }


def decision_brief_arb_readiness(
    readiness: BriefReadiness, assertions: Mapping[str, Any]
) -> ARBReadinessResult:
    """Convert server gate truth plus one explicit human-review assertion."""
    supplied = assertions if isinstance(assertions, Mapping) else {}
    blockers = [_blocker_document(item) for item in readiness.gate.blockers]
    reason_codes = [item["code"] for item in blockers]
    human_reviewed = supplied.get("human_reviewed") is True
    if not human_reviewed:
        reason_codes.append("human_review_required")
        blockers.append(
            {
                "code": "human_review_required",
                "assertion": "human_reviewed",
            }
        )
    governance_result = {
        "allowed": readiness.gate.allowed,
        "current_stage": readiness.gate.current_stage,
        "target_stage": readiness.gate.target_stage,
        "policy_version": readiness.gate.policy_version,
        "blockers": [_blocker_document(item) for item in readiness.gate.blockers],
        "warnings": [_blocker_document(item) for item in readiness.gate.warnings],
        "evidence_ids": list(readiness.gate.evidence_ids),
    }
    return ARBReadinessResult(
        ready=bool(readiness.ready and readiness.gate.allowed and human_reviewed),
        reason_codes=reason_codes,
        missing_evidence=blockers,
        checks={
            "human_reviewed": human_reviewed,
            "gate_policy_version": readiness.gate.policy_version,
            "option_version_ids": list(readiness.option_version_ids),
            "evidence_ids": list(readiness.evidence_ids),
        },
        governance_result=governance_result,
    )


def _load_decision_brief_workstream(subject: GovernedSubject):
    from app.models.transformation_decision import DecisionBrief
    from app.models.transformation_programme import ProgrammeWorkstream

    _require_subject(subject, "decision_brief")
    brief = db.session.execute(
        db.select(DecisionBrief).where(
            DecisionBrief.id == subject.subject_id,
            DecisionBrief.organization_id == subject.organization_id,
        )
    ).scalar_one_or_none()
    if brief is None:
        raise _not_found()
    workstream = db.session.execute(
        db.select(ProgrammeWorkstream).where(
            ProgrammeWorkstream.id == brief.workstream_id,
            ProgrammeWorkstream.organization_id == subject.organization_id,
        )
    ).scalar_one_or_none()
    if workstream is None:
        raise _not_found()
    return workstream


def load_programme_id(subject: GovernedSubject) -> int:
    """Resolve the programme behind an already tenant-validated brief subject."""
    return _load_decision_brief_workstream(subject).programme_id


def load_workstream_id(subject: GovernedSubject) -> int:
    """Resolve the workstream behind an already tenant-validated brief subject."""
    return _load_decision_brief_workstream(subject).id


class DecisionBriefARBAdapter:
    subject_type = "decision_brief"

    def load(self, actor: ActorContext, subject_id: int) -> GovernedSubject:
        try:
            brief = DecisionBriefService.load_brief_for_tenant(actor, subject_id)
            version = DecisionBriefService.require_latest_frozen_version(brief)
        except (NotAuthorised, NotFound, ValueError) as error:
            raise _not_found() from error
        return GovernedSubject(
            self.subject_type,
            brief.id,
            brief.organization_id,
            brief.title,
            version.id,
        )

    def evaluate(self, actor, subject, assertions):
        self._require_current_subject(actor, subject)
        readiness = DecisionBriefService.evaluate(
            actor=actor, brief_id=subject.subject_id
        )
        return decision_brief_arb_readiness(readiness, assertions)

    def snapshot(self, actor, subject, readiness):
        self._require_current_subject(actor, subject)
        checks = readiness.checks if isinstance(readiness.checks, Mapping) else {}
        if (
            not readiness.ready
            or checks.get("human_reviewed") is not True
            or not isinstance(checks.get("gate_policy_version"), str)
            or not checks["gate_policy_version"]
        ):
            raise BlockedByEvidence("arb_subject_not_ready")
        version = self._load_version(actor, subject.logical_version_id)
        if not DecisionBriefService.verify_hash(version):
            raise CommandConflict("decision_brief_hash_mismatch")
        return PinnedEvidence("decision_brief_version", version.id, version.content_hash)

    def canonical_url(self, subject):
        _require_subject(subject, self.subject_type)
        return (
            f"/solutions/programmes/{load_programme_id(subject)}/workstreams/"
            f"{load_workstream_id(subject)}/decision"
        )

    @staticmethod
    def _load_version(actor, version_id):
        if version_id is None:
            raise _not_found()
        try:
            return DecisionBriefService.require_version_for_tenant(actor, version_id)
        except (NotAuthorised, NotFound, ValueError) as error:
            raise _not_found() from error

    @classmethod
    def _require_current_subject(cls, actor, subject):
        _require_subject(subject, cls.subject_type)
        if subject.organization_id != actor.organization_id:
            raise _not_found()
        try:
            brief = DecisionBriefService.load_brief_for_tenant(actor, subject.subject_id)
            version = DecisionBriefService.require_latest_frozen_version(brief)
        except (NotAuthorised, NotFound, ValueError) as error:
            raise _not_found() from error
        if version.id != subject.logical_version_id:
            raise _not_found()
        return brief, version


class SolutionARBAdapter:
    """Compatibility adapter over the existing Solution ARB implementation."""

    subject_type = "solution"

    def __init__(self):
        self._evaluation_context: ContextVar[dict[str, Any] | None] = ContextVar(
            f"solution_arb_adapter_context_{id(self)}", default=None
        )

    def load(self, actor, subject_id):
        row = self._load_row(actor, subject_id)
        return GovernedSubject(
            self.subject_type, row.id, row.organization_id, row.name, None
        )

    def evaluate(self, actor, subject, assertions):
        self._require_current_subject(actor, subject)
        supplied = deepcopy(dict(assertions)) if isinstance(assertions, Mapping) else {}
        workspace_id = supplied.pop("workspace_id", None)
        result = ARBSubmissionService.evaluate(
            subject.subject_id,
            actor.user_id,
            workspace_id,
            supplied,
        )
        self._evaluation_context.set(
            {
                "subject_id": subject.subject_id,
                "actor_id": actor.user_id,
                "workspace_id": workspace_id,
                "assertions": supplied,
            }
        )
        return result

    def snapshot(self, actor, subject, readiness):
        self._require_current_subject(actor, subject)
        if not readiness.ready:
            raise BlockedByEvidence("arb_subject_not_ready")
        context = self._evaluation_context.get()
        if (
            context is None
            or context["subject_id"] != subject.subject_id
            or context["actor_id"] != actor.user_id
        ):
            raise CommandConflict("solution_readiness_context_missing")
        submitted = ARBSubmissionService.submit(
            subject.subject_id,
            actor.user_id,
            context["workspace_id"],
            context["assertions"],
        )
        if not submitted.success or submitted.snapshot_id is None:
            reason = submitted.reason_codes[0] if submitted.reason_codes else "submission_failed"
            raise CommandConflict(reason)
        snapshot = db.session.execute(
            db.select(ARBSubmissionEvidenceSnapshot).where(
                ARBSubmissionEvidenceSnapshot.id == submitted.snapshot_id,
                ARBSubmissionEvidenceSnapshot.organization_id == actor.organization_id,
                ARBSubmissionEvidenceSnapshot.solution_id == subject.subject_id,
            )
        ).scalar_one_or_none()
        if snapshot is None or snapshot.content_hash != snapshot.recompute_content_hash():
            raise CommandConflict("solution_evidence_hash_mismatch")
        return PinnedEvidence(
            "solution_evidence_snapshot", snapshot.id, snapshot.content_hash
        )

    def canonical_url(self, subject):
        _require_subject(subject, self.subject_type)
        return f"/solutions/{subject.subject_id}?tab=governance"

    @classmethod
    def _load_row(cls, actor, subject_id):
        _require_actor_membership(actor)
        if isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0:
            raise _not_found()
        row = db.session.execute(
            db.select(Solution).where(
                Solution.id == subject_id,
                Solution.organization_id == actor.organization_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise _not_found()
        return row

    @classmethod
    def _require_current_subject(cls, actor, subject):
        _require_subject(subject, cls.subject_type)
        if subject.organization_id != actor.organization_id:
            raise _not_found()
        return cls._load_row(actor, subject.subject_id)


def _canonical_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


def _complete_payload(row) -> dict[str, Any]:
    return {
        column.name: _canonical_value(getattr(row, column.name))
        for column in row.__table__.columns
    }


class _SubjectSnapshotAdapter:
    model_type = None
    subject_type = ""
    policy_version = ""
    required_fields: tuple[str, ...] = ()

    def load(self, actor, subject_id):
        row = self._load_row(actor, subject_id)
        return GovernedSubject(
            self.subject_type, row.id, row.organization_id, row.name if hasattr(row, "name") else row.title, None
        )

    def evaluate(self, actor, subject, assertions):
        row = self._require_current_subject(actor, subject)
        reason_codes = []
        missing = []
        for field in self.required_fields:
            value = getattr(row, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                code = f"{self.subject_type}_{field}_required"
                reason_codes.append(code)
                missing.append({"code": code, "field": field})
        human_reviewed = (
            isinstance(assertions, Mapping) and assertions.get("human_reviewed") is True
        )
        if not human_reviewed:
            reason_codes.append("human_review_required")
            missing.append(
                {"code": "human_review_required", "assertion": "human_reviewed"}
            )
        return ARBReadinessResult(
            ready=not reason_codes,
            reason_codes=reason_codes,
            missing_evidence=missing,
            checks={
                "human_reviewed": human_reviewed,
                "required_fields": list(self.required_fields),
                "policy_version": self.policy_version,
            },
            governance_result={"policy_version": self.policy_version},
        )

    def snapshot(self, actor, subject, readiness):
        row = self._require_current_subject(actor, subject)
        current_fields_complete = all(
            value is not None and (not isinstance(value, str) or bool(value.strip()))
            for value in (getattr(row, field, None) for field in self.required_fields)
        )
        checks = readiness.checks if isinstance(readiness.checks, Mapping) else {}
        if (
            not readiness.ready
            or not current_fields_complete
            or checks.get("human_reviewed") is not True
            or checks.get("policy_version") != self.policy_version
        ):
            raise BlockedByEvidence("arb_subject_not_ready")
        # Use the database timestamp, including its rendered UTC offset, so the
        # immutable hash is identical before and after PostgreSQL round-trips.
        captured_at = db.session.scalar(db.select(db.func.clock_timestamp()))
        values = {
            "organization_id": actor.organization_id,
            "subject_type": self.subject_type,
            "subject_id": row.id,
            "architecture_model_id": row.id
            if self.subject_type == "architecture_model"
            else None,
            "adr_id": row.id if self.subject_type == "adr" else None,
            "schema_version": 1,
            "policy_version": self.policy_version,
            "captured_by_id": actor.user_id,
            "captured_at": captured_at,
            "payload": _complete_payload(row),
            "citations": [
                {"resource_type": self.subject_type, "resource_id": row.id}
            ],
        }
        snapshot = ARBSubjectEvidenceSnapshot(**values)
        snapshot.content_hash = snapshot.recompute_content_hash()
        db.session.add(snapshot)
        db.session.flush()
        return PinnedEvidence(
            "arb_subject_evidence_snapshot", snapshot.id, snapshot.content_hash
        )

    def canonical_url(self, subject):
        _require_subject(subject, self.subject_type)
        return self._canonical_url(subject.subject_id)

    def _load_row(self, actor, subject_id):
        _require_actor_membership(actor)
        if isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0:
            raise _not_found()
        row = db.session.execute(
            db.select(self.model_type).where(
                self.model_type.id == subject_id,
                self.model_type.organization_id == actor.organization_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise _not_found()
        return row

    def _require_current_subject(self, actor, subject):
        _require_subject(subject, self.subject_type)
        if subject.organization_id != actor.organization_id:
            raise _not_found()
        return self._load_row(actor, subject.subject_id)


class ArchitectureModelARBAdapter(_SubjectSnapshotAdapter):
    subject_type = "architecture_model"
    model_type = ArchitectureModel
    policy_version = "architecture-model-arb-r1"
    required_fields = ("name", "version", "model_data")

    @staticmethod
    def _canonical_url(_subject_id):
        return "/architecture/models"


class ADRARBAdapter(_SubjectSnapshotAdapter):
    subject_type = "adr"
    model_type = ArchitectureDecisionRecord
    policy_version = "adr-arb-r1"
    required_fields = ("title", "context", "decision", "rationale", "consequences")

    @staticmethod
    def _canonical_url(subject_id):
        return f"/architecture/adrs/{subject_id}"


_ADAPTERS: dict[str, ARBSubjectAdapter] = {
    "decision_brief": DecisionBriefARBAdapter(),
    "solution": SolutionARBAdapter(),
    "architecture_model": ArchitectureModelARBAdapter(),
    "adr": ADRARBAdapter(),
}


def get_arb_subject_adapter(subject_type: str) -> ARBSubjectAdapter:
    if not isinstance(subject_type, str):
        raise _not_found()
    try:
        return _ADAPTERS[subject_type]
    except KeyError as error:
        raise _not_found() from error


ARB_SUBJECT_ADAPTERS: Mapping[str, ARBSubjectAdapter] = _ADAPTERS


__all__ = [
    "ADRARBAdapter",
    "ARBSubjectAdapter",
    "ARB_SUBJECT_ADAPTERS",
    "ArchitectureModelARBAdapter",
    "DecisionBriefARBAdapter",
    "SolutionARBAdapter",
    "decision_brief_arb_readiness",
    "get_arb_subject_adapter",
    "load_programme_id",
    "load_workstream_id",
]
