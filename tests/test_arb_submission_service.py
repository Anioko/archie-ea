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
        readiness = ARBSubmissionService.evaluate(
            solution.id, owner.id, assertions=_ready_assertions()
        )
        snapshot = ARBSubmissionService.build_evidence_snapshot(
            organization_id=org.id,
            solution_id=solution.id,
            actor_id=owner.id,
            workspace_id=None,
            assertions=_ready_assertions(),
            readiness=readiness,
        )

    assert blocked.reason_codes == ["missing_direct_route_evidence"]
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

    assert evaluation.reason_codes == ["evaluator_unavailable"]
    assert "database detail" not in repr(evaluation)
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

    assert not [item for item in added if "evidence" in item]
    assert not [item for item in failed if "evidence" in item]
    assert not [item for item in missing_tables if "evidence" in item]
    assert not [item for item in blocking if "evidence" in item]
    assert first_apply[1] == []
    assert second_apply[1] == []


# The 11 retired direct-writer tests were removed only after ownership and their
# executable contracts moved to these named typed tests:
# - idempotence/fresh-session/evidence-change replay:
#   test_replay_returns_the_original_ids_without_re_evaluating_or_resnapshotting,
#   test_real_adr_submission_is_atomic_and_same_key_replay_is_stable, and
#   test_different_command_key_reconciles_to_the_same_open_cycle;
# - atomic Solution graph and rollback:
#   test_real_solution_submission_pins_legacy_evidence_into_typed_graph,
#   test_review_item_insert_failure_rolls_back_snapshot_cycle_and_result, and
#   test_submission_event_insert_failure_rolls_back_entire_graph;
# - missing tenant/facade-only behavior:
#   test_legacy_solution_facade_delegates_without_direct_review_write and
#   test_adapter_maps_domain_errors_to_safe_legacy_results;
# - runtime schema guards, immutable snapshots, and concurrency:
#   test_reconcile_installs_typed_arb_constraints_idempotently,
#   test_reconcile_repairs_missing_disabled_and_malformed_typed_guards,
#   test_direct_sql_cannot_rewrite_typed_snapshot_or_history, and
#   test_database_rejects_two_open_cycles_for_one_typed_subject.
