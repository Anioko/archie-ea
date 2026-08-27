from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import uuid

from app.models.arb_submission_evidence import WorkbenchArtifactEvidence
from app.models.solution_architect_models import (
    SolutionAnalysisSession,
    SolutionSessionStatus,
)
from app.models.solution_models import Solution
from app.models.user import User
from app.modules.ai_chat.services.agent_runner import AgentRunner
from app.modules.ai_chat.services.ai_chat_approval_service import AIChatApprovalService
from app.modules.ai_chat.services.workbench_kernel import ArtifactState, WorkbenchKernel
from app.modules.ai_chat.tools.executor import ToolCall, ToolExecutor
from app.modules.ai_chat.tools.registry import TOOL_SCHEMA_BY_NAME
from app.modules.solutions_strategic.v2.services.arb_submission_service import (
    ARBSubmissionResult,
)


def _user(session, org):
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"ai-arb-{suffix}@example.test",
        first_name="AI",
        last_name="Architect",
        organization_id=org.id,
        enterprise_role="platform_admin",
        is_org_admin=True,
        is_platform_admin=True,
    )
    session.add(user)
    session.flush()
    return user


def _solution(session, org, actor):
    solution = Solution(
        name=f"AI ARB {uuid.uuid4().hex[:8]}",
        description="Evidence-gated AI submission",
        organization_id=org.id,
        created_by_id=actor.id,
        governance_status="draft",
    )
    session.add(solution)
    session.flush()
    return solution


def _workspace(session, org, actor, solution):
    workspace = SolutionAnalysisSession(
        name=f"AI workspace {uuid.uuid4().hex[:8]}",
        status=SolutionSessionStatus.IN_PROGRESS,
        created_by_id=actor.id,
        organization_id=org.id,
        custom_metadata={
            "workspace_type": "greenfield",
            "solution_id": solution.id,
            "artifacts": {},
        },
    )
    session.add(workspace)
    session.flush()
    return workspace


def test_registry_does_not_offer_workspace_or_workflow_identity_to_the_llm():
    properties = TOOL_SCHEMA_BY_NAME["submit_for_arb_review"]["parameters"]["properties"]

    assert "workspace_id" not in properties
    assert "workflow_type" not in properties
    assert "phase" not in properties


def test_runner_overwrites_llm_workspace_and_discards_workflow_selection():
    arguments = AgentRunner._inject_trusted_tool_context(
        "submit_for_arb_review",
        {
            "solution_name": "Customer Platform",
            "workspace_id": 999,
            "workflow_type": "brownfield",
        },
        trusted_workspace_id=42,
    )

    assert arguments == {"solution_name": "Customer Platform", "workspace_id": 42}


def test_runner_strips_model_controlled_cost_provenance_and_attestations():
    arguments = AgentRunner._inject_trusted_tool_context(
        "submit_for_arb_review",
        {
            "solution_name": "Costed Platform",
            "cost_source": "tco_engine",
            "human_reviewed": True,
            "direct_route_evidence": {"design_reviewed": True},
        },
        trusted_workspace_id=42,
    )

    assert arguments == {"solution_name": "Costed Platform", "workspace_id": 42}


def test_executor_requires_trusted_workspace_for_ai_submission(
    db_session, make_org, tenant_ctx
):
    org = make_org("ai-arb-tool-block")
    actor = _user(db_session, org)
    solution = _solution(db_session, org, actor)

    with tenant_ctx(org.id):
        executor = ToolExecutor(actor.id)
        executor._user_can_write = lambda: True
        executor._resolver.resolve_solution = lambda _name: {
            "resolved": True,
            "id": solution.id,
            "name": solution.name,
        }
        result = executor.execute(
            ToolCall("call-1", "submit_for_arb_review", {"solution_name": solution.name})
        )

    assert result["success"] is False
    assert result["reason_codes"] == ["trusted_workspace_required"]
    assert solution.governance_status == "draft"


