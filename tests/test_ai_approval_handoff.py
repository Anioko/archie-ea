"""Two-person, tenant-scoped approval handoff for AI-originated writes."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest


pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org_id, label, *, can_approve=True):
    """Create a user with either GENERAL permission or an explicit Viewer role."""
    from app.models.user import Permission, Role, User

    suffix = uuid.uuid4().hex[:8]
    role_name = "AI Approval Reviewer" if can_approve else "AI Approval Viewer"
    role = Role.query.filter_by(name=role_name).first()
    if role is None:
        role = Role(
            name=role_name,
            permissions=Permission.GENERAL if can_approve else 0,
            index="main",
            default=False,
        )
        db_session.add(role)
        db_session.flush()
    user = User(
        email=f"ai-handoff-{label}-{suffix}@example.com",
        first_name=label,
        last_name="Reviewer",
        organization_id=org_id,
        confirmed=True,
        enterprise_role="solution_architect",
    )
    user.role = role
    db_session.add(user)
    db_session.flush()
    return user


def _queue(service):
    result = service.create_pending_approval(
        operation_type="create",
        entity_type="capability",
        original_command="create capability Handoff",
        operation_payload={"name": "Handoff"},
        summary="Create capability Handoff",
        chat_session_id="handoff-test",
    )
    assert result["success"], result
    return result["approval_id"]


def _fake_execution(monkeypatch):
    import app.modules.ai_chat.services.ai_chat_approval_service as svc_mod

    calls = []

    class _FakeDataService:
        def __init__(self, user_id):
            self.user_id = user_id

        def create_capability(self, payload):
            calls.append((self.user_id, payload))
            return {"success": True, "id": 9001}

    monkeypatch.setattr(svc_mod, "AIDataInteractionService", _FakeDataService)
    return calls


def test_same_org_reviewer_executes_once_and_receives_allowlisted_queue(
    db_session, make_org, tenant_ctx, monkeypatch
):
    """A different authorized user reviews exactly one same-org queued write."""
    from app.modules.ai_chat.services.ai_chat_approval_service import AIChatApprovalService
    from app.models.ai_chat_crud_approval import AIChatApprovalAuditLog, AIChatCRUDApproval

    org = make_org("approval-handoff")
    requester = _make_user(db_session, org.id, "Requester")
    reviewer = _make_user(db_session, org.id, "Reviewer")

    with tenant_ctx(org.id):
        approval_id = _queue(AIChatApprovalService(requester.id))
        approval = db_session.get(AIChatCRUDApproval, approval_id)
        assert approval.organization_id == org.id

        queue = AIChatApprovalService(reviewer.id).get_approver_queue()
        assert queue["success"] is True
        assert queue["approvals"] == [
            {
                "id": approval_id,
                "operation_type": "create",
                "entity_type": "capability",
                "summary": "Create capability Handoff",
                "created_at": approval.created_at.isoformat(),
                "expires_at": approval.expires_at.isoformat(),
                "requester": {"id": requester.id, "display_name": "Requester Reviewer"},
            }
        ]

        calls = _fake_execution(monkeypatch)
        mismatch = AIChatApprovalService(reviewer.id).approve_and_execute(approval_id, requester.id)
        assert mismatch["code"] == "FORBIDDEN"
        assert calls == []

        result = AIChatApprovalService(reviewer.id).approve_and_execute(approval_id, reviewer.id)
        assert result["success"] is True
        assert calls == [(reviewer.id, {"name": "Handoff"})]

        replay = AIChatApprovalService(reviewer.id).approve_and_execute(approval_id, reviewer.id)
        assert replay == {"success": False, "code": "CONFLICT", "error": "Approval is already approved"}
        assert len(calls) == 1

        events = AIChatApprovalAuditLog.query.filter_by(approval_id=approval_id).all()
        assert {event.event for event in events} >= {"created", "approved", "executed"}


def test_foreign_org_cannot_see_or_decide_known_approval_id(
    db_session, make_org, tenant_ctx, monkeypatch
):
    """Known numeric IDs never reveal or execute another organization's request."""
    from app.modules.ai_chat.services.ai_chat_approval_service import AIChatApprovalService

    org_a = make_org("approval-a")
    org_b = make_org("approval-b")
    requester = _make_user(db_session, org_a.id, "RequesterA")
    foreign_reviewer = _make_user(db_session, org_b.id, "ReviewerB")

    with tenant_ctx(org_a.id):
        approval_id = _queue(AIChatApprovalService(requester.id))

    calls = _fake_execution(monkeypatch)
    with tenant_ctx(org_b.id):
        service = AIChatApprovalService(foreign_reviewer.id)
        assert service.get_approver_queue() == {"success": True, "approvals": []}
        assert service.approve_and_execute(approval_id, foreign_reviewer.id)["code"] == "NOT_FOUND"
        assert service.reject_approval(approval_id)["code"] == "NOT_FOUND"
    assert calls == []


