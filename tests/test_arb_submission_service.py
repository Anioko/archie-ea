from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import uuid
import threading

import pytest
import psycopg2
from sqlalchemy import event
from flask import g

from app import db
from app.models.architecture_review_board import ARBReviewItem
from app.models.audit_log import AuditLog
from app.models.solution_architect_models import (
    RecommendationOptionType,
    SolutionAnalysisSession,
    SolutionRecommendation,
    SolutionSessionStatus,
)
from app.models.solution_governance import SolutionNotification
from app.models.solution_models import Solution
from app.models.user import User
from app.models.vendor.vendor_organization import VendorOrganization, VendorProduct
from app.models.arb_submission_evidence import (
    ARBSubmissionEvidenceSnapshot,
    WorkbenchArtifactEvidence,
    evidence_immutability_is_installed,
    ensure_evidence_immutability_triggers,
)
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
    for name, artifact in (artifacts or {}).items():
        WorkbenchArtifactEvidence.capture(
            organization_id=org.id,
            workspace_id=workspace.id,
            solution_id=solution.id,
            name=name,
            state=artifact["state"],
            payload=artifact.get("data") or {},
            actor_id=actor.id,
        )
    session.flush()
    return workspace


def _artifacts(*names):
    return {
        name: {"state": "persisted", "data": {"name": name, "value": f"evidence-{name}"}}
        for name in names
    }


def _ready_assertions(**overrides):
    values = {
        "human_reviewed": True,
        "direct_route_evidence": {
            "design_reviewed": {"passed": True, "evidence": "Architecture design checked"},
            "security_impact_reviewed": {"passed": True, "evidence": "Security impact checked"},
            "data_impact_reviewed": {"passed": True, "evidence": "Data impact checked"},
        },
    }
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


def test_cross_tenant_solution_and_workspace_ids_are_not_resolved(
    db_session, make_org, tenant_ctx, passing_gate
):
    org_a, org_b = make_org("cross-a"), make_org("cross-b")
    owner_a, owner_b = _user(db_session, org_a), _user(db_session, org_b)
    solution_a = _solution(db_session, org_a, owner_a)
    solution_b = _solution(db_session, org_b, owner_b)
    workspace_b = _workspace(db_session, org_b, owner_b, solution_b)

    with tenant_ctx(org_a.id):
        foreign_solution = ARBSubmissionService.evaluate(
            solution_b.id, owner_a.id, assertions=_ready_assertions()
        )
        foreign_workspace = ARBSubmissionService.evaluate(
            solution_a.id, owner_a.id, workspace_b.id, _ready_assertions()
        )

    assert foreign_solution.reason_codes == ["solution_not_found"]
    assert foreign_workspace.reason_codes == ["workspace_not_found"]


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
    assert snapshot.checks["direct_route_evidence"] == _ready_assertions()["direct_route_evidence"]