def test_executor_delegates_to_canonical_service_with_trusted_identity(
    db_session, make_org, tenant_ctx, monkeypatch
):
    org = make_org("ai-arb-tool-submit")
    actor = _user(db_session, org)
    solution = _solution(db_session, org, actor)
    workspace = _workspace(db_session, org, actor, solution)
    calls = []

    def submit(**kwargs):
        calls.append(kwargs)
        return ARBSubmissionResult(
            True, review_item_id=73, review_number="REV-2026-TEST", snapshot_id=91
        )

    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionAdapter.submit_solution_for_actor",
        submit,
    )
    with tenant_ctx(org.id):
        executor = ToolExecutor(actor.id)
        monkeypatch.setattr(executor, "_user_can_write", lambda: True)
        executor._resolver.resolve_solution = lambda _name: {
            "resolved": True,
            "id": solution.id,
            "name": solution.name,
        }
        result = executor.execute(
            ToolCall(
                "call-2",
                "submit_for_arb_review",
                {"solution_name": solution.name, "workspace_id": workspace.id},
            )
        )

    assert calls == [{
        "actor_id": actor.id,
        "solution_id": solution.id,
        "trusted_workspace_id": workspace.id,
        "trusted_human_reviewed": True,
        "command_key": (
            "ai-tool-3ba8dced2e729b165dfb4e6a16f08d0f81338b045127b9a57cbc62f0853ec592"
        ),
    }]
    assert result["success"] is True
    assert result["result"] == {
        "solution": solution.name,
        "review_item_id": 73,
        "review_number": "REV-2026-TEST",
        "snapshot_id": 91,
        "idempotent": False,
        "review_cycle_id": None,
        "canonical_url": None,
    }
    assert solution.governance_status == "draft"


def test_executor_rejects_model_supplied_workspace_not_bound_to_solution(
    db_session, make_org, tenant_ctx, monkeypatch
):
    org = make_org("ai-arb-tool-forged-workspace")
    actor = _user(db_session, org)
    solution = _solution(db_session, org, actor)
    other_solution = _solution(db_session, org, actor)
    forged_workspace = _workspace(db_session, org, actor, other_solution)

    def must_not_submit(**_kwargs):
        raise AssertionError("an unverified workspace reached the trusted adapter")

    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionAdapter.submit_solution_for_actor",
        must_not_submit,
    )
    with tenant_ctx(org.id):
        executor = ToolExecutor(actor.id)
        monkeypatch.setattr(executor, "_user_can_write", lambda: True)
        executor._resolver.resolve_solution = lambda _name: {
            "resolved": True,
            "id": solution.id,
            "name": solution.name,
        }
        result = executor.execute(
            ToolCall(
                "forged-workspace",
                "submit_for_arb_review",
                {
                    "solution_name": solution.name,
                    "workspace_id": forged_workspace.id,
                },
            )
        )

    assert result["success"] is False
    assert result["reason_codes"] == ["trusted_workspace_required"]
    assert solution.governance_status == "draft"


def test_costed_executor_block_returns_canonical_architect_recovery(
    db_session, make_org, tenant_ctx, monkeypatch
):
    org = make_org("ai-cost-recovery")
    actor = _user(db_session, org)
    solution = _solution(db_session, org, actor)
    solution.estimated_cost = Decimal("250000.00")
    workspace = _workspace(db_session, org, actor, solution)
    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionAdapter.submit_solution_for_actor",
        lambda **_kwargs: ARBSubmissionResult(
            False,
            ["cost_source_required"],
            [{"code": "cost_source_required"}],
        ),
    )
    with tenant_ctx(org.id):
        executor = ToolExecutor(actor.id)
        monkeypatch.setattr(executor, "_user_can_write", lambda: True)
        executor._resolver.resolve_solution = lambda _name: {
            "resolved": True,
            "id": solution.id,
            "name": solution.name,
        }
        result = executor.execute(
            ToolCall(
                "cost-call",
                "submit_for_arb_review",
                {
                    "solution_name": solution.name,
                    "workspace_id": workspace.id,
                    "cost_source": "tco_engine",
                },
            )
        )

    assert result["success"] is False
    assert result["recovery"]["url"] == f"/solutions/{solution.id}?tab=governance"
    assert result["recovery"]["action"] == "architect_cost_provenance_review_required"
    assert "architect" in result["recovery"]["message"].lower()


def test_costed_workbench_block_returns_same_canonical_recovery(
    db_session, make_org, tenant_ctx, monkeypatch
):
    org = make_org("workbench-cost-recovery")
    actor = _user(db_session, org)
    solution = _solution(db_session, org, actor)
    solution.estimated_cost = Decimal("250000.00")
    workspace = _workspace(db_session, org, actor, solution)
    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionAdapter.submit_solution_for_actor",
        lambda **_kwargs: ARBSubmissionResult(
            False, ["cost_source_required"], [{"code": "cost_source_required"}]
        ),
    )
    with tenant_ctx(org.id):
        result = WorkbenchKernel(user_id=actor.id).submit_to_arb(workspace.id)

    assert result["success"] is False
    assert result["recovery"]["url"] == f"/solutions/{solution.id}?tab=governance"
    assert result["recovery"]["action"] == "architect_cost_provenance_review_required"


