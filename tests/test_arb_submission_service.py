from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import event

from app import db
from app.models.architecture_review_board import ARBReviewItem
from app.models.audit_log import AuditLog
from app.models.solution_architect_models import SolutionAnalysisSession, SolutionSessionStatus
from app.models.solution_governance import SolutionNotification
from app.models.solution_models import Solution
from app.models.user import User
from app.models.arb_submission_evidence import ARBSubmissionEvidenceSnapshot
from app.modules.solutions_strategic.v2.services.arb_submission_service import (
    ARBSubmissionService,
)


def _user(session, org, *, admin=False):
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"arb-{suffix}@example.test",
        first_name="ARB",
        last_name="Tester",
        organization_id=org.id,
        is_org_admin=admin,
        is_platform_admin=admin,
        enterprise_role="platform_admin" if admin else "business_architect",
    )
    session.add(user)
    session.flush()
    return user


def _solution(session, org, actor, **overrides):
    values = {
        "name": f"Evidence solution {uuid.uuid4().hex[:8]}",
        "description": "A governed solution",
        "organization_id": org.id,
        "created_by_id": actor.id,
        "governance_status": "draft",
    }
    values.update(overrides)
    solution = Solution(**values)
    session.add(solution)
    session.flush()
    return solution


def _workspace(session, org, actor, solution, *, workflow_type="greenfield", artifacts=None):
    workspace = SolutionAnalysisSession(
        name=f"ARB workspace {uuid.uuid4().hex[:8]}",
        status=SolutionSessionStatus.IN_PROGRESS,
        created_by_id=actor.id,
        organization_id=org.id,
        custom_metadata={
            "workspace_type": workflow_type,
            "solution_id": solution.id,
            "artifacts": artifacts or {},
        },
    )
    session.add(workspace)
    session.flush()
    return workspace


def _artifacts(*names):
    return {
        name: {"state": "persisted", "data": {"name": name, "value": f"evidence-{name}"}}
        for name in names
    }


def _ready_assertions(**overrides):
    values = {"human_reviewed": True, "direct_route_checks": {"design_reviewed": True}}
    values.update(overrides)
    return values


@pytest.fixture
def passing_gate(monkeypatch):
    monkeypatch.setattr(
        "app.modules.solutions_strategic.v2.services.arb_submission_service.check_gate",
        lambda solution_id, gate_name: {
            "passed": True,
            "failures": [],
            "gate_name": gate_name,
        },
    )


def test_evaluate_binds_tenant_actor_workspace_and_derives_workflow(
    db_session, make_org, tenant_ctx, passing_gate
):
    org_a, org_b = make_org("arb-a"), make_org("arb-b")
    owner = _user(db_session, org_a)
    outsider = _user(db_session, org_a)
    foreign = _user(db_session, org_b)
    solution = _solution(db_session, org_a, owner)
    workspace = _workspace(
        db_session,
        org_a,
        owner,
        solution,
        workflow_type="brownfield",
        artifacts=_artifacts(
            "portfolio_context", "current_state", "gap_analysis", "transition_plan"
        ),
    )

    with tenant_ctx(org_a.id):
        result = ARBSubmissionService.evaluate(
            solution.id, owner.id, workspace.id, _ready_assertions()
        )
        unauthorized = ARBSubmissionService.evaluate(
            solution.id, outsider.id, workspace.id, _ready_assertions()
        )
        foreign_actor = ARBSubmissionService.evaluate(
            solution.id, foreign.id, workspace.id, _ready_assertions()
        )

    assert result.ready is True
    assert result.workflow_type == "brownfield"
    assert unauthorized.reason_codes == ["actor_not_authorized"]
    assert foreign_actor.reason_codes == ["actor_not_found"]