def test_requester_can_cancel_and_same_org_reviewer_can_reject(db_session, make_org, tenant_ctx):
    """Cancellation is requester-owned; review rejection is a same-org write permission."""
    from app.modules.ai_chat.services.ai_chat_approval_service import AIChatApprovalService
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval, ApprovalStatus

    org = make_org("approval-reject")
    requester = _make_user(db_session, org.id, "Requester")
    reviewer = _make_user(db_session, org.id, "Reviewer")

    with tenant_ctx(org.id):
        requester_service = AIChatApprovalService(requester.id)
        cancelled_id = _queue(requester_service)
        assert requester_service.reject_approval(cancelled_id, "cancelled")["success"] is True
        assert db_session.get(AIChatCRUDApproval, cancelled_id).status == ApprovalStatus.REJECTED

        reviewer_id = _queue(requester_service)
        rejected = AIChatApprovalService(reviewer.id).reject_approval(reviewer_id, "needs evidence")
        assert rejected["success"] is True
        assert db_session.get(AIChatCRUDApproval, reviewer_id).status == ApprovalStatus.REJECTED


def test_viewer_is_denied_reviewer_queue_and_rejection(db_session, make_org, tenant_ctx):
    from app.modules.ai_chat.services.ai_chat_approval_service import AIChatApprovalService

    org = make_org("approval-viewer")
    requester = _make_user(db_session, org.id, "Requester")
    viewer = _make_user(db_session, org.id, "Viewer", can_approve=False)

    with tenant_ctx(org.id):
        approval_id = _queue(AIChatApprovalService(requester.id))
        service = AIChatApprovalService(viewer.id)
        assert service.get_approver_queue()["code"] == "FORBIDDEN"
        assert service.reject_approval(approval_id)["code"] == "FORBIDDEN"


def test_approval_routes_hide_foreign_rows_and_forbid_viewer_queue(
    app, db_session, make_org, tenant_ctx, login_as
):
    """HTTP contracts preserve 404 for foreign IDs and 403 for capability denial."""
    from app.modules.ai_chat.services.ai_chat_approval_service import AIChatApprovalService

    org_a = make_org("approval-route-a")
    org_b = make_org("approval-route-b")
    requester = _make_user(db_session, org_a.id, "RequesterA")
    foreign_reviewer = _make_user(db_session, org_b.id, "ReviewerB")
    viewer = _make_user(db_session, org_b.id, "ViewerB", can_approve=False)

    with tenant_ctx(org_a.id):
        approval_id = _queue(AIChatApprovalService(requester.id))

    client = app.test_client()
    login_as(client, foreign_reviewer)
    assert client.get("/ai-chat/approvals/queue").get_json() == {"success": True, "approvals": []}
    assert client.post(f"/ai-chat/approvals/{approval_id}/approve").status_code == 404
    assert client.post(f"/ai-chat/approvals/{approval_id}/reject").status_code == 404

    login_as(client, viewer)
    assert client.get("/ai-chat/approvals/queue").status_code == 403


def test_backfill_is_idempotent_and_reports_no_remaining_nulls(db_session, make_org):
    """Legacy NULL rows derive their owner exactly from their requester."""
    from app.commands.backfill_ai_chat_approval_org import run_backfill
    from app.models.ai_chat_crud_approval import AIChatCRUDApproval, ApprovalStatus

    org = make_org("approval-backfill")
    requester = _make_user(db_session, org.id, "Requester")
    approval = AIChatCRUDApproval(
        user_id=requester.id,
        organization_id=None,
        operation_type="create",
        entity_type="capability",
        original_command="legacy approval",
        operation_payload='{"name": "Legacy"}',
        summary="Legacy approval",
        status=ApprovalStatus.PENDING,
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db_session.add(approval)
    db_session.flush()

    first = run_backfill()
    second = run_backfill()
    db_session.refresh(approval)
    assert approval.organization_id == org.id
    assert first["backfilled"] >= 1
    assert first["remaining_nulls"] == 0
    assert second == {"backfilled": 0, "remaining_nulls": 0}


def test_approval_modal_is_a_reviewer_queue_with_requester_attribution():
    """The shared modal cannot present a requester's own approval as actionable."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/js/ai_chat/approval_modal.js").read_text(encoding="utf-8")
    template = (root / "app/templates/ai_chat/index.html").read_text(encoding="utf-8")

    assert 'fetch("/ai-chat/approvals/queue"' in js
    assert "Approvals for review" in template
    assert "Requested by" in template
    assert "queued for another authorized user" in (
        root / "app/modules/ai_chat/services/ai_chat_approval_service.py"
    ).read_text(encoding="utf-8")
