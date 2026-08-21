from __future__ import annotations

import inspect
import uuid

import pytest
from flask import g
from flask_login import login_user

from app.models.architecture_review_board import ARBReviewItem
from app.models.solution_models import Solution
from app.models.user import User
from app.modules.ai_chat.services.multi_domain_chat_service import MultiDomainChatService
from app.modules.solutions_strategic.v2.services.arb_submission_service import (
    ARBSubmissionResult,
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

    def submit(solution_id, actor_id, workspace_id=None, assertions=None):
        calls.append((solution_id, actor_id, workspace_id, assertions))
        return ARBSubmissionResult(
            True,
            review_item_id=71,
            review_number="REV-2026-ENTRY",
            snapshot_id=72,
        )

    monkeypatch.setattr(
        "app.modules.solutions_strategic.v2.services.arb_submission_service."
        "ARBSubmissionService.submit",
        submit,
    )
    module = __import__(module_name, fromlist=[function_name])
    before = db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count()
    response = _call_route(
        app,
        getattr(module, function_name),
        actor,
        org.id,
        solution.id,
        {
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
        },
    )

    body = _json(response)
    assert calls == [
        (
            solution.id,
            actor.id,
            None,
            {
                "human_reviewed": True,
                "cost_source": "manual_override",
                "direct_route_evidence": {
                    "design_reviewed": True,
                    "security_impact_reviewed": True,
                    "data_impact_reviewed": True,
                },
                "resubmission_notes": None,
            },
        )
    ]
    assert body["success"] is True
    payload = body.get("data", body)
    assert payload["review_number"] == "REV-2026-ENTRY"
    assert payload["snapshot_id"] == 72
    assert solution.governance_status == "draft"
    assert db_session.query(ARBReviewItem).filter_by(solution_id=solution.id).count() == before


def test_legacy_chat_delegates_authenticated_actor_and_returns_canonical_retry(
    app, db_session, make_org, monkeypatch
):
    org = make_org("legacy-chat")
    actor = _actor(db_session, org)
    solution = _solution(db_session, org, actor)
    calls = []

    def submit(solution_id, actor_id, workspace_id=None, assertions=None):
        calls.append((solution_id, actor_id, workspace_id, assertions))
        return ARBSubmissionResult(
            True,
            review_item_id=81,
            review_number="REV-2026-RETRY",
            snapshot_id=82,
            idempotent=True,
        )

    monkeypatch.setattr(
        "app.modules.solutions_strategic.v2.services.arb_submission_service."
        "ARBSubmissionService.submit",
        submit,
    )
    service = object.__new__(MultiDomainChatService)
    with app.test_request_context("/"):
        g.current_org_id = org.id
        login_user(actor)
        result = service._handle_arb_submission(
            f"/submit-arb {solution.id}", {"workspace_id": 55}
        )

    assert calls == [(solution.id, actor.id, 55, {})]
    assert result["success"] is True
    assert result["arb_id"] == 81
    assert result["snapshot_id"] == 82
    assert result["already_submitted"] is True
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
        "app.modules.solutions_strategic.v2.services.arb_submission_service."
        "ARBSubmissionService.submit",
        lambda *args, **kwargs: ARBSubmissionResult(
            False,
            ["actor_not_authorized"],
            [{"code": "actor_not_authorized", "action": "Ask a solution stakeholder"}],
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
            f"/submit-arb {solution.id}", {"workspace_id": 99}
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
