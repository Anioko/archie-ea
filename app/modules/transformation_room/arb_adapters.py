"""Tenant-safe adapters from governed subjects to immutable ARB evidence."""

from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping, Protocol, runtime_checkable

from app import db
from app.models.adr import ArchitectureDecisionRecord
from app.models.architecture_review_board import ARBGovernanceStandard
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

    def _evaluate_row(self, row, assertions):
        reason_codes = []
        missing = []
        for field in self.required_fields:
            value = getattr(row, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                code = f"{self.subject_type}_{field}_required"
                reason_codes.append(code)
                missing.append({"code": code, "field": field})
        dossier, subject_blockers = self._governance_dossier(row)
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
        supplied_policy = dossier.get("policy_version") if isinstance(dossier, Mapping) else None
        if supplied_policy != self.policy_version:
            reason_codes.append("arb_policy_version_mismatch")
            missing.append(
                {
                    "code": "arb_policy_version_mismatch",
                    "expected": self.policy_version,
                    "actual": supplied_policy,
                }
            )
        standards = self._mandatory_standards()
        supplied_standards = dossier.get("standards") if isinstance(dossier, Mapping) else None
        supplied_standards = supplied_standards if isinstance(supplied_standards, list) else []
        satisfied_standard_ids = []
        standard_results = []
        for standard in standards:
            satisfied = any(
                isinstance(item, Mapping)
                and item.get("standard_id") == standard.id
                and item.get("standard_code") == standard.code
                and item.get("satisfied") is True
                for item in supplied_standards
            )
            standard_results.append(
                {
                    "standard_id": standard.id,
                    "standard_code": standard.code,
                    "satisfied": satisfied,
                }
            )
            if satisfied:
                satisfied_standard_ids.append(standard.id)
            else:
                reason_codes.append("mandatory_standard_unsatisfied")
                missing.append(
                    {
                        "code": "mandatory_standard_unsatisfied",
                        "standard_id": standard.id,
                        "standard_code": standard.code,
                    }
                )
        evidence, evidence_blockers = self._supporting_evidence(dossier)
        for blocker in evidence_blockers:
            reason_codes.append(blocker["code"])
            missing.append(blocker)
        reason_codes = list(dict.fromkeys(reason_codes))
        subject_payload = _complete_payload(row)
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
                "subject_hash": subject_hash,
                "standard_ids": sorted(satisfied_standard_ids),
                "evidence_ids": [item["resource_id"] for item in evidence],
                "evidence_citations": evidence,
            },
            governance_result={
                "policy_version": self.policy_version,
                "review_type": self.review_type,
                "mandatory_standards": standard_results,
                "supporting_evidence_count": len(evidence),
            },
        )

    def snapshot(self, actor, subject, readiness):
        row = self._require_current_subject(actor, subject, lock=True)
        checks = readiness.checks if isinstance(readiness.checks, Mapping) else {}
        if not readiness.ready:
            raise BlockedByEvidence("arb_subject_not_ready")
        current = self._evaluate_row(
            row,
            {"human_reviewed": checks.get("human_reviewed") is True},
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
                "subject": _complete_payload(row),
                "readiness": deepcopy(current.checks),
                "governance_result": deepcopy(current.governance_result),
            },
            "citations": [
                {"resource_type": self.subject_type, "resource_id": row.id},
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
            statement = statement.with_for_update(of=self.model_type)
        row = db.session.execute(statement).scalar_one_or_none()
        if row is None:
            raise _not_found()
        return row

    def _require_current_subject(self, actor, subject, *, lock=False):
        _require_subject(subject, self.subject_type)
        if subject.organization_id != actor.organization_id:
            raise _not_found()
        return self._load_row(actor, subject.subject_id, lock=lock)

    def _mandatory_standards(self):
        rows = db.session.execute(
            db.select(ARBGovernanceStandard).where(
                ARBGovernanceStandard.status == "active",
                ARBGovernanceStandard.mandatory.is_(True),
            )
        ).scalars()
        applicable = []
        for row in rows:
            types = row.applies_to_review_types
            if not types or self.review_type in types:
                applicable.append(row)
        return sorted(applicable, key=lambda row: (row.code, row.id))

    def _supporting_evidence(self, dossier):
        raw = dossier.get("evidence") if isinstance(dossier, Mapping) else None
        if not isinstance(raw, list) or not raw:
            return [], [{"code": "supporting_evidence_required"}]
        now = datetime.now(timezone.utc)
        citations = []
        blockers = []
        seen = set()
        for item in raw:
            evidence_id = item.get("evidence_id") if isinstance(item, Mapping) else None
            evidence_type = item.get("evidence_type") if isinstance(item, Mapping) else None
            content_hash = item.get("content_hash") if isinstance(item, Mapping) else None
            captured_at = self._parse_aware_datetime(item.get("captured_at")) if isinstance(item, Mapping) else None
            expires_at = self._parse_aware_datetime(item.get("expires_at")) if isinstance(item, Mapping) else None
            valid_id = (
                not isinstance(evidence_id, bool)
                and isinstance(evidence_id, (int, str))
                and bool(str(evidence_id).strip())
            )
            valid_hash = (
                isinstance(content_hash, str)
                and len(content_hash) == 64
                and all(character in "0123456789abcdef" for character in content_hash.lower())
            )
            if (
                not valid_id
                or evidence_id in seen
                or not isinstance(evidence_type, str)
                or not evidence_type.strip()
                or not valid_hash
                or captured_at is None
                or expires_at is None
            ):
                blockers.append({"code": "supporting_evidence_invalid", "evidence_id": evidence_id})
                continue
            if expires_at <= now:
                blockers.append({"code": "supporting_evidence_stale", "evidence_id": evidence_id})
                continue
            seen.add(evidence_id)
            citations.append(
                {
                    "resource_type": evidence_type,
                    "resource_id": evidence_id,
                    "content_hash": content_hash.lower(),
                    "captured_at": captured_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                }
            )
        if not citations and not blockers:
            blockers.append({"code": "supporting_evidence_required"})
        return citations, blockers

    @staticmethod
    def _parse_aware_datetime(value):
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)

    def _governance_dossier(self, row):
        raise NotImplementedError


class ArchitectureModelARBAdapter(_SubjectSnapshotAdapter):
    subject_type = "architecture_model"
    model_type = ArchitectureModel
    policy_version = "architecture-model-arb-r2"
    review_type = "technology_selection"
    required_fields = ("name", "version", "model_data")

    @staticmethod
    def _canonical_url(_subject_id):
        return "/architecture/models"

    def _governance_dossier(self, row):
        try:
            document = json.loads(row.model_data)
        except (TypeError, ValueError):
            return {}, [{"code": "architecture_model_json_invalid", "field": "model_data"}]
        if not isinstance(document, Mapping):
            return {}, [{"code": "architecture_model_json_invalid", "field": "model_data"}]
        dossier = document.get("arb_readiness")
        return (dossier if isinstance(dossier, Mapping) else {}), []


class ADRARBAdapter(_SubjectSnapshotAdapter):
    subject_type = "adr"
    model_type = ArchitectureDecisionRecord
    policy_version = "adr-arb-r2"
    review_type = "architecture_change"
    required_fields = ("title", "context", "decision", "rationale", "consequences")

    @staticmethod
    def _canonical_url(subject_id):
        return f"/architecture/adrs/records/{subject_id}"

    def _governance_dossier(self, row):
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
        governance = row.governance_blob if isinstance(row.governance_blob, Mapping) else {}
        dossier = governance.get("arb_readiness")
        return (dossier if isinstance(dossier, Mapping) else {}), blockers


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
