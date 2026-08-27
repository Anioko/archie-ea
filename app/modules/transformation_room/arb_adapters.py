"""Tenant-safe adapters from governed subjects to immutable ARB evidence."""

from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from types import MappingProxyType
from types import SimpleNamespace
from typing import Any, Mapping, Protocol, runtime_checkable

from app import db
from app.models.adr import ArchitectureDecisionRecord
from app.models.architecture_review_board import ARBGovernanceStandard
from app.models.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel
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
        *,
        review_item_id: int | None = None,
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


def _readiness_document(readiness: ARBReadinessResult) -> dict[str, Any]:
    return {
        "ready": readiness.ready,
        "reason_codes": deepcopy(readiness.reason_codes),
        "missing_evidence": deepcopy(readiness.missing_evidence),
        "workflow_type": readiness.workflow_type,
        "checks": deepcopy(readiness.checks),
        "artifacts": deepcopy(readiness.artifacts),
        "governance_result": deepcopy(readiness.governance_result),
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


_ADAPTER_POLICY_ATTRIBUTES = frozenset(
    {"model_type", "subject_type", "policy_version", "review_type", "required_fields"}
)


class _ImmutableAdapterPolicyMeta(type):
    def __setattr__(cls, name, value):
        if name in _ADAPTER_POLICY_ATTRIBUTES:
            raise AttributeError("ARB adapter policy configuration is immutable")
        super().__setattr__(name, value)


class _ImmutableAdapter(metaclass=_ImmutableAdapterPolicyMeta):
    __slots__ = ()


class DecisionBriefARBAdapter(_ImmutableAdapter):
    __slots__ = ()
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

    def snapshot(self, actor, subject, readiness, *, review_item_id=None):
        del review_item_id
        self._require_current_subject(actor, subject)
        checks = readiness.checks if isinstance(readiness.checks, Mapping) else {}
        if (
            not readiness.ready
            or checks.get("human_reviewed") is not True
            or not isinstance(checks.get("gate_policy_version"), str)
            or not checks["gate_policy_version"]
        ):
            raise BlockedByEvidence("arb_subject_not_ready")
        current = decision_brief_arb_readiness(
            DecisionBriefService.evaluate(actor=actor, brief_id=subject.subject_id),
            {"human_reviewed": checks["human_reviewed"]},
        )
        if not current.ready or _readiness_document(current) != _readiness_document(readiness):
            raise CommandConflict("arb_readiness_stale")
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


class SolutionARBAdapter(_ImmutableAdapter):
    __slots__ = ("_evaluation_context",)
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

    def snapshot(self, actor, subject, readiness, *, review_item_id=None):
        self._require_current_subject(actor, subject, lock=True)
        if not readiness.ready:
            raise BlockedByEvidence("arb_subject_not_ready")
        context = self._evaluation_context.get()
        if (
            context is None
            or context["subject_id"] != subject.subject_id
            or context["actor_id"] != actor.user_id
        ):
            raise CommandConflict("solution_readiness_context_missing")
        current = ARBSubmissionService.evaluate(
            subject.subject_id,
            actor.user_id,
            context["workspace_id"],
            context["assertions"],
        )
        if not current.ready or _readiness_document(current) != _readiness_document(readiness):
            raise CommandConflict("arb_readiness_stale")
        snapshot = ARBSubmissionService.build_evidence_snapshot(
            organization_id=actor.organization_id,
            review_item_id=review_item_id,
            solution_id=subject.subject_id,
            actor_id=actor.user_id,
            workspace_id=context["workspace_id"],
            assertions=context["assertions"],
            readiness=readiness,
        )
        if snapshot.content_hash != snapshot.recompute_content_hash():
            raise CommandConflict("solution_evidence_hash_mismatch")
        return PinnedEvidence(
            "solution_evidence_snapshot", snapshot.id, snapshot.content_hash
        )

    def canonical_url(self, subject):
        _require_subject(subject, self.subject_type)
        return f"/solutions/{subject.subject_id}?tab=governance"

    @classmethod
    def _load_row(cls, actor, subject_id, *, lock=False):
        _require_actor_membership(actor)
        if isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0:
            raise _not_found()
        statement = db.select(Solution).where(
                Solution.id == subject_id,
                Solution.organization_id == actor.organization_id,
            )
        if lock:
            statement = statement.with_for_update(of=Solution)
        row = db.session.execute(statement).scalar_one_or_none()
        if row is None:
            raise _not_found()
        return row

    @classmethod
    def _require_current_subject(cls, actor, subject, *, lock=False):
        _require_subject(subject, cls.subject_type)
        if subject.organization_id != actor.organization_id:
            raise _not_found()
        return cls._load_row(actor, subject.subject_id, lock=lock)


def _canonical_value(value):
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
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


class _SubjectSnapshotAdapter(_ImmutableAdapter):
    __slots__ = ()
    model_type = None
    subject_type = ""
    policy_version = ""
    review_type = ""
    required_fields: tuple[str, ...] = ()

    def load(self, actor, subject_id):
        row = self._load_row(actor, subject_id)
        return GovernedSubject(
            self.subject_type, row.id, row.organization_id, row.name if hasattr(row, "name") else row.title, None
        )

    def evaluate(self, actor, subject, assertions):
        row = self._require_current_subject(actor, subject)
        return self._evaluate_row(row, assertions)

    def _evaluate_row(self, row, assertions, *, lock_evidence=False):
        reason_codes = []
        missing = []
        for field in self.required_fields:
            value = getattr(row, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                code = f"{self.subject_type}_{field}_required"
                reason_codes.append(code)
                missing.append({"code": code, "field": field})
        subject_payload, evidence_citations, subject_blockers = self._server_evidence(
            row, lock=lock_evidence
        )
        for blocker in subject_blockers:
            reason_codes.append(blocker["code"])
            missing.append(blocker)
        human_reviewed = (
            isinstance(assertions, Mapping) and assertions.get("human_reviewed") is True
        )
        if not human_reviewed:
            reason_codes.append("human_review_required")
            missing.append(
                {"code": "human_review_required", "assertion": "human_reviewed"}
            )
        standards = self._mandatory_standards(lock=lock_evidence)
        standard_results = [self._policy_entry(standard) for standard in standards]
        policy_digest = hashlib.sha256(
            json.dumps(
                standard_results,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        reason_codes = list(dict.fromkeys(reason_codes))
        subject_hash = hashlib.sha256(
            json.dumps(
                subject_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        return ARBReadinessResult(
            ready=not reason_codes,
            reason_codes=reason_codes,
            missing_evidence=missing,
            checks={
                "human_reviewed": human_reviewed,
                "required_fields": list(self.required_fields),
                "policy_version": self.policy_version,
                "policy_digest": policy_digest,
                "subject_hash": subject_hash,
                "subject_payload": subject_payload,
                "applicable_standard_ids": [item["standard_id"] for item in standard_results],
                "evidence_citations": evidence_citations,
            },
            governance_result={
                "policy_version": self.policy_version,
                "review_type": self.review_type,
                "mandatory_standards": standard_results,
                "standards_status": "pending_review",
                "supporting_evidence_count": len(evidence_citations),
            },
        )

    def snapshot(self, actor, subject, readiness, *, review_item_id=None):
        del review_item_id
        row = self._require_current_subject(actor, subject, lock=True)
        checks = readiness.checks if isinstance(readiness.checks, Mapping) else {}
        if not readiness.ready:
            raise BlockedByEvidence("arb_subject_not_ready")
        current = self._evaluate_row(
            row,
            {"human_reviewed": checks.get("human_reviewed") is True},
            lock_evidence=True,
        )
        if not current.ready or _readiness_document(current) != _readiness_document(readiness):
            raise CommandConflict("arb_readiness_stale")
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
            "payload": {
                "subject": deepcopy(current.checks["subject_payload"]),
                "readiness": {
                    key: deepcopy(value)
                    for key, value in current.checks.items()
                    if key != "subject_payload"
                },
                "governance_result": deepcopy(current.governance_result),
            },
            "citations": [
                {
                    "resource_type": self.subject_type,
                    "resource_id": row.id,
                    "content_hash": current.checks["subject_hash"],
                },
                {
                    "resource_type": "arb_policy_catalogue",
                    "resource_id": self.review_type,
                    "content_hash": current.checks["policy_digest"],
                    "policy_version": self.policy_version,
                },
                *deepcopy(current.checks["evidence_citations"]),
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

    def _load_row(self, actor, subject_id, *, lock=False):
        _require_actor_membership(actor)
        if isinstance(subject_id, bool) or not isinstance(subject_id, int) or subject_id <= 0:
            raise _not_found()
        statement = db.select(self.model_type).where(
                self.model_type.id == subject_id,
                self.model_type.organization_id == actor.organization_id,
            )
        if lock:
            statement = statement.with_for_update(of=self.model_type).execution_options(
                populate_existing=True
            )
        row = db.session.execute(statement).scalar_one_or_none()
        if row is None:
            raise _not_found()
        return row

    def _require_current_subject(self, actor, subject, *, lock=False):
        _require_subject(subject, self.subject_type)
        if subject.organization_id != actor.organization_id:
            raise _not_found()
        return self._load_row(actor, subject.subject_id, lock=lock)

    def _mandatory_standards(self, *, lock=False):
        statement = db.select(ARBGovernanceStandard).where(
                ARBGovernanceStandard.status == "active",
                ARBGovernanceStandard.mandatory.is_(True),
            )
        if lock:
            statement = statement.with_for_update(of=ARBGovernanceStandard).execution_options(
                populate_existing=True
            )
        rows = db.session.execute(statement).scalars()
        applicable = []
        for row in rows:
            types = row.applies_to_review_types
            if not types or self.review_type in types:
                applicable.append(row)
        return sorted(applicable, key=lambda row: (row.code, row.id))

    @staticmethod
    def _policy_entry(standard):
        return {
            "standard_id": standard.id,
            "standard_code": standard.code,
            "name": standard.name,
            "status": "pending_review",
            "requirements": _canonical_value(standard.requirements or []),
            "checklist_items": _canonical_value(standard.checklist_items or []),
            "effective_date": _canonical_value(standard.effective_date),
            "review_date": _canonical_value(standard.review_date),
            "updated_at": _canonical_value(standard.updated_at),
        }

    def _server_evidence(self, row, *, lock=False):
        raise NotImplementedError


class ArchitectureModelARBAdapter(_SubjectSnapshotAdapter):
    __slots__ = ()
    subject_type = "architecture_model"
    model_type = ArchitectureModel
    policy_version = "architecture-model-arb-r2"
    review_type = "technology_selection"
    required_fields = ("name", "version")

    @staticmethod
    def _canonical_url(_subject_id):
        return "/architecture/models"

    def _server_evidence(self, row, *, lock=False):
        from app.modules.architecture.services.archimate_validator import ArchiMateValidator

        element_statement = db.select(ArchiMateElement).where(
            ArchiMateElement.architecture_id == row.id,
            ArchiMateElement.organization_id == row.organization_id,
        ).order_by(ArchiMateElement.id)
        relationship_statement = db.select(ArchiMateRelationship).where(
            ArchiMateRelationship.architecture_id == row.id,
            ArchiMateRelationship.organization_id == row.organization_id,
        ).order_by(ArchiMateRelationship.id)
        if lock:
            element_statement = element_statement.with_for_update(
                of=ArchiMateElement
            ).execution_options(populate_existing=True)
            relationship_statement = relationship_statement.with_for_update(
                of=ArchiMateRelationship
            ).execution_options(populate_existing=True)
        element_rows = list(db.session.execute(element_statement).scalars())
        relationship_rows = list(db.session.execute(relationship_statement).scalars())
        elements = sorted(
            (_complete_payload(item) for item in element_rows), key=lambda item: item["id"]
        )
        relationships = sorted(
            (_complete_payload(item) for item in relationship_rows),
            key=lambda item: item["id"],
        )
        validation_subject = SimpleNamespace(
            id=row.id,
            elements=element_rows,
            relationships=relationship_rows,
        )
        validation = _canonical_value(
            ArchiMateValidator().validate_model(validation_subject)
        )
        blockers = []
        if not elements:
            blockers.append({"code": "architecture_model_elements_required"})
        if not validation.get("is_valid"):
            blockers.append(
                {
                    "code": "architecture_model_validation_failed",
                    "element_errors": validation.get("element_errors", []),
                    "relationship_errors": validation.get("relationship_errors", []),
                }
            )
        payload = {
            "id": row.id,
            "name": row.name,
            "version": row.version,
            "solution_id": row.solution_id,
            "elements": elements,
            "relationships": relationships,
            "validation": validation,
        }
        validation_hash = hashlib.sha256(
            json.dumps(validation, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return payload, [
            {
                "resource_type": "archimate_validation",
                "resource_id": row.id,
                "content_hash": validation_hash,
                "validator_version": "archimate-validator-r1",
            }
        ], blockers


class ADRARBAdapter(_SubjectSnapshotAdapter):
    __slots__ = ()
    subject_type = "adr"
    model_type = ArchitectureDecisionRecord
    policy_version = "adr-arb-r2"
    review_type = "architecture_change"
    required_fields = ("title", "context", "decision", "rationale", "consequences")

    @staticmethod
    def _canonical_url(subject_id):
        return f"/architecture/adrs/records/{subject_id}"

    def _server_evidence(self, row, *, lock=False):
        blockers = []
        if row.status != "proposed" or row.review_status not in {None, "pending", "changes-requested"}:
            blockers.append(
                {
                    "code": "adr_state_not_submittable",
                    "status": row.status,
                    "review_status": row.review_status,
                }
            )
        for field in (
            "alternatives_considered",
            "stakeholders",
            "affected_systems",
            "related_adr_ids",
            "tags",
            "risks",
        ):
            value = getattr(row, field, None)
            if value is None or not str(value).strip():
                continue
            try:
                json.loads(value)
            except (TypeError, ValueError):
                blockers.append({"code": "adr_json_invalid", "field": field})
        if row.architecture_model_id is not None:
            linked_model_statement = db.select(ArchitectureModel).where(
                    ArchitectureModel.id == row.architecture_model_id,
                    ArchitectureModel.organization_id == row.organization_id,
                )
            if lock:
                linked_model_statement = linked_model_statement.with_for_update(
                    of=ArchitectureModel
                ).execution_options(populate_existing=True)
            linked_model = db.session.execute(linked_model_statement).scalar_one_or_none()
            if linked_model is None:
                blockers.append({"code": "adr_architecture_model_outside_tenant"})
        if row.solution_id is not None:
            linked_solution_statement = db.select(Solution).where(
                    Solution.id == row.solution_id,
                    Solution.organization_id == row.organization_id,
                )
            if lock:
                linked_solution_statement = linked_solution_statement.with_for_update(
                    of=Solution
                ).execution_options(populate_existing=True)
            linked_solution = db.session.execute(linked_solution_statement).scalar_one_or_none()
            if linked_solution is None:
                blockers.append({"code": "adr_solution_outside_tenant"})
        linked_adr_ids = []
        for field in ("related_adr_ids",):
            raw = getattr(row, field, None)
            if raw:
                try:
                    parsed = json.loads(raw)
                except (TypeError, ValueError):
                    parsed = []
                if isinstance(parsed, list):
                    linked_adr_ids.extend(item for item in parsed if isinstance(item, int))
        linked_adr_ids.extend(
            item
            for item in (row.supersedes_adr_id, row.superseded_by_adr_id)
            if item is not None
        )
        linked_adr_ids = sorted(set(linked_adr_ids))
        if row.id in linked_adr_ids:
            blockers.append({"code": "adr_self_reference"})
        if linked_adr_ids:
            linked_adrs_statement = db.select(ArchitectureDecisionRecord).where(
                        ArchitectureDecisionRecord.id.in_(linked_adr_ids),
                        ArchitectureDecisionRecord.organization_id == row.organization_id,
                    )
            if lock:
                linked_adrs_statement = linked_adrs_statement.with_for_update(
                    of=ArchitectureDecisionRecord
                ).execution_options(populate_existing=True)
            linked_adrs = list(db.session.execute(linked_adrs_statement).scalars())
            resolved = {item.id for item in linked_adrs}
            if resolved != set(linked_adr_ids):
                blockers.append({"code": "adr_link_outside_tenant_or_missing"})
        payload = _complete_payload(row)
        payload.pop("governance_blob", None)
        linked_resources = []
        for resource_type, resource in (
            ("architecture_model", locals().get("linked_model")),
            ("solution", locals().get("linked_solution")),
        ):
            if resource is not None:
                content = _complete_payload(resource)
                linked_resources.append(
                    {
                        "resource_type": resource_type,
                        "resource_id": resource.id,
                        "content_hash": hashlib.sha256(
                            json.dumps(
                                content,
                                sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False,
                                default=str,
                            ).encode("utf-8")
                        ).hexdigest(),
                    }
                )
        for linked_adr in sorted(locals().get("linked_adrs", []), key=lambda item: item.id):
            content = _complete_payload(linked_adr)
            content.pop("governance_blob", None)
            linked_resources.append(
                {
                    "resource_type": "adr",
                    "resource_id": linked_adr.id,
                    "content_hash": hashlib.sha256(
                        json.dumps(
                            content,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                            default=str,
                        ).encode("utf-8")
                    ).hexdigest(),
                }
            )
        payload["resolved_links"] = deepcopy(linked_resources)
        return payload, linked_resources, blockers


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


ARB_SUBJECT_ADAPTERS: Mapping[str, ARBSubjectAdapter] = MappingProxyType(_ADAPTERS)


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