def test_mutable_workspace_metadata_cannot_satisfy_required_evidence(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("mutable-metadata")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    workspace = _workspace(db_session, org, owner, solution)
    workspace.custom_metadata = {
        **workspace.custom_metadata,
        "artifacts": _artifacts("brief", "scope", "recommendation"),
    }
    db_session.flush()

    with tenant_ctx(org.id):
        result = ARBSubmissionService.evaluate(
            solution.id, owner.id, workspace.id, _ready_assertions()
        )

    assert result.ready is False
    assert [item["artifact"] for item in result.missing_evidence] == [
        "brief",
        "scope",
        "recommendation",
    ]


@pytest.mark.parametrize(
    "missing_name", ["design_reviewed", "security_impact_reviewed", "data_impact_reviewed"]
)
def test_direct_submission_requires_each_named_check_with_evidence(
    db_session, make_org, tenant_ctx, passing_gate, missing_name
):
    org = make_org(f"direct-{missing_name}")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    assertions = _ready_assertions()
    assertions["direct_route_evidence"].pop(missing_name)

    with tenant_ctx(org.id):
        result = ARBSubmissionService.evaluate(solution.id, owner.id, assertions=assertions)

    assert result.reason_codes == ["missing_direct_route_evidence"]
    assert result.missing_evidence == [
        {"code": "direct_route_check_missing", "check": missing_name}
    ]


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


def test_workspace_owner_solution_and_workflow_binding_fail_closed(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("workspace-binding")
    owner = _user(db_session, org)
    other = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    other_solution = _solution(db_session, org, owner)
    owner_mismatch = _workspace(db_session, org, other, solution)
    solution_mismatch = _workspace(db_session, org, owner, other_solution)
    invalid_workflow = _workspace(db_session, org, owner, solution, workflow_type="invented")

    with tenant_ctx(org.id):
        assert ARBSubmissionService.evaluate(
            solution.id, owner.id, owner_mismatch.id, _ready_assertions()
        ).reason_codes == ["workspace_actor_mismatch"]
        assert ARBSubmissionService.evaluate(
            solution.id, owner.id, solution_mismatch.id, _ready_assertions()
        ).reason_codes == ["workspace_solution_mismatch"]
        assert ARBSubmissionService.evaluate(
            solution.id, owner.id, invalid_workflow.id, _ready_assertions()
        ).reason_codes == ["workspace_workflow_invalid"]


def test_named_stakeholder_and_admin_have_solution_access(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("access-contract")
    owner = _user(db_session, org)
    stakeholder = _user(db_session, org)
    admin = _user(db_session, org, admin=True)
    solution = _solution(db_session, org, owner, technical_lead=stakeholder.email)

    with tenant_ctx(org.id):
        stakeholder_result = ARBSubmissionService.evaluate(
            solution.id, stakeholder.id, assertions=_ready_assertions()
        )
        admin_result = ARBSubmissionService.evaluate(
            solution.id, admin.id, assertions=_ready_assertions()
        )

    assert stakeholder_result.ready is True
    assert admin_result.ready is True


def test_human_review_cost_vendor_and_governance_requirements(
    db_session, make_org, tenant_ctx, passing_gate, monkeypatch
):
    org = make_org("evidence-requirements")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner, estimated_cost=Decimal("1.00"))
    workspace = _workspace(
        db_session,
        org,
        owner,
        solution,
        artifacts=_artifacts("brief", "scope", "recommendation"),
    )
    recommendation = SolutionRecommendation(
        organization_id=org.id,
        session_id=workspace.id,
        option_type=RecommendationOptionType.BUY,
        is_recommended=True,
        vendor_products=[999999999],
        generated_by_model="test-model",
    )
    db_session.add(recommendation)
    db_session.flush()

    with tenant_ctx(org.id):
        no_human = ARBSubmissionService.evaluate(
            solution.id, owner.id, workspace.id, {"cost_source": "manual_override"}
        )
        no_cost_source = ARBSubmissionService.evaluate(
            solution.id, owner.id, workspace.id, {"human_reviewed": True}
        )
        bad_vendor = ARBSubmissionService.evaluate(
            solution.id,
            owner.id,
            workspace.id,
            {"human_reviewed": True, "cost_source": "manual_override"},
        )
        vendor = VendorOrganization(name=f"Valid Vendor {uuid.uuid4().hex[:10]}")
        db_session.add(vendor)
        db_session.flush()
        product = VendorProduct(vendor_organization_id=vendor.id, name="Valid Product")
        db_session.add(product)
        db_session.flush()
        recommendation.vendor_products = [product.id]
        db_session.flush()
        valid_vendor = ARBSubmissionService.evaluate(
            solution.id,
            owner.id,
            workspace.id,
            {"human_reviewed": True, "cost_source": "manual_override"},
        )
        monkeypatch.setattr(
            "app.modules.solutions_strategic.v2.services.arb_submission_service.check_gate",
            lambda *_: {"passed": False, "failures": [{"reason": "missing goal"}]},
        )
        gate_blocked = ARBSubmissionService.evaluate(
            solution.id,
            owner.id,
            workspace.id,
            {"human_reviewed": True, "cost_source": "manual_override"},
        )

    assert no_human.reason_codes == ["human_review_required"]
    assert no_cost_source.reason_codes == ["cost_source_required"]
    assert bad_vendor.reason_codes == ["recommended_vendor_not_found"]
    assert valid_vendor.ready is True
    assert gate_blocked.reason_codes == ["governance_gate_failed"]


def test_evidence_schema_is_nullable_compatible_and_reconcile_safe(app, _schema):
    from app.commands.reconcile_schema import _reconcile

    nullable_columns = [
        column
        for model in (ARBSubmissionEvidenceSnapshot, WorkbenchArtifactEvidence)
        for column in model.__table__.columns
        if not column.primary_key
    ]
    assert all(column.nullable for column in nullable_columns)
    assert "review_number" not in ARBSubmissionEvidenceSnapshot.__table__.columns

    with app.app_context():
        added, failed, missing_tables, blocking = _reconcile(dry_run=True)
        first_apply = _reconcile(dry_run=False)
        second_apply = _reconcile(dry_run=False)
        immutability_installed = evidence_immutability_is_installed(
            db.session.connection()
        )

    assert not [item for item in added if "evidence" in item]
    assert not [item for item in failed if "evidence" in item]
    assert not [item for item in missing_tables if "evidence" in item]
    assert not [item for item in blocking if "evidence" in item]
    assert first_apply[1] == []
    assert second_apply[1] == []
    assert immutability_installed is True


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


def test_retry_from_a_fresh_database_session_returns_one_canonical_review(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("fresh-session-retry")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    org_id, owner_id, solution_id = org.id, owner.id, solution.id

    with tenant_ctx(org_id):
        first = ARBSubmissionService.submit(solution_id, owner_id, assertions=_ready_assertions())
    db.session.remove()

    with tenant_ctx(org_id):
        second = ARBSubmissionService.submit(solution_id, owner_id, assertions={})

    assert first.success is True
    assert second.success is True and second.idempotent is True
    assert second.review_item_id == first.review_item_id
    assert db.session.query(ARBReviewItem).filter_by(solution_id=solution_id).count() == 1


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
    assert snapshot.content_hash == snapshot.recompute_content_hash()
    assert db_session.query(SolutionNotification).filter_by(solution_id=solution.id).count() == 1
    assert (
        db_session.query(AuditLog)
        .filter_by(table_name="arb_review_items", record_id=review.id)
        .count()
        == 1
    )


def test_active_retry_uses_captured_snapshot_after_current_evidence_changes(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("retry-mutation")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    workspace = _workspace(
        db_session,
        org,
        owner,
        solution,
        artifacts=_artifacts("brief", "scope", "recommendation"),
    )

    with tenant_ctx(org.id):
        first = ARBSubmissionService.submit(
            solution.id, owner.id, workspace.id, _ready_assertions()
        )
        workspace.custom_metadata = {**workspace.custom_metadata, "artifacts": {}}
        db_session.flush()
        second = ARBSubmissionService.submit(solution.id, owner.id, workspace.id, {})

    assert second.success is True
    assert second.idempotent is True
    assert second.review_item_id == first.review_item_id
    assert second.snapshot_id == first.snapshot_id


def test_submit_preserves_tenant_context_missing_reason(db_session, make_org, passing_gate):
    org = make_org("no-context")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)

    result = ARBSubmissionService.submit(solution.id, owner.id, assertions=_ready_assertions())

    assert result.reason_codes == ["tenant_context_missing"]


def test_runtime_submission_executes_no_schema_ddl(db_session, make_org, tenant_ctx, passing_gate):
    org = make_org("runtime-no-ddl")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    statements = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(db.engine, "before_cursor_execute", record_statement)
    try:
        with tenant_ctx(org.id):
            result = ARBSubmissionService.submit(
                solution.id, owner.id, assertions=_ready_assertions()
            )
    finally:
        event.remove(db.engine, "before_cursor_execute", record_statement)

    assert result.success is True
    ddl_prefixes = ("CREATE ", "ALTER ", "DROP ", "DO ", "SELECT PG_ADVISORY")
    assert not [
        statement for statement in statements if statement.lstrip().upper().startswith(ddl_prefixes)
    ]


def test_missing_database_trigger_blocks_runtime_submission_with_precise_reason(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("missing-trigger")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    connection = db_session.connection()
    connection.exec_driver_sql(
        "DROP TRIGGER IF EXISTS trg_reject_evidence_mutation ON arb_submission_evidence_snapshots"
    )

    try:
        with tenant_ctx(org.id):
            result = ARBSubmissionService.submit(
                solution.id, owner.id, assertions=_ready_assertions()
            )
        assert result.success is False
        assert result.reason_codes == ["evidence_immutability_unavailable"]
        assert db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count() == 0
    finally:
        ensure_evidence_immutability_triggers(connection)


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


def test_append_only_snapshot_rejects_bulk_and_raw_mutation(
    db_session, make_org, tenant_ctx, passing_gate
):
    org = make_org("bulk-immutable")
    owner = _user(db_session, org)
    solution = _solution(db_session, org, owner)
    workspace = _workspace(
        db_session,
        org,
        owner,
        solution,
        artifacts=_artifacts("brief", "scope", "recommendation"),
    )
    with tenant_ctx(org.id):
        result = ARBSubmissionService.submit(
            solution.id, owner.id, workspace.id, _ready_assertions()
        )

    with pytest.raises(ValueError, match="append-only"):
        db_session.execute(
            db.update(ARBSubmissionEvidenceSnapshot)
            .where(ARBSubmissionEvidenceSnapshot.id == result.snapshot_id)
            .values(workflow_type="tampered")
        )
    db_session.rollback()

    with pytest.raises(ValueError, match="append-only"):
        db_session.execute(
            db.text("DELETE FROM arb_submission_evidence_snapshots WHERE id = :snapshot_id"),
            {"snapshot_id": result.snapshot_id},
        )


def test_two_concurrent_transactions_create_one_review_and_database_rejects_raw_mutation(
    app, _schema, monkeypatch
):
    monkeypatch.setattr(
        "app.modules.solutions_strategic.v2.services.arb_submission_service.check_gate",
        lambda *_: {"passed": True, "failures": [], "gate_name": "arb_submission"},
    )
    from app.models.organization import Organization

    with app.app_context():
        suffix = uuid.uuid4().hex[:10]
        org = Organization(name=f"Concurrent {suffix}", slug=f"concurrent-{suffix}")
        db.session.add(org)
        db.session.flush()
        owner = _user(db.session, org)
        solution = _solution(db.session, org, owner)
        workspace = _workspace(
            db.session,
            org,
            owner,
            solution,
            artifacts=_artifacts("brief", "scope", "recommendation"),
        )
        db.session.commit()
        artifact_id = (
            db.session.query(WorkbenchArtifactEvidence.id)
            .filter_by(workspace_id=workspace.id, name="brief")
            .scalar()
        )
        org_id, owner_id, solution_id, workspace_id = (
            org.id,
            owner.id,
            solution.id,
            workspace.id,
        )

    barrier = threading.Barrier(2)
    results = []
    errors = []

    def submit_from_independent_transaction():
        try:
            with app.test_request_context("/"):
                g.current_org_id = org_id
                barrier.wait(timeout=10)
                results.append(
                    ARBSubmissionService.submit(
                        solution_id,
                        owner_id,
                        workspace_id,
                        assertions=_ready_assertions(),
                    )
                )
                db.session.remove()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=submit_from_independent_transaction) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert errors == []
    assert len(results) == 2
    assert {result.review_item_id for result in results} == {results[0].review_item_id}
    assert sorted(result.idempotent for result in results) == [False, True]

    with app.app_context():
        assert db.session.query(ARBReviewItem).filter_by(solution_id=solution_id).count() == 1
        snapshot = (
            db.session.query(ARBSubmissionEvidenceSnapshot).filter_by(solution_id=solution_id).one()
        )
        snapshot_id = snapshot.id
        db.session.remove()

    database_url = app.config["SQLALCHEMY_DATABASE_URI"]
    raw = psycopg2.connect(database_url)
    try:
        for statement in (
            f"/* immutable */ UPDATE public.arb_submission_evidence_snapshots SET workflow_type='x' WHERE id={snapshot_id}",
            f"WITH target AS (SELECT {snapshot_id} AS id) DELETE FROM arb_submission_evidence_snapshots USING target WHERE arb_submission_evidence_snapshots.id=target.id",
            f"DELETE FROM public.arb_submission_evidence_snapshots WHERE id={snapshot_id}",
            f"/* immutable */ UPDATE public.workbench_artifact_evidence SET state='draft' WHERE id={artifact_id}",
            f"WITH target AS (SELECT {artifact_id} AS id) DELETE FROM workbench_artifact_evidence USING target WHERE workbench_artifact_evidence.id=target.id",
        ):
            with pytest.raises(psycopg2.Error, match="append-only"):
                with raw.cursor() as cursor:
                    cursor.execute(statement)
            raw.rollback()
    finally:
        with raw.cursor() as cursor:
            cursor.execute("ALTER TABLE arb_submission_evidence_snapshots DISABLE TRIGGER USER")
            cursor.execute(
                "DELETE FROM arb_submission_evidence_snapshots WHERE solution_id=%s",
                (solution_id,),
            )
            cursor.execute("ALTER TABLE arb_submission_evidence_snapshots ENABLE TRIGGER USER")
            cursor.execute("ALTER TABLE workbench_artifact_evidence DISABLE TRIGGER USER")
            cursor.execute(
                "DELETE FROM workbench_artifact_evidence WHERE solution_id=%s", (solution_id,)
            )
            cursor.execute("ALTER TABLE workbench_artifact_evidence ENABLE TRIGGER USER")
            cursor.execute(
                "DELETE FROM solution_notifications WHERE solution_id=%s", (solution_id,)
            )
            cursor.execute("DELETE FROM soc2_audit_log WHERE organization_id=%s", (org_id,))
            cursor.execute(
                "UPDATE solutions SET arb_review_item_id=NULL WHERE id=%s", (solution_id,)
            )
            cursor.execute("DELETE FROM arb_review_items WHERE solution_id=%s", (solution_id,))
            cursor.execute("DELETE FROM solutions WHERE id=%s", (solution_id,))
            cursor.execute("DELETE FROM solution_analysis_sessions WHERE id=%s", (workspace_id,))
            cursor.execute("DELETE FROM users WHERE id=%s", (owner_id,))
            cursor.execute("DELETE FROM organizations WHERE id=%s", (org_id,))
        raw.commit()
        raw.close()
