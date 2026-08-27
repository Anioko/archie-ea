"""HTTP ingress boundary for typed ADR / Architecture Model ARB submission.

The Solution subject already has a dedicated compatibility boundary in
``arb_submission_adapter``.  ADR and Architecture Model had **no** live ingress
at all — the typed command service was reachable only from tests — so this
module is the adapter the route-convergence audit asks for: it builds a trusted
``ActorContext`` from the authenticated session, derives an idempotency key,
calls ``TypedARBSubmissionService.submit`` and translates the typed domain
outcome into the documented failure envelope.

Nothing from the request body crosses this boundary except the explicit
``human_reviewed`` assertion.  Actor, organisation, role, readiness and status
fields supplied by a caller are ignored by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import logging
import uuid
from typing import Any, Mapping

from flask import request
from flask_login import current_user

from app import db
from app.models.architecture_review_board import ARBReviewCycle
from app.modules.transformation_room.arb_submission_adapter import (
    _COMMAND_KEY,
    TypedARBSubmissionAdapter,
)
from app.modules.transformation_room.arb_submission_service import (
    TypedARBSubmissionService,
)
from app.modules.transformation_room.domain import (
    ActorContext,
    BlockedByEvidence,
    CommandConflict,
    KnownPreCommitTransient,
    NotAuthorised,
    NotFound,
    TransformationError,
)


logger = logging.getLogger(__name__)

#: Subjects this ingress may submit.  Solution keeps its own legacy boundary and
#: Decision Brief is submitted from the workstream decision surface.
SUPPORTED_SUBJECT_TYPES = frozenset({"adr", "architecture_model"})

_SAFE_CONFLICT_REASONS = frozenset(
    {
        "arb_readiness_stale",
        "arb_submission_anchor_changed",
    }
)


@dataclass(frozen=True)
class TypedSubjectSubmissionResult:
    """Translated typed submission outcome for a JSON HTTP caller."""

    success: bool
    http_status: int = 200
    reason_codes: list[str] = field(default_factory=list)
    missing_evidence: list[dict[str, Any]] = field(default_factory=list)
    request_id: str | None = None
    idempotent: bool = False
    review_cycle_id: int | None = None
    review_item_id: int | None = None
    evidence_id: int | None = None
    review_number: str | None = None
    cycle_number: int | None = None
    subject_type: str | None = None
    subject_id: int | None = None
    canonical_url: str | None = None

    def success_payload(self) -> dict[str, Any]:
        """Flat ARB compatibility envelope plus the canonical typed identifiers."""
        return {
            "success": True,
            "review_cycle_id": self.review_cycle_id,
            "review_item_id": self.review_item_id,
            # Legacy aliases retained for existing callers.
            "review_id": self.review_item_id,
            "evidence_id": self.evidence_id,
            "snapshot_id": self.evidence_id,
            "review_number": self.review_number,
            "cycle_number": self.cycle_number,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "status": "submitted",
            "canonical_url": self.canonical_url,
            "redirect_url": (
                f"/arb/reviews/{self.review_item_id}"
                if self.review_item_id is not None
                else None
            ),
            "idempotent": self.idempotent,
            "request_id": self.request_id,
        }

    def failure_payload(self) -> dict[str, Any]:
        """Stable failure envelope: no exception text, no foreign identity."""
        return {
            "success": False,
            "reason_codes": list(self.reason_codes),
            "missing_evidence": list(self.missing_evidence),
            "request_id": self.request_id,
        }


class TypedARBSubjectIngress:
    """Trusted caller boundary for typed ADR / Architecture Model submission."""

    @classmethod
    def submit_from_request(
        cls,
        *,
        subject_type: str,
        subject_id: Any,
        payload: Mapping[str, Any] | None = None,
    ) -> TypedSubjectSubmissionResult:
        request_id = cls._request_id()
        if subject_type not in SUPPORTED_SUBJECT_TYPES:
            return TypedSubjectSubmissionResult(
                False,
                400,
                ["unsupported_subject_type"],
                request_id=request_id,
            )
        if (
            isinstance(subject_id, bool)
            or not isinstance(subject_id, int)
            or subject_id <= 0
        ):
            return TypedSubjectSubmissionResult(
                False,
                400,
                ["invalid_subject_id"],
                request_id=request_id,
            )

        authenticated = bool(getattr(current_user, "is_authenticated", False))
        try:
            actor = TypedARBSubmissionAdapter._actor_from_request()
        except NotAuthorised:
            return TypedSubjectSubmissionResult(
                False,
                403 if authenticated else 401,
                ["actor_not_authorized"] if authenticated else ["not_authenticated"],
                request_id=request_id,
            )
        request_id = actor.request_id or request_id

        supplied = payload if isinstance(payload, Mapping) else {}
        # The only browser assertion accepted at submission.
        human_reviewed = supplied.get("human_reviewed") is True

        try:
            # A command key may be supplied as a header or an explicit field.
            # A browser `review_item_id` is never accepted as a token.
            supplied_key = request.headers.get("Idempotency-Key") if request else None
            if supplied_key is None:
                supplied_key = supplied.get("idempotency_key")
            command_key = cls._command_key(
                supplied_key,
                actor=actor,
                subject_type=subject_type,
                subject_id=subject_id,
                human_reviewed=human_reviewed,
            )
        except ValueError:
            return TypedSubjectSubmissionResult(
                False,
                400,
                ["invalid_idempotency_key"],
                request_id=request_id,
            )

        return cls.submit(
            actor=actor,
            command_key=command_key,
            subject_type=subject_type,
            subject_id=subject_id,
            human_reviewed=human_reviewed,
        )

    @classmethod
    def submit(
        cls,
        *,
        actor: ActorContext,
        command_key: str,
        subject_type: str,
        subject_id: int,
        human_reviewed: bool = False,
    ) -> TypedSubjectSubmissionResult:
        request_id = actor.request_id
        try:
            result = TypedARBSubmissionService.submit(
                actor=actor,
                command_key=command_key,
                subject_type=subject_type,
                subject_id=subject_id,
                assertions={"human_reviewed": human_reviewed is True},
            )
        except TransformationError as error:
            return cls._failure(error, request_id)
        except ValueError:
            return TypedSubjectSubmissionResult(
                False, 400, ["invalid_submission_request"], request_id=request_id
            )
        except Exception:
            logger.exception("Typed ARB subject submission failed")
            return TypedSubjectSubmissionResult(
                False, 503, ["submission_failed"], request_id=request_id
            )

        response = dict(result.response)
        object_ids = dict(result.object_ids)
        return TypedSubjectSubmissionResult(
            True,
            200 if result.idempotent else 201,
            request_id=request_id,
            idempotent=result.idempotent,
            review_cycle_id=response.get("review_cycle_id")
            or object_ids.get("review_cycle_id"),
            review_item_id=response.get("review_item_id")
            or object_ids.get("review_item_id"),
            evidence_id=response.get("evidence_id") or object_ids.get("evidence_id"),
            review_number=response.get("review_number"),
            cycle_number=response.get("cycle_number"),
            subject_type=response.get("subject_type") or subject_type,
            subject_id=response.get("subject_id") or subject_id,
            canonical_url=response.get("canonical_url"),
        )

    # ── trusted input derivation ──────────────────────────────────────── #

    @staticmethod
    def _request_id() -> str:
        try:
            supplied = request.headers.get("X-Request-ID") if request else None
        except RuntimeError:
            supplied = None
        return supplied or str(uuid.uuid4())

    @classmethod
    def _command_key(
        cls,
        supplied: str | None,
        *,
        actor: ActorContext,
        subject_type: str,
        subject_id: int,
        human_reviewed: bool,
    ) -> str:
        if supplied is not None:
            if not isinstance(supplied, str) or not _COMMAND_KEY.fullmatch(supplied):
                raise ValueError("invalid idempotency key")
            return supplied
        anchor = cls._submission_anchor(actor, subject_type, subject_id)
        identity = (
            f"{actor.organization_id}:{actor.user_id}:{subject_type}:{subject_id}:"
            f"{human_reviewed}:{anchor}"
        ).encode("utf-8")
        return f"arb-{subject_type}-{hashlib.sha256(identity).hexdigest()}"

    @staticmethod
    def _submission_anchor(
        actor: ActorContext, subject_type: str, subject_id: int
    ) -> str:
        latest = db.session.execute(
            db.select(ARBReviewCycle)
            .where(
                ARBReviewCycle.organization_id == actor.organization_id,
                ARBReviewCycle.subject_type == subject_type,
                ARBReviewCycle.subject_id == subject_id,
            )
            .order_by(ARBReviewCycle.cycle_number.desc(), ARBReviewCycle.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest is None:
            return "root"
        if latest.closed_at is None:
            return str(latest.predecessor_cycle_id or "root")
        return str(latest.id)

    # ── outcome translation (§13 failure contract) ────────────────────── #

    @staticmethod
    def _failure(
        error: TransformationError, request_id: str | None
    ) -> TypedSubjectSubmissionResult:
        if isinstance(error, NotFound):
            return TypedSubjectSubmissionResult(
                False, 404, ["arb_subject_not_found"], request_id=request_id
            )
        if isinstance(error, NotAuthorised):
            return TypedSubjectSubmissionResult(
                False, 403, ["actor_not_authorized"], request_id=request_id
            )
        if isinstance(error, BlockedByEvidence):
            reason_codes = error.details.get("reason_codes")
            missing = error.details.get("missing_evidence")
            safe_reasons = (
                list(reason_codes)
                if isinstance(reason_codes, list) and reason_codes
                else ["arb_subject_not_ready"]
            )
            return TypedSubjectSubmissionResult(
                False,
                503 if "evaluator_unavailable" in safe_reasons else 422,
                safe_reasons,
                list(missing) if isinstance(missing, list) else [],
                request_id=request_id,
            )
        if isinstance(error, CommandConflict):
            reason = (
                error.reason
                if error.reason in _SAFE_CONFLICT_REASONS
                else "submission_conflict"
            )
            return TypedSubjectSubmissionResult(
                False, 409, [reason], request_id=request_id
            )
        if isinstance(error, KnownPreCommitTransient):
            return TypedSubjectSubmissionResult(
                False, 503, ["submission_failed"], request_id=request_id
            )
        return TypedSubjectSubmissionResult(
            False, 500, ["submission_failed"], request_id=request_id
        )


__all__ = [
    "SUPPORTED_SUBJECT_TYPES",
    "TypedARBSubjectIngress",
    "TypedSubjectSubmissionResult",
]
