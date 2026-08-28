"""Tenant-safe compatibility boundary for typed ARB decision routes."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import logging
import re
import uuid
from typing import Any, Mapping, Sequence

from flask import g, request
from flask_login import current_user

from app import db
from app.models.architecture_review_board import ARBReviewCycle, ARBReviewItem
from app.models.arb_decision_event import ARBCondition, ARBDecisionEvent
from app.models.user import User
from app.modules.transformation_room.arb_condition_evidence_service import (
    TypedARBConditionEvidenceService,
)
from app.modules.transformation_room.arb_condition_lifecycle_service import (
    TypedARBConditionLifecycleService,
)
from app.modules.transformation_room.arb_decision_service import (
    TypedARBDecisionService,
)
from app.modules.transformation_room.domain import (
    ActorContext,
    CommandConflict,
    KnownPreCommitTransient,
    NotAuthorised,
    NotFound,
    TransformationError,
)


logger = logging.getLogger(__name__)

_COMMAND_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,199}\Z")
_SAFE_AUTHORIZATION_REASONS = frozenset(
    {
        "arb_decision_not_authorised",
        "arb_decision_separation_of_duties",
    }
)
_OUTCOMES = {
    "approved": "approved",
    "approved_with_conditions": "approved_with_conditions",
    "conditional": "approved_with_conditions",
    "request_changes": "approved_with_conditions",
    "rejected": "rejected",
    "deferred": "returned_for_evidence",
    "return_for_evidence": "returned_for_evidence",
    "returned_for_evidence": "returned_for_evidence",
    "return_for_options": "returned_for_options",
    "returned_for_options": "returned_for_options",
}


@dataclass(frozen=True)
class LegacyARBDecisionResult:
    success: bool
    reason_codes: list[str] = field(default_factory=list)
    http_status: int = 200
    review_cycle_id: int | None = None
    review_item_id: int | None = None
    decision_event_id: int | None = None
    condition_ids: list[int] = field(default_factory=list)
    status: str | None = None
    outcome: str | None = None
    conditions: list[dict[str, Any]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    idempotent: bool = False
    typed: bool = True


class TypedARBDecisionAdapter:
    """Resolve legacy route identities before invoking the typed command.

    Browser identity, tenant, role, status and subject fields are deliberately
    absent from the command input.  Only the authenticated session and the
    tenant installed by middleware can create ``ActorContext``.
    """

    @classmethod
    def decide_review_from_request(
        cls,
        *,
        review_item_id: int,
        payload: Mapping[str, Any] | None,
        outcome: str | None = None,
    ) -> LegacyARBDecisionResult:
        try:
            actor = cls._actor_from_request()
            resolved = cls._resolve_review(actor, review_item_id)
            if resolved is None:
                return LegacyARBDecisionResult(False, typed=False)
            cycle, _review = resolved
            supplied = payload if isinstance(payload, Mapping) else {}
            mapped_outcome = cls._outcome(outcome or supplied.get("decision"))
            conditions = cls._conditions(supplied.get("conditions"))
            if mapped_outcome == "approved" and conditions:
                mapped_outcome = "approved_with_conditions"
            rationale = cls._rationale(supplied, mapped_outcome)
            command_key = cls._command_key(
                request.headers.get("Idempotency-Key"),
                actor=actor,
                cycle_id=cycle.id,
                outcome=mapped_outcome,
                rationale=rationale,
                conditions=conditions,
            )
            result = TypedARBDecisionService.decide(
                actor=actor,
                command_key=command_key,
                cycle_id=cycle.id,
                outcome=mapped_outcome,
                rationale=rationale,
                conditions=conditions,
            )
            response = dict(result.response)
            object_ids = dict(result.object_ids)
            return LegacyARBDecisionResult(
                True,
                review_cycle_id=object_ids.get("review_cycle_id"),
                review_item_id=object_ids.get("review_item_id"),
                decision_event_id=object_ids.get("decision_event_id"),
                condition_ids=list(object_ids.get("condition_ids") or ()),
                status=response.get("status"),
                outcome=response.get("outcome"),
                conditions=list(response.get("conditions") or ()),
                idempotent=result.idempotent,
            )
        except ValueError:
            return LegacyARBDecisionResult(
                False, ["invalid_decision_request"], http_status=400
            )
        except TransformationError as error:
            return cls._failure(error)
        except Exception:
            logger.exception("Typed ARB decision adapter failed")
            return LegacyARBDecisionResult(
                False, ["decision_not_confirmed"], http_status=503
            )

    @classmethod
    def decide_solution_from_request(
        cls,
        *,
        solution_id: int,
        review_item_id: int,
        payload: Mapping[str, Any] | None,
    ) -> LegacyARBDecisionResult:
        try:
            actor = cls._actor_from_request()
            try:
                resolved = cls._resolve_review(actor, review_item_id)
            except NotFound:
                from app.models.solution_governance import SolutionARBReview

                legacy = db.session.execute(
                    db.select(SolutionARBReview.id).where(
                        SolutionARBReview.id == review_item_id,
                        SolutionARBReview.organization_id == actor.organization_id,
                        SolutionARBReview.solution_id == solution_id,
                    )
                ).scalar_one_or_none()
                if legacy is not None:
                    return LegacyARBDecisionResult(False, typed=False)
                raise
            if resolved is None:
                return LegacyARBDecisionResult(False, typed=False)
            cycle, _review = resolved
            if cycle.subject_type != "solution" or cycle.solution_id != solution_id:
                raise NotFound("arb_review_not_found")
        except TransformationError as error:
            return cls._failure(error)
        return cls.decide_review_from_request(
            review_item_id=review_item_id,
            payload=payload,
        )

    @classmethod
    def decide_current_solution_from_request(
        cls,
        *,
        solution_id: int,
        payload: Mapping[str, Any] | None,
        outcome: str,
    ) -> LegacyARBDecisionResult:
        try:
            actor = cls._actor_from_request()
            cycle = cls._resolve_solution_cycle(actor, solution_id, open_only=False)
            review = db.session.execute(
                db.select(ARBReviewItem).where(
                    ARBReviewItem.organization_id == actor.organization_id,
                    ARBReviewItem.review_cycle_id == cycle.id,
                )
            ).scalar_one_or_none()
            if review is None:
                raise NotFound("arb_review_not_found")
        except TransformationError as error:
            return cls._failure(error)
        return cls.decide_review_from_request(
            review_item_id=review.id,
            payload=payload,
            outcome=outcome,
        )

    @classmethod
    def begin_review_from_request(
        cls, *, review_item_id: int
    ) -> LegacyARBDecisionResult:
        """Reject the unaudited legacy begin-review mutation for typed cycles."""
        try:
            actor = cls._actor_from_request()
            resolved = cls._resolve_review(actor, review_item_id)
            if resolved is None:
                return LegacyARBDecisionResult(False, typed=False)
            cycle, review = resolved
            TypedARBDecisionService.authorise_decision(
                db.session, actor, cycle.id, for_update=False
            )
            return LegacyARBDecisionResult(
                False,
                ["typed_begin_review_not_supported"],
                http_status=409,
                review_cycle_id=cycle.id,
                review_item_id=review.id,
                status=cycle.status,
            )
        except TransformationError as error:
            return cls._failure(error)
        except Exception:
            logger.exception("Typed ARB begin-review adapter failed")
            return LegacyARBDecisionResult(
                False, ["review_not_confirmed"], http_status=503
            )

    @classmethod
    def begin_current_solution_from_request(
        cls, *, solution_id: int
    ) -> LegacyARBDecisionResult:
        try:
            actor = cls._actor_from_request()
            cycle = cls._resolve_solution_cycle(actor, solution_id, open_only=False)
            review = db.session.execute(
                db.select(ARBReviewItem).where(
                    ARBReviewItem.organization_id == actor.organization_id,
                    ARBReviewItem.review_cycle_id == cycle.id,
                )
            ).scalar_one_or_none()
            if review is None:
                raise NotFound("arb_review_not_found")
        except TransformationError as error:
            return cls._failure(error)
        return cls.begin_review_from_request(review_item_id=review.id)

    @classmethod
    def transition_review_from_request(
        cls, *, review_item_id: int, payload: Mapping[str, Any] | None
    ) -> LegacyARBDecisionResult:
        supplied = payload if isinstance(payload, Mapping) else {}
        target = str(supplied.get("target_stage") or "").strip().lower()
        if target not in {
            "approved",
            "approved_with_conditions",
            "rejected",
            "returned_for_evidence",
            "returned_for_options",
        }:
            try:
                actor = cls._actor_from_request()
                resolved = cls._resolve_review(actor, review_item_id)
                if resolved is None:
                    return LegacyARBDecisionResult(False, typed=False)
                cycle, review = resolved
                return LegacyARBDecisionResult(
                    False,
                    ["typed_stage_transition_not_supported"],
                    http_status=409,
                    review_cycle_id=cycle.id,
                    review_item_id=review.id,
                    status=cycle.status,
                )
            except TransformationError as error:
                return cls._failure(error)
        return cls.decide_review_from_request(
            review_item_id=review_item_id,
            payload=supplied,
            outcome=target,
        )

    @classmethod
    def fulfill_condition_from_request(
        cls, *, condition_id: int, payload: Mapping[str, Any] | None
    ) -> LegacyARBDecisionResult:
        supplied = payload if isinstance(payload, Mapping) else {}
        if supplied.get("governance_model") != "typed":
            return LegacyARBDecisionResult(False, typed=False)
        try:
            actor = cls._actor_from_request()
            cls._resolve_condition(
                actor,
                condition_id,
                review_item_id=cls._positive_int(supplied.get("review_item_id")),
            )
            action = str(supplied.get("action") or "").strip().lower()
            if action == "submit_evidence":
                evidence = supplied.get("evidence")
                if not isinstance(evidence, Mapping):
                    raise ValueError("typed condition evidence must be an object")
                capture_key = cls._operation_command_key(
                    operation="capture",
                    actor=actor,
                    object_id=condition_id,
                    payload=evidence,
                )
                captured = TypedARBConditionEvidenceService.capture(
                    actor=actor,
                    command_key=capture_key,
                    condition_id=condition_id,
                    evidence=dict(evidence),
                )
                evidence_id = captured.object_ids["condition_evidence_id"]
                submitted = TypedARBConditionLifecycleService.submit_evidence(
                    actor=actor,
                    command_key=cls._operation_command_key(
                        operation="submit",
                        actor=actor,
                        object_id=condition_id,
                        payload={"condition_evidence_id": evidence_id},
                    ),
                    condition_id=condition_id,
                    condition_evidence_id=evidence_id,
                )
                data = {
                    **dict(submitted.response),
                    "condition_evidence_id": evidence_id,
                    "idempotent": captured.idempotent and submitted.idempotent,
                }
            elif action == "verify":
                evidence_id = cls._positive_int(supplied.get("condition_evidence_id"))
                verified = TypedARBConditionLifecycleService.verify(
                    actor=actor,
                    command_key=cls._operation_command_key(
                        operation="verify",
                        actor=actor,
                        object_id=condition_id,
                        payload={"condition_evidence_id": evidence_id},
                    ),
                    condition_id=condition_id,
                    condition_evidence_id=evidence_id,
                )
                data = {**dict(verified.response), "idempotent": verified.idempotent}
            else:
                return LegacyARBDecisionResult(
                    False,
                    ["typed_condition_fulfill_not_supported"],
                    http_status=409,
                )
            return LegacyARBDecisionResult(True, data=data)
        except ValueError:
            return LegacyARBDecisionResult(
                False, ["invalid_condition_request"], http_status=400
            )
        except TransformationError as error:
            return cls._failure(error)
        except Exception:
            logger.exception("Typed ARB condition fulfillment adapter failed")
            return LegacyARBDecisionResult(
                False, ["condition_not_confirmed"], http_status=503
            )

    @classmethod
    def waive_condition_from_request(
        cls, *, condition_id: int, payload: Mapping[str, Any] | None
    ) -> LegacyARBDecisionResult:
        supplied = payload if isinstance(payload, Mapping) else {}
        if supplied.get("governance_model") != "typed":
            return LegacyARBDecisionResult(False, typed=False)
        try:
            actor = cls._actor_from_request()
            cls._resolve_condition(
                actor,
                condition_id,
                review_item_id=cls._positive_int(supplied.get("review_item_id")),
            )
            result = TypedARBConditionLifecycleService.waive(
                actor=actor,
                command_key=cls._operation_command_key(
                    operation="waive",
                    actor=actor,
                    object_id=condition_id,
                    payload=supplied,
                ),
                condition_id=condition_id,
                reason=supplied.get("reason"),
                expires_at=supplied.get("expires_at"),
                scope=supplied.get("scope"),
                compensating_control=supplied.get("compensating_control"),
            )
            return LegacyARBDecisionResult(
                True,
                data={**dict(result.response), "idempotent": result.idempotent},
            )
        except ValueError:
            return LegacyARBDecisionResult(
                False, ["invalid_condition_request"], http_status=400
            )
        except TransformationError as error:
            return cls._failure(error)
        except Exception:
            logger.exception("Typed ARB condition waiver adapter failed")
            return LegacyARBDecisionResult(
                False, ["condition_not_confirmed"], http_status=503
            )

    @classmethod
    def current_solution_lifecycle_from_request(
        cls, *, solution_id: int
    ) -> LegacyARBDecisionResult:
        try:
            actor = cls._actor_from_request()
            try:
                cycle = cls._resolve_solution_cycle(actor, solution_id, open_only=False)
            except NotFound:
                return LegacyARBDecisionResult(False, typed=False)
            review = db.session.execute(
                db.select(ARBReviewItem).where(
                    ARBReviewItem.organization_id == actor.organization_id,
                    ARBReviewItem.review_cycle_id == cycle.id,
                )
            ).scalar_one_or_none()
            if review is None:
                raise NotFound("arb_review_not_found")
            decision = db.session.execute(
                db.select(ARBDecisionEvent).where(
                    ARBDecisionEvent.organization_id == actor.organization_id,
                    ARBDecisionEvent.review_cycle_id == cycle.id,
                )
            ).scalar_one_or_none()
            conditions = []
            if decision is not None:
                conditions = db.session.scalars(
                    db.select(ARBCondition)
                    .where(
                        ARBCondition.organization_id == actor.organization_id,
                        ARBCondition.decision_event_id == decision.id,
                    )
                    .order_by(ARBCondition.condition_number, ARBCondition.id)
                ).all()
            allowed = cls._typed_lifecycle_transitions(cycle.status, conditions)
            condition_data = [
                {
                    "id": condition.id,
                    "condition_number": condition.condition_number,
                    "description": condition.description,
                    "category": condition.category,
                    "due_date": condition.due_date.isoformat()
                    if condition.due_date
                    else None,
                    "status": condition.status,
                    "revision": condition.revision,
                }
                for condition in conditions
            ]
            data = {
                "governance_status": cycle.status,
                "allowed_transitions": allowed,
                "can_withdraw": False,
                "arb_submission_date": review.submitted_at.isoformat()
                if review.submitted_at
                else None,
                "arb_approval_date": decision.created_at.isoformat()
                if decision is not None
                and decision.outcome in {"approved", "approved_with_conditions"}
                else None,
                "arb_rejection_reason": decision.rationale
                if decision is not None and decision.outcome == "rejected"
                else None,
                "review_cycle_id": cycle.id,
                "review_item_id": review.id,
                "decision_event_id": decision.id if decision is not None else None,
                "terminal_outcome": cycle.terminal_outcome,
                "conditions": condition_data,
            }
            return LegacyARBDecisionResult(True, status=cycle.status, data=data)
        except TransformationError as error:
            return cls._failure(error)

    @classmethod
    def legacy_solution_review_matches_request(
        cls, *, solution_id: int, review_item_id: int
    ) -> bool:
        actor = cls._actor_from_request()
        from app.models.solution_governance import SolutionARBReview

        return db.session.execute(
            db.select(SolutionARBReview.id).where(
                SolutionARBReview.id == review_item_id,
                SolutionARBReview.organization_id == actor.organization_id,
                SolutionARBReview.solution_id == solution_id,
            )
        ).scalar_one_or_none() is not None

    @classmethod
    def legacy_condition_matches_request(cls, *, condition_id: int) -> bool:
        actor = cls._actor_from_request()
        from app.services.arb_workflow_service import ARBCondition as LegacyCondition

        return db.session.execute(
            db.select(LegacyCondition.id)
            .join(ARBReviewItem, ARBReviewItem.id == LegacyCondition.review_item_id)
            .where(
                LegacyCondition.id == condition_id,
                ARBReviewItem.organization_id == actor.organization_id,
                ARBReviewItem.review_cycle_id.is_(None),
            )
        ).scalar_one_or_none() is not None

    @classmethod
    def review_is_typed(cls, review_item_id: int) -> bool:
        actor = cls._actor_from_request()
        return cls._resolve_review(actor, review_item_id) is not None

    @classmethod
    def solution_has_typed_cycle(cls, solution_id: int) -> bool:
        actor = cls._actor_from_request()
        return db.session.execute(
            db.select(ARBReviewCycle.id).where(
                ARBReviewCycle.organization_id == actor.organization_id,
                ARBReviewCycle.subject_type == "solution",
                ARBReviewCycle.subject_id == solution_id,
                ARBReviewCycle.solution_id == solution_id,
            ).limit(1)
        ).scalar_one_or_none() is not None

    @staticmethod
    def _resolve_review(actor: ActorContext, review_item_id: int):
        review = db.session.execute(
            db.select(ARBReviewItem).where(
                ARBReviewItem.id == review_item_id,
                ARBReviewItem.organization_id == actor.organization_id,
            )
        ).scalar_one_or_none()
        if review is None:
            raise NotFound("arb_review_not_found")
        if review.review_cycle_id is None:
            return None
        cycle = db.session.execute(
            db.select(ARBReviewCycle).where(
                ARBReviewCycle.id == review.review_cycle_id,
                ARBReviewCycle.organization_id == actor.organization_id,
            )
        ).scalar_one_or_none()
        if cycle is None:
            raise NotFound("arb_review_not_found")
        TypedARBDecisionService._assert_cycle_review_projection_equal(cycle, review)
        return cycle, review

    @staticmethod
    def _resolve_solution_cycle(
        actor: ActorContext, solution_id: int, *, open_only: bool
    ) -> ARBReviewCycle:
        statement = db.select(ARBReviewCycle).where(
            ARBReviewCycle.organization_id == actor.organization_id,
            ARBReviewCycle.subject_type == "solution",
            ARBReviewCycle.subject_id == solution_id,
            ARBReviewCycle.solution_id == solution_id,
        )
        if open_only:
            statement = statement.where(ARBReviewCycle.closed_at.is_(None))
        cycle = db.session.execute(
            statement.order_by(
                ARBReviewCycle.cycle_number.desc(), ARBReviewCycle.id.desc()
            ).limit(1)
        ).scalar_one_or_none()
        if cycle is None:
            raise NotFound("arb_review_not_found")
        return cycle

    @staticmethod
    def _resolve_condition(
        actor: ActorContext, condition_id: int, *, review_item_id: int
    ) -> ARBCondition:
        condition_id = TypedARBDecisionAdapter._positive_int(condition_id)
        resolved = TypedARBDecisionAdapter._resolve_review(actor, review_item_id)
        if resolved is None:
            raise NotFound("arb_condition_not_found")
        cycle, review = resolved
        condition = db.session.execute(
            db.select(ARBCondition).where(
                ARBCondition.id == condition_id,
                ARBCondition.organization_id == actor.organization_id,
                ARBCondition.review_cycle_id == cycle.id,
                ARBCondition.review_item_id == review.id,
            )
        ).scalar_one_or_none()
        if condition is None:
            raise NotFound("arb_condition_not_found")
        return condition

    @staticmethod
    def _positive_int(value: Any) -> int:
        if isinstance(value, bool):
            raise ValueError("a positive integer is required")
        try:
            normalized = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError("a positive integer is required") from error
        if normalized <= 0:
            raise ValueError("a positive integer is required")
        return normalized

    @staticmethod
    def _operation_command_key(
        *,
        operation: str,
        actor: ActorContext,
        object_id: int,
        payload: Mapping[str, Any],
    ) -> str:
        supplied = request.headers.get("Idempotency-Key")
        if supplied is not None and not _COMMAND_KEY.fullmatch(supplied):
            raise ValueError("invalid idempotency key")
        identity = json.dumps(
            {
                "base_key": supplied,
                "operation": operation,
                "organization_id": actor.organization_id,
                "user_id": actor.user_id,
                "object_id": object_id,
                "payload": dict(payload),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return f"arb-condition-{operation}-{hashlib.sha256(identity).hexdigest()}"

    @staticmethod
    def _typed_lifecycle_transitions(
        status: str, conditions: Sequence[ARBCondition]
    ) -> list[str]:
        if status in {
            "submitted",
            "under_review",
            "pending_information",
            "pending_info",
            "pending",
        }:
            return [
                "approved",
                "approved_with_conditions",
                "rejected",
                "returned_for_evidence",
                "returned_for_options",
            ]
        condition_statuses = {condition.status for condition in conditions}
        allowed = []
        if "pending" in condition_statuses:
            allowed.extend(("submit_condition_evidence", "waive_condition"))
        if "evidence_submitted" in condition_statuses:
            allowed.extend(("verify_condition_evidence", "waive_condition"))
        return list(dict.fromkeys(allowed))

    @staticmethod
    def _actor_from_request() -> ActorContext:
        organization_id = getattr(g, "current_org_id", None)
        if (
            not current_user.is_authenticated
            or not isinstance(organization_id, int)
            or organization_id <= 0
        ):
            raise NotAuthorised("arb_decision_not_authorised")
        user = db.session.execute(
            db.select(User).where(
                User.id == current_user.id,
                User.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if user is None:
            raise NotAuthorised("arb_decision_not_authorised")
        roles = frozenset(
            role
            for role in (
                user.enterprise_role,
                "organization_admin" if user.is_org_admin else None,
                "platform_admin" if user.is_platform_admin else None,
            )
            if role
        )
        return ActorContext(
            user_id=user.id,
            organization_id=organization_id,
            roles=roles,
            request_id=request.headers.get("X-Request-ID") or str(uuid.uuid4()),
        )

    @staticmethod
    def _outcome(value: Any) -> str:
        normalized = str(value or "").strip().lower()
        outcome = _OUTCOMES.get(normalized)
        if outcome is None:
            raise ValueError("unsupported ARB decision outcome")
        return outcome

    @staticmethod
    def _rationale(payload: Mapping[str, Any], outcome: str) -> str:
        candidates = (
            payload.get("rationale"),
            payload.get("decision_reason"),
            payload.get("reason"),
            payload.get("notes"),
            payload.get("approval_notes"),
        )
        rationale = next(
            (value.strip() for value in candidates if isinstance(value, str) and value.strip()),
            "",
        )
        if not rationale:
            raise ValueError(f"rationale is required for {outcome}")
        return rationale

    @staticmethod
    def _conditions(raw: Any) -> list[dict[str, Any]]:
        if raw in (None, "", []):
            return []
        if isinstance(raw, str):
            values: Sequence[Any] = [line for line in raw.splitlines() if line.strip()]
        elif isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray)):
            values = raw
        else:
            raise ValueError("conditions must be a list or newline-delimited text")
        conditions = []
        for ordinal, value in enumerate(values, start=1):
            if isinstance(value, str):
                conditions.append(
                    {
                        "condition_number": f"COND-{ordinal}",
                        "description": value,
                        "due_date": None,
                    }
                )
            elif isinstance(value, Mapping):
                conditions.append(
                    {
                        "condition_number": value.get("condition_number")
                        or value.get("code")
                        or f"COND-{ordinal}",
                        "description": value.get("description") or value.get("text")
                        or value.get("condition"),
                        "category": value.get("category"),
                        "due_date": value.get("due_date"),
                    }
                )
            else:
                raise ValueError("conditions must contain text or objects")
        return conditions

    @staticmethod
    def _command_key(
        supplied: str | None,
        *,
        actor: ActorContext,
        cycle_id: int,
        outcome: str,
        rationale: str,
        conditions: Sequence[Mapping[str, Any]],
    ) -> str:
        if supplied is not None:
            if not isinstance(supplied, str) or not _COMMAND_KEY.fullmatch(supplied):
                raise ValueError("invalid idempotency key")
            return supplied
        identity = json.dumps(
            {
                "organization_id": actor.organization_id,
                "user_id": actor.user_id,
                "cycle_id": cycle_id,
                "outcome": outcome,
                "rationale": rationale,
                "conditions": list(conditions),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return f"arb-decision-{hashlib.sha256(identity).hexdigest()}"

    @staticmethod
    def _failure(error: TransformationError) -> LegacyARBDecisionResult:
        if isinstance(error, NotFound):
            return LegacyARBDecisionResult(
                False, ["review_not_found"], http_status=404
            )
        if isinstance(error, NotAuthorised):
            reason = (
                error.reason
                if error.reason in _SAFE_AUTHORIZATION_REASONS
                else "actor_not_authorized"
            )
            return LegacyARBDecisionResult(
                False, [reason], http_status=403
            )
        if isinstance(error, CommandConflict):
            return LegacyARBDecisionResult(
                False, ["decision_conflict"], http_status=409
            )
        if isinstance(error, KnownPreCommitTransient):
            return LegacyARBDecisionResult(
                False, ["decision_not_confirmed"], http_status=503
            )
        return LegacyARBDecisionResult(False, ["decision_failed"], http_status=500)


__all__ = ["LegacyARBDecisionResult", "TypedARBDecisionAdapter"]