def test_evaluate_requires_each_named_artifact_at_persisted_state(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("artifacts")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    artifacts = _artifacts("brief", "recommendation")
    artifacts["scope"] = {"state": "confirmed", "data": {"value": "not persisted"}}
    workspace = _workspace(db_session, org, owner, solution, artifacts=artifacts)

    with tenant_ctx(org.id):
        result = ARBSubmissionService.evaluate(
            solution.id, owner.id, workspace.id, _ready_assertions()
        )

    assert result.ready is False
    assert result.reason_codes == ["missing_named_artifacts"]
    assert result.missing_evidence == [
        {"code": "artifact_not_persisted", "artifact": "scope", "required_state": "persisted"}
    ]


def test_direct_submission_requires_and_snapshots_explicit_checks(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("direct")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)

    with tenant_ctx(org.id):
        blocked = ARBSubmissionService.evaluate(
            solution.id, owner.id, assertions={"human_reviewed": True}
        )
        submitted = ARBSubmissionService.submit(
            solution.id, owner.id, assertions=_ready_assertions()
        )

    assert blocked.reason_codes == ["missing_direct_route_evidence"]
    snapshot = db_session.get(ARBSubmissionEvidenceSnapshot, submitted.snapshot_id)
    assert snapshot.workflow_type == "direct"
    assert snapshot.artifacts == {}
    assert snapshot.checks["direct_route_checks"] == {"design_reviewed": True}


def test_evaluator_exception_fails_closed_without_writes(
    db_session, make_org, tenant_ctx, monkeypatch
):
    org = make_org("exception")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    monkeypatch.setattr(
        "app.modules.solutions_strategic.v2.services.arb_submission_service.check_gate",
        lambda *_: (_ for _ in ()).throw(RuntimeError("database detail must not leak")),
    )

    with tenant_ctx(org.id):
        evaluation = ARBSubmissionService.evaluate(
            solution.id, owner.id, assertions=_ready_assertions()
        )
        submission = ARBSubmissionService.submit(
            solution.id, owner.id, assertions=_ready_assertions()
        )

    assert evaluation.reason_codes == ["evaluator_unavailable"]
    assert "database detail" not in repr(evaluation)
    assert submission.success is False
    assert submission.reason_codes == ["evaluator_unavailable"]
    assert db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count() == 0
    assert (
        db_session.query(ARBSubmissionEvidenceSnapshot).filter_by(solution_id=solution.id).count()
        == 0
    )


def test_submit_is_idempotent_for_an_active_review(db_session, make_org, tenant_ctx, passing_gate):
    org = make_org("retry")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)

    with tenant_ctx(org.id):
        first = ARBSubmissionService.submit(solution.id, owner.id, assertions=_ready_assertions())
        second = ARBSubmissionService.submit(solution.id, owner.id, assertions=_ready_assertions())

    assert first.success is True and first.idempotent is False
    assert second.success is True and second.idempotent is True
    assert second.review_item_id == first.review_item_id
    assert second.snapshot_id == first.snapshot_id
    assert db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count() == 1
    assert (
        db_session.query(ARBSubmissionEvidenceSnapshot).filter_by(solution_id=solution.id).count()
        == 1
    )


def test_submit_atomically_writes_canonical_records_and_snapshot(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("atomic")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner, estimated_cost=Decimal("125.00"))
    workspace = _workspace(
        db_session,
        org,
        owner,
        solution,
        artifacts=_artifacts("brief", "scope", "recommendation"),
    )
    assertions = _ready_assertions(cost_source="manual_override", resubmission_notes="Updated")

    with tenant_ctx(org.id):
        result = ARBSubmissionService.submit(solution.id, owner.id, workspace.id, assertions)

    review = db_session.get(ARBReviewItem, result.review_item_id)
    snapshot = db_session.get(ARBSubmissionEvidenceSnapshot, result.snapshot_id)
    db_session.refresh(solution)
    assert result.success is True
    assert review.organization_id == org.id and review.submitter_id == owner.id
    assert solution.governance_status == "arb_review"
    assert solution.arb_review_item_id == review.id
    assert solution.arb_submission_date is not None
    assert snapshot.review_item_id == review.id
    assert snapshot.organization_id == org.id
    assert snapshot.actor_id == owner.id
    assert snapshot.workspace_id == workspace.id
    assert snapshot.request_assertions == assertions
    assert snapshot.artifacts["recommendation"]["data"]["value"] == "evidence-recommendation"
    assert len(snapshot.content_hash) == 64
    assert db_session.query(SolutionNotification).filter_by(solution_id=solution.id).count() == 1
    assert (
        db_session.query(AuditLog)
        .filter_by(table_name="arb_review_items", record_id=review.id)
        .count()
        == 1
    )


def test_required_write_failure_rolls_back_every_submission_change(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("rollback")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    solution_id = solution.id
    db_session.commit()

    def fail_snapshot_insert(_mapper, _connection, _target):
        raise RuntimeError("forced snapshot failure")

    event.listen(ARBSubmissionEvidenceSnapshot, "before_insert", fail_snapshot_insert)
    try:
        with tenant_ctx(org.id):
            result = ARBSubmissionService.submit(
                solution.id, owner.id, assertions=_ready_assertions()
            )
    finally:
        event.remove(ARBSubmissionEvidenceSnapshot, "before_insert", fail_snapshot_insert)

    assert result.success is False
    assert result.reason_codes == ["submission_failed"]
    assert db_session.query(ARBReviewItem).filter_by(solution_id=solution_id).count() == 0
    assert (
        db_session.query(ARBSubmissionEvidenceSnapshot).filter_by(solution_id=solution_id).count()
        == 0
    )
    persisted_solution = db_session.get(Solution, solution_id)
    assert persisted_solution.governance_status == "draft"
    assert persisted_solution.arb_review_item_id is None


def test_snapshot_rejects_updates_and_retains_captured_payload(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("immutable")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    artifacts = _artifacts("brief", "scope", "recommendation")
    workspace = _workspace(db_session, org, owner, solution, artifacts=artifacts)

    with tenant_ctx(org.id):
        result = ARBSubmissionService.submit(
            solution.id, owner.id, workspace.id, _ready_assertions()
        )

    snapshot = db_session.get(ARBSubmissionEvidenceSnapshot, result.snapshot_id)
    captured = deepcopy(snapshot.artifacts)
    workspace.custom_metadata = {**workspace.custom_metadata, "artifacts": {}}
    db_session.flush()
    assert snapshot.artifacts == captured

    snapshot.workflow_type = "tampered"
    with pytest.raises(ValueError, match="append-only"):
        db_session.flush()
    db_session.rollback()
