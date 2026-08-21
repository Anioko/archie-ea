from __future__ import annotations

from dataclasses import replace
import uuid

from app.models.arb_submission_evidence import WorkbenchArtifactEvidence
from app.models.solution_architect_models import (
    SolutionAnalysisSession,
    SolutionSessionStatus,
)
from app.models.solution_models import Solution
from app.models.user import User
from app.modules.ai_chat.services.agent_runner import AgentRunner
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


def test_executor_requires_trusted_workspace_for_ai_submission(
    db_session, make_org, tenant_ctx
):
    org = make_org("ai-arb-tool-block")
    actor = _user(db_session, org)
    solution = _solution(db_session, org, actor)

    with tenant_ctx(org.id):
        executor = ToolExecutor(actor.id)
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

    def submit(solution_id, actor_id, workspace_id=None, assertions=None):
        calls.append((solution_id, actor_id, workspace_id, assertions))
        return ARBSubmissionResult(
            True, review_item_id=73, review_number="REV-2026-TEST", snapshot_id=91
        )

    monkeypatch.setattr(
        "app.modules.solutions_strategic.v2.services.arb_submission_service."
        "ARBSubmissionService.submit",
        submit,
    )
    with tenant_ctx(org.id):
        executor = ToolExecutor(actor.id)
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

    assert calls == [(solution.id, actor.id, workspace.id, {"human_reviewed": True})]
    assert result["success"] is True
    assert result["result"] == {
        "solution": solution.name,
        "review_item_id": 73,
        "review_number": "REV-2026-TEST",
        "snapshot_id": 91,
        "idempotent": False,
    }
    assert solution.governance_status == "draft"


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
            "app.modules.solutions_strategic.v2.services.arb_submission_service."
            "ARBSubmissionService.submit",
            lambda *args, **kwargs: blocked_result,
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
            "app.modules.solutions_strategic.v2.services.arb_submission_service."
            "ARBSubmissionService.submit",
            lambda *args, **kwargs: successful_result,
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
        "app.modules.solutions_strategic.v2.services.arb_submission_service."
        "ARBSubmissionService.submit",
        lambda *args, **kwargs: ARBSubmissionResult(
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
