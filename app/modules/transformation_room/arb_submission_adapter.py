"""Trusted caller boundary for legacy Solution ARB submission ingresses."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import logging
import re
import uuid
from typing import Any, Mapping

from flask import g, has_request_context, request
from flask_login import current_user

from app import db
from app.models.architecture_review_board import ARBReviewCycle
from app.models.solution_architect_models import SolutionDriver, SolutionGoal
from app.models.solution_lifecycle_models import SolutionRisk
from app.models.solution_models import Solution
from app.models.user import User
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

_COMMAND_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,199}\Z")
_SAFE_CONFLICT_REASONS = frozenset(
    {
        "arb_readiness_stale",
        "arb_submission_anchor_changed",
        "decision_brief_hash_mismatch",
        "solution_evidence_hash_mismatch",
    }
)


@dataclass(frozen=True)
class LegacyARBSubmissionResult:
    """Compatibility result shared by HTTP, chat and workbench callers."""

    success: bool
    reason_codes: list[str] = field(default_factory=list)
    missing_evidence: list[dict[str, Any]] = field(default_factory=list)
    review_item_id: int | None = None
    review_number: str | None = None
    snapshot_id: int | None = None
    idempotent: bool = False
    review_cycle_id: int | None = None
    canonical_url: str | None = None
    http_status: int = 200


class TypedARBSubmissionAdapter:
    """Build trusted command inputs and translate typed domain outcomes.

    Payload identity, role, subject association and readiness fields never cross
    this boundary. A browser may make only the explicit human-review assertion;
    workspace identity is supplied separately by a server-bound caller.
    """

    @classmethod
    def submit_solution_from_request(
        cls,
        *,
        solution_id: int,
        payload: Mapping[str, Any] | None,
        trusted_workspace_id: int | None = None,
    ) -> LegacyARBSubmissionResult:
        try:
            actor = cls._actor_from_request()
            supplied = payload if isinstance(payload, Mapping) else {}
            human_reviewed = (
                supplied.get("human_reviewed") is True
                or supplied.get("ai_content_reviewed") is True
            )
            command_key = cls._command_key(
                request.headers.get("Idempotency-Key"),
                actor=actor,
                solution_id=solution_id,
                workspace_id=trusted_workspace_id,
                human_reviewed=human_reviewed,
            )
            assertions = cls._server_assertions(
                actor=actor,
                solution_id=solution_id,
                workspace_id=trusted_workspace_id,
                human_reviewed=human_reviewed,
            )
            return cls._submit(
                actor=actor,
                command_key=command_key,
                solution_id=solution_id,
                workspace_id=trusted_workspace_id,
                assertions=assertions,
            )
        except ValueError:
            return LegacyARBSubmissionResult(
                False,
                ["invalid_idempotency_key"],
                http_status=400,
            )
        except TransformationError as error:
            return cls._failure(error)

    @classmethod
    def submit_subject_from_request(
        cls,
        *,
        subject_type: str,
        subject_id: int,
        payload: Mapping[str, Any] | None,
    ) -> LegacyARBSubmissionResult:
        """Submit an ADR or model using authenticated server identity only."""
        if subject_type not in {"adr", "architecture_model"}:
            return LegacyARBSubmissionResult(
                False, ["unsupported_subject_type"], http_status=400
            )
        try:
            actor = cls._actor_from_request()
            supplied = payload if isinstance(payload, Mapping) else {}
            raw_human_reviewed = supplied.get("human_reviewed")
            human_reviewed = raw_human_reviewed is True or (
                isinstance(raw_human_reviewed, str)
                and raw_human_reviewed.strip().lower() in {"1", "on", "true", "yes"}
            )
            command_key = cls._subject_command_key(
                request.headers.get("Idempotency-Key"),
                actor=actor,
                subject_type=subject_type,
                subject_id=subject_id,
                human_reviewed=human_reviewed,
            )
            return cls._submit_subject(
                actor=actor,
                command_key=command_key,
                subject_type=subject_type,
                subject_id=subject_id,
                assertions={"human_reviewed": human_reviewed},
            )
        except ValueError:
            return LegacyARBSubmissionResult(
                False, ["invalid_idempotency_key"], http_status=400
            )
        except TransformationError as error:
            return cls._failure(error, subject_type=subject_type)

    @classmethod
    def submit_solution_for_actor(
        cls,
        *,
        actor_id: int,
        solution_id: int,
        trusted_workspace_id: int | None = None,
        trusted_human_reviewed: bool = False,
        command_key: str | None = None,
        request_id: str | None = None,
    ) -> LegacyARBSubmissionResult:
        """Submit for a server-authenticated non-route caller.

        ``actor_id`` and workspace identity must originate from the caller's
        authenticated server state, never its model/browser argument map.
        """
        try:
            actor = cls._actor_for_server_caller(actor_id, request_id=request_id)
            resolved_key = cls._command_key(
                command_key,
                actor=actor,
                solution_id=solution_id,
                workspace_id=trusted_workspace_id,
                human_reviewed=trusted_human_reviewed is True,
            )
            assertions = cls._server_assertions(
                actor=actor,
                solution_id=solution_id,
                workspace_id=trusted_workspace_id,
                human_reviewed=trusted_human_reviewed is True,
            )
            return cls._submit(
                actor=actor,
                command_key=resolved_key,
                solution_id=solution_id,
                workspace_id=trusted_workspace_id,
                assertions=assertions,
            )
        except ValueError:
            return LegacyARBSubmissionResult(
                False,
                ["invalid_idempotency_key"],
                http_status=400,
            )
        except TransformationError as error:
            return cls._failure(error)

    @classmethod
    def _submit(
        cls,
        *,
        actor: ActorContext,
        command_key: str,
        solution_id: int,
        workspace_id: int | None,
        assertions: Mapping[str, Any],
    ) -> LegacyARBSubmissionResult:
        try:
            result = TypedARBSubmissionService.submit_legacy_solution(
                actor=actor,
                command_key=command_key,
                solution_id=solution_id,
                workspace_id=workspace_id,
                assertions=assertions,
            )
        except TransformationError as error:
            return cls._failure(error)
        except Exception:
            logger.exception("Typed ARB submission adapter failed")
            return LegacyARBSubmissionResult(
                False,
                ["submission_failed"],
                http_status=503,
            )

        response = dict(result.response)
        object_ids = dict(result.object_ids)
        return LegacyARBSubmissionResult(
            True,
            review_item_id=response.get("review_item_id")
            or object_ids.get("review_item_id"),
            review_number=response.get("review_number"),
            snapshot_id=response.get("evidence_id") or object_ids.get("evidence_id"),
            idempotent=result.idempotent,
            review_cycle_id=response.get("review_cycle_id")
            or object_ids.get("review_cycle_id"),
            canonical_url=response.get("canonical_url"),
            http_status=200 if result.idempotent else 201,
        )

    @classmethod
    def _submit_subject(
        cls,
        *,
        actor: ActorContext,
        command_key: str,
        subject_type: str,
        subject_id: int,
        assertions: Mapping[str, Any],
    ) -> LegacyARBSubmissionResult:
        try:
            result = TypedARBSubmissionService.submit(
                actor=actor,
                command_key=command_key,
                subject_type=subject_type,
                subject_id=subject_id,
                assertions=assertions,
            )
        except TransformationError as error:
            return cls._failure(error, subject_type=subject_type)
        except Exception:
            logger.exception("Typed ARB subject submission adapter failed")
            return LegacyARBSubmissionResult(
                False, ["submission_failed"], http_status=503
            )

        response = dict(result.response)
        object_ids = dict(result.object_ids)
        return LegacyARBSubmissionResult(
            True,
            review_item_id=response.get("review_item_id")
            or object_ids.get("review_item_id"),
            review_number=response.get("review_number"),
            snapshot_id=response.get("evidence_id") or object_ids.get("evidence_id"),
            idempotent=result.idempotent,
            review_cycle_id=response.get("review_cycle_id")
            or object_ids.get("review_cycle_id"),
            canonical_url=response.get("canonical_url"),
            http_status=200 if result.idempotent else 201,
        )

    @staticmethod
    def _server_assertions(
        *,
        actor: ActorContext,
        solution_id: int,
        workspace_id: int | None,
        human_reviewed: bool,
    ) -> dict[str, Any]:
        """Derive all non-human evidence from tenant-owned persisted records."""
        solution = db.session.execute(
            db.select(Solution).where(
                Solution.id == solution_id,
                Solution.organization_id == actor.organization_id,
            )
        ).scalar_one_or_none()
        if solution is None:
            raise NotFound("arb_subject_not_found")

        assertions: dict[str, Any] = {"human_reviewed": human_reviewed is True}
        if workspace_id is None:
            problem_id = db.session.execute(
                db.select(SolutionDriver.problem_id)
                .join(
                    SolutionGoal,
                    SolutionGoal.problem_id == SolutionDriver.problem_id,
                )
                .where(
                    SolutionDriver.organization_id == actor.organization_id,
                    SolutionGoal.organization_id == actor.organization_id,
                    SolutionDriver.problem.has(session_id=solution.analysis_session_id),
                )
                .limit(1)
            ).scalar_one_or_none()
            risk_id = db.session.execute(
                db.select(SolutionRisk.id)
                .where(
                    SolutionRisk.organization_id == actor.organization_id,
                    SolutionRisk.solution_id == solution.id,
                )
                .limit(1)
            ).scalar_one_or_none()
            evidence: dict[str, dict[str, Any]] = {}
            if problem_id is not None and risk_id is not None:
                evidence["design_reviewed"] = {
                    "passed": True,
                    "evidence": (
                        "Persisted governance evidence: driver/goal problem "
                        f"{problem_id}, solution risk {risk_id}."
                    ),
                }
            if isinstance(solution.security_lead, str) and solution.security_lead.strip():
                evidence["security_impact_reviewed"] = {
                    "passed": True,
                    "evidence": "Persisted security lead assignment reviewed.",
                }
            if (
                isinstance(solution.data_protection_officer, str)
                and solution.data_protection_officer.strip()
            ):
                evidence["data_impact_reviewed"] = {
                    "passed": True,
                    "evidence": "Persisted data protection officer assignment reviewed.",
                }
            if evidence:
                assertions["direct_route_evidence"] = evidence

        if (
            human_reviewed is True
            and solution.estimated_cost is not None
            and solution.estimated_cost != 0
        ):
            assertions["cost_source"] = "manual_override"
        return assertions

    @staticmethod
    def _actor_from_request() -> ActorContext:
        organization_id = getattr(g, "current_org_id", None)
        if (
            not current_user.is_authenticated
            or not isinstance(organization_id, int)
            or organization_id <= 0
        ):
            raise NotAuthorised("arb_submission_not_authorised")
        return TypedARBSubmissionAdapter._load_actor(
            current_user.id,
            organization_id,
            request.headers.get("X-Request-ID") or str(uuid.uuid4()),
        )

    @staticmethod
    def _actor_for_server_caller(actor_id: int, *, request_id: str | None) -> ActorContext:
        organization_id = getattr(g, "current_org_id", None)
        if not isinstance(organization_id, int) or organization_id <= 0:
            raise NotAuthorised("arb_submission_not_authorised")
        if has_request_context() and current_user.is_authenticated:
            if current_user.id != actor_id:
                raise NotAuthorised("arb_submission_actor_mismatch")
        return TypedARBSubmissionAdapter._load_actor(
            actor_id,
            organization_id,
            request_id or str(uuid.uuid4()),
        )

    @staticmethod
    def _load_actor(actor_id: int, organization_id: int, request_id: str) -> ActorContext:
        actor = db.session.execute(
            db.select(User).where(
                User.id == actor_id,
                User.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if actor is None:
            raise NotAuthorised("arb_submission_not_authorised")
        roles = {
            role
            for role in (
                actor.enterprise_role,
                "organization_admin" if actor.is_org_admin else None,
                "platform_admin" if actor.is_platform_admin else None,
            )
            if role
        }
        return ActorContext(
            user_id=actor.id,
            organization_id=organization_id,
            roles=frozenset(roles),
            request_id=request_id,
        )

    @classmethod
    def _command_key(
        cls,
        supplied: str | None,
        *,
        actor: ActorContext,
        solution_id: int,
        workspace_id: int | None,
        human_reviewed: bool,
    ) -> str:
        if supplied is not None:
            if not isinstance(supplied, str) or not _COMMAND_KEY.fullmatch(supplied):
                raise ValueError("invalid idempotency key")
            return supplied
        anchor = cls._submission_anchor(actor, solution_id)
        identity = (
            f"{actor.organization_id}:{actor.user_id}:{solution_id}:"
            f"{workspace_id or 'direct'}:{human_reviewed}:{anchor}"
        ).encode("utf-8")
        return f"arb-solution-{hashlib.sha256(identity).hexdigest()}"

    @classmethod
    def _subject_command_key(
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
        anchor = cls._typed_submission_anchor(actor, subject_type, subject_id)
        identity = (
            f"{actor.organization_id}:{actor.user_id}:{subject_type}:{subject_id}:"
            f"{human_reviewed}:{anchor}"
        ).encode("utf-8")
        return f"arb-{subject_type}-{hashlib.sha256(identity).hexdigest()}"

    @staticmethod
    def _submission_anchor(actor: ActorContext, solution_id: int) -> str:
        return TypedARBSubmissionAdapter._typed_submission_anchor(
            actor, "solution", solution_id
        )

    @staticmethod
    def _typed_submission_anchor(
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

    @staticmethod
    def _failure(
        error: TransformationError, *, subject_type: str = "solution"
    ) -> LegacyARBSubmissionResult:
        if isinstance(error, NotFound):
            return LegacyARBSubmissionResult(
                False, [f"{subject_type}_not_found"], http_status=404
            )
        if isinstance(error, NotAuthorised):
            return LegacyARBSubmissionResult(
                False, ["actor_not_authorized"], http_status=403
            )
        if isinstance(error, BlockedByEvidence):
            reason_codes = error.details.get("reason_codes")
            missing = error.details.get("missing_evidence")
            safe_reasons = (
                list(reason_codes)
                if isinstance(reason_codes, list)
                else ["arb_subject_not_ready"]
            )
            return LegacyARBSubmissionResult(
                False,
                safe_reasons,
                list(missing) if isinstance(missing, list) else [],
                http_status=503 if "evaluator_unavailable" in safe_reasons else 422,
            )
        if isinstance(error, CommandConflict):
            reason = (
                error.reason
                if error.reason in _SAFE_CONFLICT_REASONS
                else "submission_conflict"
            )
            return LegacyARBSubmissionResult(False, [reason], http_status=409)
        if isinstance(error, KnownPreCommitTransient):
            return LegacyARBSubmissionResult(
                False, ["submission_failed"], http_status=503
            )
        return LegacyARBSubmissionResult(False, ["submission_failed"], http_status=500)


__all__ = ["LegacyARBSubmissionResult", "TypedARBSubmissionAdapter"]
