"""Pins the AI chat approval-execution path reported in the 17 Aug 2026 QA
sweep: the approve route previously called AIChatApprovalService's
approve_approval, a method that never existed (AttributeError -> 500), so
the queue could be polled but never actually executed. Fixed in
app/modules/ai_chat/routes/approval_routes.py to call approve_and_execute
instead — this test pins that the route (not just the service) actually
mutates the target record end-to-end.

Uses the shared fixtures in tests/conftest.py.
"""

import uuid

import pytest


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


@pytest.fixture
def admin_client(app, db_session, make_org):
    from app.models.user import User

    org = make_org("aiapprove")
    user = User(
        email=f"aiapprove-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Ai",
        last_name="Approve",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()
    client = app.test_client()
    _login(client, user.id)
    return org, client, user


def test_approve_route_actually_executes_the_operation(admin_client, app, tenant_ctx, db_session):
    org, client, user = admin_client
    from app import db
    from app.models.application_portfolio import ApplicationComponent
    from app.modules.ai_chat.services.ai_chat_approval_service import AIChatApprovalService

    with tenant_ctx(org.id):
        appc = ApplicationComponent(name="Pre-approval name")
        db.session.add(appc)
        db.session.commit()
        app_id = appc.id

        service = AIChatApprovalService(user.id)
        created = service.create_pending_approval(
            operation_type="update",
            entity_type="application",
            original_command="rename this application",
            operation_payload={"name": "Post-approval name"},
            summary="Rename Pre-approval name to Post-approval name",
            entity_id=app_id,
        )
        assert created.get("success") is True, created
        approval_id = created["approval_id"]

    _login(client, user.id)

    resp = client.post(f"/ai-chat/approvals/{approval_id}/approve")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["success"] is True, body

    with tenant_ctx(org.id):
        db.session.refresh(appc)
        assert appc.name == "Post-approval name"
