from __future__ import annotations

import inspect
import uuid

import pytest
from flask import g
from flask_login import login_user

from app.models.architecture_review_board import ARBReviewItem
from app.models.solution_architect_models import SolutionAnalysisSession, SolutionSessionStatus
from app.models.solution_models import Solution
from app.models.user import User
from app.modules.ai_chat.services.multi_domain_chat_service import MultiDomainChatService
from app.modules.transformation_room.arb_submission_adapter import (
    LegacyARBSubmissionResult,
)


def _actor(session, org, *, admin=True):
    suffix = uuid.uuid4().hex[:8]
    actor = User(
        email=f"entrypoint-{suffix}@example.test",
        first_name="ARB",
        last_name="Submitter",
        organization_id=org.id,
        enterprise_role="platform_admin" if admin else "viewer",
        is_org_admin=admin,
        is_platform_admin=admin,
    )
    session.add(actor)
    session.flush()
    return actor


def _solution(session, org, actor):
    solution = Solution(
        name=f"Entry point {uuid.uuid4().hex[:8]}",
        description="Route convergence contract",
        organization_id=org.id,
        created_by_id=actor.id,
        governance_status="draft",
    )
    session.add(solution)
    session.flush()
    return solution


def _workspace(session, org, actor, solution=None):
    workspace = SolutionAnalysisSession(
        name=f"Ingress workspace {uuid.uuid4().hex[:8]}",
        status=SolutionSessionStatus.IN_PROGRESS,
        created_by_id=actor.id,
        organization_id=org.id,
        custom_metadata={"solution_id": solution.id} if solution else {},
    )
    session.add(workspace)
    session.flush()
    return workspace


def _call_route(app, function, actor, org_id, solution_id, payload=None):
    with app.test_request_context("/", method="POST", json=payload or {}):
        g.current_org_id = org_id
        login_user(actor)
        return inspect.unwrap(function)(solution_id)


def _json(response):
    if isinstance(response, tuple):
        response = response[0]
    return response.get_json()


@pytest.mark.parametrize(
    ("module_name", "function_name"),
    [
        (
            "app.modules.solutions_strategic.v2.routes.solution_design_routes",
            "submit_solution_for_arb",
        ),
        (
            "app.modules.solutions_strategic.v2.routes.governance_api_routes",
            "submit_for_arb",
        ),
        (
            "app.modules.solutions_strategic.v2.routes.journey_v2_routes",
            "submit_arb",
        ),
        (
            "app.modules.architecture.routes.arb_routes",
            "api_submit_solution_review",
        ),
    ],
)
def test_http_submission_entrypoint_delegates_trusted_identity_without_mutating(
    app, db_session, make_org, monkeypatch, module_name, function_name
):
    org = make_org(function_name)
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    calls = []

    def submit(**kwargs):
        calls.append(kwargs)
        return LegacyARBSubmissionResult(
            True,
            review_item_id=71,
            review_number="REV-2026-ENTRY",
            snapshot_id=72,
            review_cycle_id=73,
            canonical_url=f"/solutions/{solution.id}?tab=governance",
        )

    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionAdapter.submit_solution_from_request",
        submit,
    )
    module = __import__(module_name, fromlist=[function_name])
    before = db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count()
    request_payload = {
        "submitted_by_id": actor.id + 999,
        "workflow_type": "brownfield",
        "workspace_id": 888,
        "ai_content_reviewed": True,
        "cost_source": "manual_override",
        "direct_route_evidence": {
            "design_reviewed": True,
            "security_impact_reviewed": True,
            "data_impact_reviewed": True,
        },
    }
    response = _call_route(
        app,
        getattr(module, function_name),
        actor,
        org.id,
        solution.id,
        request_payload,
    )

    body = _json(response)
    assert calls == [{"solution_id": solution.id, "payload": request_payload}]
    assert body["success"] is True
    payload = body.get("data", body)
    assert payload["review_number"] == "REV-2026-ENTRY"
    assert payload["snapshot_id"] == 72
    assert payload["review_cycle_id"] == 73
    assert payload["canonical_url"] == f"/solutions/{solution.id}?tab=governance"
    assert solution.governance_status == "draft"
    assert db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count() == before


