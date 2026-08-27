"""Command-fenced capture of immutable evidence for canonical ARB conditions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import select

from app import db
from app.models.architecture_review_board import ARBReviewCycle, ARBReviewItem
from app.models.arb_condition_evidence import ARBConditionEvidenceRecord
from app.models.arb_decision_event import ARBCondition, ARBDecisionEvent
from app.models.user import User
from app.modules.transformation_room.arb_submission_service import TypedARBSubmissionService
from app.modules.transformation_room.command_service import CommandService
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    DomainMutationResult,
    NotAuthorised,
    NotFound,
)


_SUBMIT_ROLES = frozenset(
    {"chief_architect", "enterprise_architect", "solution_architect", "architect", "arb_member"}
)
_TYPED_COLUMNS = (
    "subject_type", "subject_id", "decision_brief_id", "solution_id",
    "architecture_model_id", "adr_id", "decision_brief_version_id",
    "solution_evidence_snapshot_id", "subject_evidence_snapshot_id",
)


class TypedARBConditionEvidenceService:
    OPERATION = "arb.condition.evidence.capture"
    REQUIRED_PRIOR_STATUS = "pending"
    ACCEPTED_CONDITION_STATUS = "evidence_submitted"
    ACCEPTABLE_FRESHNESS = frozenset({"fresh", "not_applicable"})
    MAX_EVIDENCE_BYTES = 64 * 1024

    @classmethod
    def capture(cls, *, actor, command_key, condition_id, evidence):
        if not isinstance(actor, ActorContext):
            raise TypeError("actor must be ActorContext")
        if not isinstance(command_key, str) or not command_key.strip():
            raise ValueError("command_key is required")
        if isinstance(condition_id, bool) or not isinstance(condition_id, int) or condition_id <= 0:
            raise ValueError("condition_id must be a positive integer")
        supplied = cls._canonical_evidence(evidence)
        condition, decision, cycle, review = cls._load_condition_graph(
            db.session, actor, condition_id, for_update=False
        )
        cls._assert_exact_typed_membership(condition, decision, cycle, review)
        cls.authorise_acceptance(db.session, actor, condition_id)
        revision = getattr(condition, "revision", 1)
        natural_key = (
            f"arb-condition-evidence:{actor.organization_id}:{condition_id}:{revision}"
        )
        payload = {"condition_id": condition_id, "condition_revision": revision, "evidence": supplied}

        def authorize(session, runtime_actor, operation, supplied_key):
            if operation != cls.OPERATION or supplied_key != natural_key:
                raise NotAuthorised("arb_condition_evidence_command_mismatch")
            cls.authorise_acceptance(session, runtime_actor, condition_id)

        return CommandService.execute(
            actor=actor,
            operation=cls.OPERATION,
            idempotency_key=command_key.strip(),
            payload=payload,
            natural_key=natural_key,
            authorizer=authorize,
            natural_key_resolver=CommandService.fail_closed_pre_envelope_recovery,
            handler=lambda session, claim: cls._accept_locked(
                session=session, actor=actor, condition_id=condition_id,
                claimed_revision=revision, evidence=supplied, claim=claim,
            ),
        )

    accept = capture

    @classmethod
    def _canonical_evidence(cls, evidence):
        if not isinstance(evidence, dict):
            raise ValueError("evidence must be an object")
        cls._reject_candidate_scope_fields(evidence)
        required = (
            "source_identity", "source_type", "source_version", "source_checksum",
            "value_json", "observed_at", "freshness_rule_version",
        )
        if any(key not in evidence for key in required):
            raise ValueError("condition evidence is incomplete")
        result = deepcopy(evidence)
        supplied_content_hash = result.pop("content_hash", None)
        for key, limit in (
            ("source_identity", 1024), ("source_type", 80),
            ("source_version", 512), ("freshness_rule_version", 160),
        ):
            value = str(result[key]).strip()
            if not value or len(value) > limit or any(ord(ch) < 32 for ch in value):
                raise ValueError(f"invalid {key}")
            result[key] = value
        checksum = str(result["source_checksum"]).lower()
        if len(checksum) != 64 or any(ch not in "0123456789abcdef" for ch in checksum):
            raise ValueError("invalid source_checksum")
        result["source_checksum"] = checksum
        result["freshness_status"] = str(result.get("freshness_status", "fresh"))
        if result["freshness_status"] not in cls.ACCEPTABLE_FRESHNESS:
            raise ValueError("condition evidence must be fresh or not_applicable")
        result["observed_at"] = cls._iso_datetime(result["observed_at"], "observed_at")
        expires = result.get("freshness_expires_at")
        result["freshness_expires_at"] = (
            cls._iso_datetime(expires, "freshness_expires_at") if expires else None
        )
        if result["freshness_expires_at"] and result["freshness_expires_at"] <= result["observed_at"]:
            raise ValueError("freshness_expires_at must be after observed_at")
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(encoded) > cls.MAX_EVIDENCE_BYTES:
            raise ValueError("condition evidence exceeds 64 KiB")
        computed_hash = cls._compute_content_hash(result)
        if supplied_content_hash is not None and supplied_content_hash.lower() != computed_hash:
            raise ValueError("content_hash does not match condition evidence")
        return result

    @staticmethod
    def _iso_datetime(value, field):
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"invalid {field}") from exc
        else:
            raise ValueError(f"invalid {field}")
        if parsed.tzinfo is None:
            raise ValueError(f"invalid {field}")
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _reject_candidate_scope_fields(evidence):
        forbidden = {"programme_id", "workstream_id", "candidate_id"}.intersection(evidence)
        if forbidden:
            raise ValueError("candidate-scoped identity is forbidden for ARB condition evidence")

    @staticmethod
    def _compute_content_hash(evidence):
        return hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    @classmethod
    def _load_condition_graph(cls, session, actor, condition_id, *, for_update):
        def load(model, *predicates):
            statement = select(model).where(*predicates)
            if for_update:
                statement = statement.with_for_update()
            return session.execute(statement).scalar_one_or_none()

        condition = load(
            ARBCondition, ARBCondition.id == condition_id,
            ARBCondition.organization_id == actor.organization_id,
        )
        if condition is None:
            raise NotFound("arb_condition_not_found")
        decision = load(
            ARBDecisionEvent, ARBDecisionEvent.id == condition.decision_event_id,
            ARBDecisionEvent.organization_id == actor.organization_id,
        )
        cycle = load(
            ARBReviewCycle, ARBReviewCycle.id == condition.review_cycle_id,
            ARBReviewCycle.organization_id == actor.organization_id,
        )
        review = load(
            ARBReviewItem, ARBReviewItem.id == condition.review_item_id,
            ARBReviewItem.organization_id == actor.organization_id,
        )
        if any(value is None for value in (decision, cycle, review)):
            raise NotFound("arb_condition_not_found")
        return condition, decision, cycle, review

    @classmethod
    def _load_condition_graph_for_update(cls, session, actor, condition_id):
        return cls._load_condition_graph(
            session, actor, condition_id, for_update=True
        )

    @staticmethod
    def _assert_exact_typed_membership(condition, decision, cycle, review):
        if (
            condition.decision_event_id != decision.id
            or condition.review_cycle_id != cycle.id
            or condition.review_item_id != review.id
            or decision.review_cycle_id != cycle.id
            or decision.review_item_id != review.id
            or any(getattr(decision, name) != getattr(cycle, name) for name in _TYPED_COLUMNS)
            or any(getattr(decision, name) != getattr(review, name) for name in _TYPED_COLUMNS)
        ):
            raise CommandConflict("arb_condition_evidence_membership_mismatch")

    @classmethod
    def authorise_acceptance(cls, session, actor, condition_id, *, for_update=False):
        user_statement = select(User).where(
            User.id == actor.user_id, User.organization_id == actor.organization_id
        )
        if for_update:
            user_statement = user_statement.with_for_update()
        user = session.execute(user_statement).scalar_one_or_none()
        condition, decision, cycle, review = cls._load_condition_graph(
            session, actor, condition_id, for_update=False
        )
        if user is None or not (
            review.submitter_id == user.id
            or decision.actor_id == user.id
            or user.is_org_admin
            or user.is_platform_admin
            or user.enterprise_role in _SUBMIT_ROLES
        ):
            raise NotAuthorised("arb_condition_evidence_not_authorised")
        cls._assert_exact_typed_membership(condition, decision, cycle, review)

    @classmethod
    def _accept_locked(cls, *, session, actor, condition_id, claimed_revision, evidence, claim):
        condition, decision, cycle, review = cls._load_condition_graph_for_update(
            session, actor, condition_id
        )
        cls._assert_exact_typed_membership(condition, decision, cycle, review)
        session.execute(
            select(ARBReviewCycle.id).where(
                ARBReviewCycle.id == cycle.id,
                ARBReviewCycle.organization_id == actor.organization_id,
            ).with_for_update()
        )
        TypedARBSubmissionService._lock_subject_submission(session, actor, cycle)
        cls.authorise_acceptance(session, actor, condition_id, for_update=True)
        if getattr(condition, "revision", 1) != claimed_revision:
            raise CommandConflict("arb_condition_revision_changed")
        if condition.status != cls.REQUIRED_PRIOR_STATUS:
            raise CommandConflict("arb_condition_not_pending")
        now = CommandService._database_now(session)
        typed_values = {name: getattr(decision, name) for name in _TYPED_COLUMNS}
        record = ARBConditionEvidenceRecord(
            organization_id=actor.organization_id,
            condition_id=condition.id,
            condition_revision=claimed_revision,
            decision_event_id=decision.id,
            review_cycle_id=cycle.id,
            review_item_id=review.id,
            **typed_values,
            value_json=evidence["value_json"],
            content_hash=cls._compute_content_hash(evidence),
            source_identity=evidence["source_identity"],
            source_type=evidence["source_type"],
            source_version=evidence["source_version"],
            source_checksum=evidence["source_checksum"],
            observed_at=datetime.fromisoformat(evidence["observed_at"].replace("Z", "+00:00")),
            collected_at=now,
            freshness_status=evidence["freshness_status"],
            freshness_expires_at=datetime.fromisoformat(evidence["freshness_expires_at"].replace("Z", "+00:00")) if evidence["freshness_expires_at"] else None,
            freshness_rule_version=evidence["freshness_rule_version"],
            created_by_id=actor.user_id,
            command_receipt_id=claim.receipt_id,
            command_generation=claim.generation,
        )
        session.add(record)
        session.flush()
        ids = {
            "condition_id": condition.id,
            "condition_evidence_id": record.id,
            "review_cycle_id": cycle.id,
            "condition_revision": claimed_revision,
        }
        return DomainMutationResult(
            object_ids=ids,
            response={**ids, "status": "captured", "lifecycle_transitioned": False},
            outbox_events=(),
        )


__all__ = ["TypedARBConditionEvidenceService"]