def test_approved_agent_tool_surfaces_structured_cost_recovery():
    tool_result = {
        "success": False,
        "error": "Architect review required",
        "reason_codes": ["cost_source_required"],
        "missing_evidence": [{"code": "cost_source_required"}],
        "recovery": {
            "action": "architect_cost_provenance_review_required",
            "url": "/solutions/42?tab=governance",
        },
    }

    response = AIChatApprovalService._execution_failure_response(tool_result, 17)

    assert response["success"] is False
    assert response["approval_id"] == 17
    assert response["reason_codes"] == ["cost_source_required"]
    assert response["recovery"] == tool_result["recovery"]


def test_workbench_missing_trusted_workspace_is_a_structured_blocker():
    result = WorkbenchKernel(user_id=7).submit_to_arb(None)

    assert result == {
        "success": False,
        "reason_codes": ["trusted_workspace_required"],
        "missing_evidence": [
            {"code": "trusted_workspace_required", "action": "Open a solution workbench"}
        ],
    }


def test_workbench_persists_artifact_evidence_then_records_only_canonical_success(
    db_session, make_org, tenant_ctx, monkeypatch
):
    org = make_org("ai-arb-workbench")
    actor = _user(db_session, org)
    solution = _solution(db_session, org, actor)
    workspace = _workspace(db_session, org, actor, solution)
    kernel = WorkbenchKernel(user_id=actor.id)

    with tenant_ctx(org.id):
        for name in ("brief", "scope", "recommendation"):
            assert kernel.set_artifact_state(workspace.id, name, ArtifactState.DRAFT.value, {"name": name})
            assert kernel.set_artifact_state(workspace.id, name, ArtifactState.CONFIRMED.value)
            assert kernel.set_artifact_state(workspace.id, name, ArtifactState.PERSISTED.value)

        evidence_before = db_session.query(WorkbenchArtifactEvidence).filter_by(
            workspace_id=workspace.id
        ).all()
        assert {row.name for row in evidence_before} == {"brief", "scope", "recommendation"}

        blocked_result = ARBSubmissionResult(
            False,
            ["governance_gate_failed"],
            [{"code": "governance_gate_failed", "action": "Complete governance checks"}],
        )
        monkeypatch.setattr(
            "app.modules.transformation_room.arb_submission_adapter."
            "TypedARBSubmissionAdapter.submit_solution_for_actor",
            lambda **_kwargs: blocked_result,
        )
        blocked = kernel.submit_to_arb(workspace.id)
        assert blocked["success"] is False
        assert kernel.get_artifact_state(workspace.id, "arb_submission") is None

        successful_result = replace(
            blocked_result,
            success=True,
            reason_codes=[],
            missing_evidence=[],
            review_item_id=101,
            review_number="REV-2026-WORKBENCH",
            snapshot_id=202,
        )
        monkeypatch.setattr(
            "app.modules.transformation_room.arb_submission_adapter."
            "TypedARBSubmissionAdapter.submit_solution_for_actor",
            lambda **_kwargs: successful_result,
        )
        submitted = kernel.submit_to_arb(workspace.id)

    assert submitted["success"] is True
    assert submitted["review_item_id"] == 101
    assert submitted["snapshot_id"] == 202
    artifact = kernel.get_artifact_state(workspace.id, "arb_submission")
    assert artifact["state"] == "persisted"
    assert artifact["data"]["review_item_id"] == 101
    assert artifact["data"]["snapshot_id"] == 202


def test_workbench_does_not_report_canonical_success_as_submission_failure(
    db_session, make_org, tenant_ctx, monkeypatch
):
    org = make_org("ai-arb-truthful-success")
    actor = _user(db_session, org)
    solution = _solution(db_session, org, actor)
    workspace = _workspace(db_session, org, actor, solution)
    kernel = WorkbenchKernel(user_id=actor.id)
    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionAdapter.submit_solution_for_actor",
        lambda **_kwargs: ARBSubmissionResult(
            True, review_item_id=301, review_number="REV-2026-DURABLE", snapshot_id=302
        ),
    )
    monkeypatch.setattr(kernel, "set_artifact_state", lambda *args, **kwargs: False)

    with tenant_ctx(org.id):
        result = kernel.submit_to_arb(workspace.id)

    assert result["success"] is True
    assert result["review_item_id"] == 301
    assert result["artifact_recorded"] is False
    assert result["warnings"] == ["submission_artifact_persistence_failed"]