def test_legacy_chat_delegates_authenticated_actor_and_returns_canonical_retry(
    app, db_session, make_org, monkeypatch
):
    org = make_org("legacy-chat")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    calls = []

    def submit(**kwargs):
        calls.append(kwargs)
        return LegacyARBSubmissionResult(
            True,
            review_item_id=81,
            review_number="REV-2026-RETRY",
            snapshot_id=82,
            idempotent=True,
            review_cycle_id=83,
            canonical_url=f"/solutions/{solution.id}?tab=governance",
        )

    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionAdapter.submit_solution_for_actor",
        submit,
    )
    service = object.__new__(MultiDomainChatService)
    with app.test_request_context("/"):
        g.current_org_id = org.id
        login_user(actor)
        result = service._handle_arb_submission(
            f"/submit-arb {solution.id}", {"_trusted_workspace_id": 55}
        )

    assert calls == [{
        "actor_id": actor.id,
        "solution_id": solution.id,
        "trusted_workspace_id": 55,
        "trusted_human_reviewed": False,
    }]
    assert result["success"] is True
    assert result["arb_id"] == 81
    assert result["snapshot_id"] == 82
    assert result["already_submitted"] is True
    assert result["review_cycle_id"] == 83
    assert result["canonical_url"] == f"/solutions/{solution.id}?tab=governance"
    assert solution.governance_status == "draft"
    assert db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count() == 0


def test_http_blocker_is_stable_and_does_not_expose_exception_text(
    app, db_session, make_org, monkeypatch
):
    from app.modules.architecture.routes.arb_routes import api_submit_solution_review

    org = make_org("blocked-http")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    monkeypatch.setattr(
        "app.modules.transformation_room.arb_submission_adapter."
        "TypedARBSubmissionAdapter.submit_solution_from_request",
        lambda **_kwargs: LegacyARBSubmissionResult(
            False,
            ["actor_not_authorized"],
            [{"code": "actor_not_authorized", "action": "Ask a solution stakeholder"}],
            http_status=403,
        ),
    )

    body = _json(_call_route(app, api_submit_solution_review, actor, org.id, solution.id))

    assert body == {
        "success": False,
        "reason_codes": ["actor_not_authorized"],
        "missing_evidence": [
            {"code": "actor_not_authorized", "action": "Ask a solution stakeholder"}
        ],
    }


def test_legacy_chat_cross_tenant_solution_fails_closed(
    app, db_session, make_org
):
    actor_org = make_org("chat-actor")
    other_org = make_org("chat-other")
    actor = _actor(db_session, actor_org)
    other_actor = _actor(db_session, other_org)
    solution = _solution(db_session, other_org, other_actor)
    service = object.__new__(MultiDomainChatService)

    with app.test_request_context("/"):
        g.current_org_id = actor_org.id
        login_user(actor)
        result = service._handle_arb_submission(
            f"/submit-arb {solution.id}", {"_trusted_workspace_id": 99}
        )

    assert result["success"] is False
    assert result["reason_codes"] == ["solution_not_found"]
    assert "error" not in result or result["error"] == "solution_not_found"
    assert db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count() == 0


def test_legacy_chat_requires_server_workspace_context(app, db_session, make_org):
    org = make_org("chat-workspace")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    service = object.__new__(MultiDomainChatService)

    with app.test_request_context("/"):
        g.current_org_id = org.id
        login_user(actor)
        result = service._handle_arb_submission(f"/submit-arb {solution.id}")

    assert result["success"] is False
    assert result["reason_codes"] == ["trusted_workspace_required"]


