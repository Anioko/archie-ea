"""Tenant-safe compatibility boundary for typed ARB decision routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timezone
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
from app.models.user import User
from app.modules.transformation_room.arb_decision_service import (
    TypedARBDecisionService,
)
from app.modules.transformation_room.command_service import CommandService
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
        """Project a typed cycle and its sole item to ``under_review``."""
        try:
            actor = cls._actor_from_request()
            resolved = cls._resolve_review(actor, review_item_id)
            if resolved is None:
                return LegacyARBDecisionResult(False, typed=False)
            cycle, review = resolved
            TypedARBDecisionService._lock_subject_decision(db.session, actor, cycle.id)
            cycle, review = TypedARBDecisionService._load_cycle_and_review_for_update(
                db.session, actor, cycle.id
            )
            TypedARBDecisionService._assert_cycle_review_projection_equal(cycle, review)
            if cycle.status == "historical_unverified":
                raise CommandConflict("historical_unverified_cycle_not_reviewable")
            # Re-authorise even an idempotent projection replay.  A user whose
            # server-side role changed after the first request must not retain
            # decision authority through the already-under-review shortcut.
            TypedARBDecisionService.authorise_decision(
                db.session, actor, cycle.id, for_update=True
            )
            if cycle.status == "under_review":
                return LegacyARBDecisionResult(
                    True,
                    review_cycle_id=cycle.id,
                    review_item_id=review.id,
                    status="under_review",
                    idempotent=True,
                )
            if cycle.status != "submitted" or cycle.closed_at is not None:
                raise CommandConflict("arb_cycle_not_open_for_review")
            now = CommandService._database_now(db.session)
            cycle.status = "under_review"
            review.status = "under_review"
            review.reviewer_id = actor.user_id
            review.review_started_at = now.astimezone(timezone.utc).replace(tzinfo=None)
            db.session.commit()
            return LegacyARBDecisionResult(
                True,
                review_cycle_id=cycle.id,
                review_item_id=review.id,
                status="under_review",
            )
        except TransformationError as error:
            db.session.rollback()
            return cls._failure(error)
        except Exception:
            db.session.rollback()
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
            return LegacyARBDecisionResult(
                False, ["actor_not_authorized"], http_status=403
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
