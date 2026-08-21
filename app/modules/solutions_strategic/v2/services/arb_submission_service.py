"""Canonical, evidence-gated submission of solutions to the ARB."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
import logging
import uuid
from decimal import Decimal
from typing import Any

from flask import g, has_request_context

from app import db
from app.models.arb_submission_evidence import (
    ARBSubmissionEvidenceSnapshot,
    WorkbenchArtifactEvidence,
    evidence_immutability_is_installed,
)
from app.models.architecture_review_board import ARBReviewItem, ARB_OPEN_STATUSES
from app.models.audit_log import AuditLog
from app.models.solution_architect_models import SolutionAnalysisSession, SolutionRecommendation
from app.models.solution_governance import SolutionNotification
from app.models.solution_models import Solution
from app.models.user import User
from app.modules.solutions_strategic.v2.services.governance_gate_service import check_gate

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ARBReadinessResult:
    ready: bool
    reason_codes: list[str] = field(default_factory=list)
    missing_evidence: list[dict[str, Any]] = field(default_factory=list)
    workflow_type: str | None = None
    checks: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    governance_result: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ARBSubmissionResult:
    success: bool
    reason_codes: list[str] = field(default_factory=list)
    missing_evidence: list[dict[str, Any]] = field(default_factory=list)
    review_item_id: int | None = None
    review_number: str | None = None
    snapshot_id: int | None = None
    idempotent: bool = False


class ARBSubmissionService:
    """Owns readiness evaluation and the complete ARB submission transaction."""

    SCHEMA_VERSION = 1
    REQUIRED_ARTIFACTS = {
        "greenfield": ("brief", "scope", "recommendation"),
        "brownfield": (
            "portfolio_context",
            "current_state",
            "gap_analysis",
            "transition_plan",
        ),
    }
    VALID_STATES = frozenset({"draft", "rejected"})
    DIRECT_ROUTE_CHECKS = (
        "design_reviewed",
        "security_impact_reviewed",
        "data_impact_reviewed",
    )

    @classmethod
    def evaluate(
        cls,
        solution_id: int,
        actor_id: int,
        workspace_id: int | None = None,
        assertions: dict[str, Any] | None = None,
    ) -> ARBReadinessResult:
        assertions = deepcopy(assertions or {})
        try:
            return cls._evaluate(solution_id, actor_id, workspace_id, assertions)
        except Exception:
            logger.exception("ARB readiness evaluation failed")
            return ARBReadinessResult(
                ready=False,
                reason_codes=["evaluator_unavailable"],
                missing_evidence=[
                    {
                        "code": "evaluator_unavailable",
                        "action": "Retry after the governance evaluator is available",
                    }
                ],
            )

    @classmethod
    def _evaluate(cls, solution_id, actor_id, workspace_id, assertions, *, active_review=False):
        organization_id = getattr(g, "current_org_id", None) if has_request_context() else None
        if organization_id is None:
            return cls._blocked("tenant_context_missing")

        solution = db.session.execute(
            db.select(Solution).where(
                Solution.id == solution_id,
                Solution.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if solution is None:
            return cls._blocked("solution_not_found")

        actor = db.session.execute(
            db.select(User).where(
                User.id == actor_id,
                User.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if actor is None:
            return cls._blocked("actor_not_found")
        if not cls._actor_can_access(actor, solution):
            return cls._blocked("actor_not_authorized")

        workspace = None
        artifacts = {}
        workflow_type = "direct"
        if workspace_id is not None:
            workspace = db.session.execute(
                db.select(SolutionAnalysisSession).where(
                    SolutionAnalysisSession.id == workspace_id,
                    SolutionAnalysisSession.organization_id == organization_id,
                )
            ).scalar_one_or_none()
            if workspace is None:
                return cls._blocked("workspace_not_found")
            metadata = workspace.custom_metadata or {}
            if workspace.created_by_id != actor.id:
                return cls._blocked("workspace_actor_mismatch")
            if metadata.get("solution_id") != solution.id:
                return cls._blocked("workspace_solution_mismatch")
            workflow_type = metadata.get("workspace_type")
            if workflow_type not in cls.REQUIRED_ARTIFACTS:
                return cls._blocked("workspace_workflow_invalid")
            rows = db.session.execute(
                db.select(WorkbenchArtifactEvidence)
                .where(
                    WorkbenchArtifactEvidence.organization_id == organization_id,
                    WorkbenchArtifactEvidence.workspace_id == workspace.id,
                    WorkbenchArtifactEvidence.solution_id == solution.id,
                )
                .order_by(
                    WorkbenchArtifactEvidence.name,
                    WorkbenchArtifactEvidence.version.desc(),
                )
            ).scalars()
            for row in rows:
                artifacts.setdefault(
                    row.name,
                    {
                        "state": row.state,
                        "data": deepcopy(row.payload or {}),
                        "evidence_id": row.id,
                        "content_hash": row.content_hash,
                        "version": row.version,
                        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
                    },
                )

        if solution.governance_status not in cls.VALID_STATES and not (
            active_review and solution.governance_status == "arb_review"
        ):
            return cls._blocked("invalid_governance_state")

        missing = []
        if workspace is not None:
            for name in cls.REQUIRED_ARTIFACTS[workflow_type]:
                artifact = artifacts.get(name)
                if not isinstance(artifact, dict):
                    missing.append({"code": "artifact_missing", "artifact": name})
                elif artifact.get("state") not in {"persisted", "approved"}:
                    missing.append(
                        {
                            "code": "artifact_not_persisted",
                            "artifact": name,
                            "required_state": "persisted",
                        }
                    )
            if missing:
                return cls._blocked("missing_named_artifacts", missing, workflow_type, artifacts)
        else:
            direct_checks = assertions.get("direct_route_evidence")
            missing_checks = []
            for name in cls.DIRECT_ROUTE_CHECKS:
                item = direct_checks.get(name) if isinstance(direct_checks, dict) else None
                if not (
                    isinstance(item, dict)
                    and item.get("passed") is True
                    and isinstance(item.get("evidence"), str)
                    and item["evidence"].strip()
                ):
                    missing_checks.append({"code": "direct_route_check_missing", "check": name})
            if missing_checks:
                return cls._blocked(
                    "missing_direct_route_evidence",
                    missing_checks,
                    workflow_type,
                )

        if cls._has_ai_content(solution, workspace) and not assertions.get("human_reviewed"):
            return cls._blocked(
                "human_review_required",
                [{"code": "human_review_required", "assertion": "human_reviewed"}],
                workflow_type,
                artifacts,
            )

        if solution.estimated_cost is not None and solution.estimated_cost != Decimal("0"):
            if assertions.get("cost_source") not in {"tco_engine", "manual_override"}:
                return cls._blocked(
                    "cost_source_required",
                    [
                        {
                            "code": "cost_source_required",
                            "allowed": ["tco_engine", "manual_override"],
                        }
                    ],
                    workflow_type,
                    artifacts,
                )

        invalid_vendors = cls._invalid_vendor_references(solution, workspace)
        if invalid_vendors:
            return cls._blocked(
                "recommended_vendor_not_found",
                [
                    {"code": "recommended_vendor_not_found", "vendor_product_id": item}
                    for item in invalid_vendors
                ],
                workflow_type,
                artifacts,
            )

        governance = check_gate(solution.id, "arb_submission")
        if not governance.get("passed"):
            return cls._blocked(
                "governance_gate_failed",
                [
                    {"code": "governance_gate_failed", "failure": deepcopy(item)}
                    for item in governance.get("failures", [])
                ],
                workflow_type,
                artifacts,
                governance,
            )

        checks = {
            "tenant_bound": True,
            "actor_authorized": True,
            "workspace_bound": workspace is not None,
            "governance_state": solution.governance_status,
            "human_reviewed": bool(assertions.get("human_reviewed")),
            "cost_source": assertions.get("cost_source"),
            "vendor_references_resolved": True,
            "direct_route_evidence": deepcopy(assertions.get("direct_route_evidence") or {}),
        }
        return ARBReadinessResult(
            ready=True,
            workflow_type=workflow_type,
            checks=checks,
            artifacts=artifacts,
            governance_result=deepcopy(governance),
        )

    @classmethod
    def submit(
        cls,
        solution_id: int,
        actor_id: int,
        workspace_id: int | None = None,
        assertions: dict[str, Any] | None = None,
    ) -> ARBSubmissionResult:
        assertions = deepcopy(assertions or {})
        try:
            organization_id = getattr(g, "current_org_id", None) if has_request_context() else None
            if organization_id is None:
                return ARBSubmissionResult(False, ["tenant_context_missing"])
            if not evidence_immutability_is_installed(db.session.connection()):
                return ARBSubmissionResult(False, ["evidence_immutability_unavailable"])
            solution = db.session.execute(
                db.select(Solution)
                .where(
                    Solution.id == solution_id,
                    Solution.organization_id == organization_id,
                )
                .with_for_update(of=Solution)
            ).scalar_one_or_none()
            if solution is None:
                return ARBSubmissionResult(False, ["solution_not_found"])

            active = (
                db.session.execute(
                    db.select(ARBReviewItem).where(
                        ARBReviewItem.organization_id == organization_id,
                        ARBReviewItem.solution_id == solution_id,
                        ARBReviewItem.status.in_(ARB_OPEN_STATUSES),
                    )
                )
                .scalars()
                .first()
            )
            if active is not None:
                identity_failure = cls._validate_retry_identity(
                    solution, actor_id, workspace_id, organization_id
                )
                if identity_failure is not None:
                    return ARBSubmissionResult(False, [identity_failure])
                snapshot = db.session.execute(
                    db.select(ARBSubmissionEvidenceSnapshot).where(
                        ARBSubmissionEvidenceSnapshot.organization_id == organization_id,
                        ARBSubmissionEvidenceSnapshot.review_item_id == active.id,
                    )
                ).scalar_one_or_none()
                if snapshot is None:
                    return ARBSubmissionResult(False, ["active_review_snapshot_missing"])
                if snapshot.workspace_id != workspace_id:
                    return ARBSubmissionResult(False, ["workspace_identity_mismatch"])
                return ARBSubmissionResult(
                    True,
                    review_item_id=active.id,
                    review_number=active.review_number,
                    snapshot_id=snapshot.id,
                    idempotent=True,
                )
            try:
                readiness = cls._evaluate(
                    solution_id,
                    actor_id,
                    workspace_id,
                    assertions,
                    active_review=False,
                )
            except Exception:
                logger.exception("ARB readiness evaluation failed during submission")
                readiness = ARBReadinessResult(
                    False,
                    ["evaluator_unavailable"],
                    [{"code": "evaluator_unavailable"}],
                )
            if not readiness.ready:
                return ARBSubmissionResult(
                    False, readiness.reason_codes, readiness.missing_evidence
                )

            now = datetime.utcnow()
            is_resubmission = solution.governance_status == "rejected"
            notes = assertions.get("resubmission_notes") or ""
            description = f"Review request for solution: {solution.description or solution.name}"
            if is_resubmission and notes:
                description = f"[Resubmission] {notes}\n\nOriginal: {description}"
            review = ARBReviewItem(
                organization_id=organization_id,
                review_number=f"REV-{now:%Y}-{uuid.uuid4().hex[:12].upper()}",
                title=f"{'Resubmission: ' if is_resubmission else ''}Solution Review: {solution.name}",
                description=description,
                review_type="solution",
                priority="medium",
                status="submitted",
                submitter_id=actor_id,
                solution_id=solution.id,
                submitted_at=now,
            )
            db.session.add(review)
            db.session.flush()

            snapshot = ARBSubmissionEvidenceSnapshot(
                schema_version=cls.SCHEMA_VERSION,
                organization_id=organization_id,
                review_item_id=review.id,
                solution_id=solution.id,
                workspace_id=workspace_id,
                workflow_type=readiness.workflow_type,
                actor_id=actor_id,
                captured_at=now,
                checks=readiness.checks,
                artifacts=readiness.artifacts,
                governance_result=readiness.governance_result,
                request_assertions=assertions,
            )
            snapshot.content_hash = snapshot.recompute_content_hash()
            db.session.add(snapshot)

            solution.governance_status = "arb_review"
            solution.arb_submission_date = now
            solution.arb_review_item_id = review.id
            db.session.add(
                SolutionNotification(
                    solution_id=solution.id,
                    user_id=solution.created_by_id or actor_id,
                    type="arb_submission",
                    message=f"Solution '{solution.name}' submitted for ARB review.",
                )
            )
            db.session.add(
                AuditLog(
                    organization_id=organization_id,
                    user_id=actor_id,
                    action="create",
                    table_name="arb_review_items",
                    record_id=review.id,
                    new_value={"status": "submitted", "snapshot_hash": snapshot.content_hash},
                )
            )
            db.session.flush()
            db.session.commit()
            return ARBSubmissionResult(
                True,
                review_item_id=review.id,
                review_number=review.review_number,
                snapshot_id=snapshot.id,
            )
        except Exception:
            db.session.rollback()
            logger.exception("Atomic ARB submission failed")
            return ARBSubmissionResult(False, ["submission_failed"])

    @staticmethod
    def _actor_can_access(actor, solution):
        if actor.id == solution.created_by_id:
            return True
        if (
            actor.is_org_admin
            or actor.is_platform_admin
            or actor.enterprise_role == "platform_admin"
        ):
            return True
        email = (actor.email or "").strip().lower()
        return bool(
            email
            and email
            in {
                (solution.solution_owner or "").strip().lower(),
                (solution.business_sponsor or "").strip().lower(),
                (solution.technical_lead or "").strip().lower(),
            }
        )

    @classmethod
    def _validate_retry_identity(cls, solution, actor_id, workspace_id, organization_id):
        actor = db.session.execute(
            db.select(User).where(
                User.id == actor_id,
                User.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if actor is None:
            return "actor_not_found"
        if not cls._actor_can_access(actor, solution):
            return "actor_not_authorized"
        if workspace_id is None:
            return None
        workspace = db.session.execute(
            db.select(SolutionAnalysisSession).where(
                SolutionAnalysisSession.id == workspace_id,
                SolutionAnalysisSession.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if workspace is None:
            return "workspace_not_found"
        if workspace.created_by_id != actor_id:
            return "workspace_actor_mismatch"
        if (workspace.custom_metadata or {}).get("solution_id") != solution.id:
            return "workspace_solution_mismatch"
        return None

    @staticmethod
    def _has_ai_content(solution, workspace):
        session_ids = {
            session_id
            for session_id in (solution.analysis_session_id, workspace.id if workspace else None)
            if session_id is not None
        }
        if not session_ids:
            return False
        return (
            db.session.execute(
                db.select(SolutionRecommendation.id).where(
                    SolutionRecommendation.session_id.in_(session_ids),
                    SolutionRecommendation.generated_by_model.is_not(None),
                )
            ).first()
            is not None
        ) or workspace is not None

    @staticmethod
    def _invalid_vendor_references(solution, workspace):
        vendor_ids = set()
        if workspace is not None:
            recommendations = db.session.execute(
                db.select(SolutionRecommendation).where(
                    SolutionRecommendation.session_id == workspace.id,
                    SolutionRecommendation.organization_id == solution.organization_id,
                    SolutionRecommendation.is_recommended.is_(True),
                )
            ).scalars()
            for recommendation in recommendations:
                vendor_ids.update(recommendation.vendor_products or [])
        if not vendor_ids:
            return []
        from app.models.vendor.vendor_organization import VendorProduct

        resolved = set(
            db.session.execute(
                db.select(VendorProduct.id).where(VendorProduct.id.in_(vendor_ids))
            ).scalars()
        )
        return sorted(vendor_ids - resolved)

    @staticmethod
    def _blocked(code, missing=None, workflow_type=None, artifacts=None, governance=None):
        return ARBReadinessResult(
            ready=False,
            reason_codes=[code],
            missing_evidence=missing or [],
            workflow_type=workflow_type,
            artifacts=artifacts or {},
            governance_result=governance or {},
        )