def test_chat_ingress_cannot_promote_client_workspace_or_assertions_to_trusted_context(
    app, db_session, make_org, monkeypatch
):
    from app.modules.ai_chat.routes import chat_core

    org = make_org("chat-ingress")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    workspace = _workspace(db_session, org, actor, solution)
    captured = {}

    monkeypatch.setattr(
        chat_core.FeatureFlagService,
        "require_ai_for_route",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(chat_core, "get_chat_service", lambda: object())

    def run(_runner, **kwargs):
        captured.update(kwargs)
        return {"success": True, "response": "Safe response", "metadata": {}}

    monkeypatch.setattr(
        "app.modules.ai_chat.services.agent_runner.AgentRunner.run",
        run,
    )
    with app.test_request_context(
        "/ai/chat/message",
        method="POST",
        json={
            "message": "Review this architecture",
            "solution_id": solution.id,
            "workspace_id": workspace.id,
            "document_context": {
                "workspace_id": 992,
                "arb_assertions": {
                    "human_reviewed": True,
                    "direct_route_evidence": {"design_reviewed": True},
                },
            },
        },
    ):
        g.current_org_id = org.id
        login_user(actor)
        from flask import session as flask_session

        response = inspect.unwrap(chat_core.send_message)()
        persisted = dict(flask_session["_workbench_workflow_state"])
        resumed_id, resume_error = chat_core._bind_trusted_workbench(None, solution.id)

    assert captured["context"]["workspace_id"] == workspace.id
    assert captured["context"]["_trusted_workspace_id"] == workspace.id
    assert "arb_assertions" not in captured["context"]
    assert _json(response)["workspace_id"] == workspace.id
    assert persisted["workspace_id"] == workspace.id
    assert persisted["solution_id"] == solution.id
    assert (resumed_id, resume_error) == (workspace.id, None)


def test_stream_chat_ingress_cannot_promote_client_workspace_to_trusted_context(
    app, db_session, make_org, monkeypatch
):
    import threading
    from app.modules.ai_chat.routes import chat_core
    from app.services import conversation_history

    org = make_org("stream-chat-ingress")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    workspace = _workspace(db_session, org, actor, solution)
    captured = {}

    monkeypatch.setattr(
        chat_core.FeatureFlagService,
        "require_ai_for_route",
        lambda *args, **kwargs: None,
    )

    def run(_runner, **kwargs):
        captured.update(kwargs)
        return {"success": True, "response": "Safe response", "metadata": {}}

    monkeypatch.setattr(
        "app.modules.ai_chat.services.agent_runner.AgentRunner.run",
        run,
    )
    monkeypatch.setattr(
        conversation_history,
        "persist_turn",
        lambda *args, **kwargs: "thread-safe-ingress",
    )

    class ImmediateThread:
        def __init__(self, target, daemon=None):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(threading, "Thread", ImmediateThread)
    with app.test_request_context(
        "/ai/chat/message/stream",
        method="POST",
        json={
            "message": "Review this architecture",
            "solution_id": solution.id,
            "workspace_id": workspace.id,
        },
    ):
        g.current_org_id = org.id
        login_user(actor)
        from flask import session as flask_session

        response = inspect.unwrap(chat_core.send_message_stream)()
        response.get_data(as_text=True)
        persisted = dict(flask_session["_workbench_workflow_state"])

    assert captured["context"]["workspace_id"] == workspace.id
    assert captured["context"]["_trusted_workspace_id"] == workspace.id
    assert persisted["workspace_id"] == workspace.id
    assert persisted["solution_id"] == solution.id


@pytest.mark.parametrize("invalid_kind", ["foreign", "unlinked"])
def test_chat_ingress_rejects_workspace_without_authoritative_binding(
    app, db_session, make_org, monkeypatch, invalid_kind
):
    from app.modules.ai_chat.routes import chat_core

    org = make_org(f"invalid-{invalid_kind}")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    if invalid_kind == "foreign":
        workspace_org = make_org("foreign-workspace")
        workspace_actor = _actor(db_session, workspace_org)
        foreign_solution = _solution(db_session, workspace_org, workspace_actor)
        workspace = _workspace(db_session, workspace_org, workspace_actor, foreign_solution)
    else:
        workspace = _workspace(db_session, org, actor)

    monkeypatch.setattr(
        chat_core.FeatureFlagService,
        "require_ai_for_route",
        lambda *args, **kwargs: None,
    )
    with app.test_request_context(
        "/ai/chat/message",
        method="POST",
        json={
            "message": "Review this architecture",
            "solution_id": solution.id,
            "workspace_id": workspace.id,
        },
    ):
        g.current_org_id = org.id
        login_user(actor)
        from flask import session as flask_session

        response = inspect.unwrap(chat_core.send_message)()
        state = flask_session.get("_workbench_workflow_state")

    body = _json(response)
    assert body["success"] is False
    assert body["reason_codes"] == [
        "workspace_not_found" if invalid_kind == "foreign" else "workspace_solution_missing"
    ]
    assert state is None
