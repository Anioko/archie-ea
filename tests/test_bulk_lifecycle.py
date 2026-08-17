"""Pins the 17 Aug 2026 QA finding: the Applications list's "Lifecycle" bulk
action was completely non-functional. Its menu sends this app's actual
lifecycle_status vocabulary (the TOGAF-decommission-phase scheme rendered by
list_simple.html's STATUS_MAP badge lookup — "2.1 strategic", "5.
decommissioned", etc.), but the route validated against
app.models.constants.LifecycleStatus, an unrelated generic vocabulary
("planning", "production", ...) the menu never sent. Every real click failed
validation.

Uses the shared fixtures in tests/conftest.py (db_session rolls back
automatically; make_org/tenant_ctx cover multi-tenant setup).
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

    org = make_org("bulklc")
    user = User(
        email=f"bulklc-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Bulk",
        last_name="Lc",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()
    client = app.test_client()
    _login(client, user.id)
    return org, client, user


def test_bulk_lifecycle_accepts_the_menus_own_values(admin_client, app, tenant_ctx, db_session):
    """The exact values app/templates/applications/list_simple.html's
    "Lifecycle" bulk menu sends must be accepted — this is the concrete
    regression: every one of these previously 400'd.
    """
    org, client, user = admin_client
    from app import db
    from app.models.application_portfolio import ApplicationComponent

    with tenant_ctx(org.id):
        appc = ApplicationComponent(name="Bulk LC Target")
        db.session.add(appc)
        db.session.commit()
        app_id = appc.id

    _login(client, user.id)

    for stage in ["2.1 strategic", "4.2 decom planned", "5. decommissioned"]:
        resp = client.post(
            "/applications/api/bulk-lifecycle",
            json={"ids": [app_id], "lifecycle_stage": stage},
        )
        assert resp.status_code == 200, (stage, resp.get_data(as_text=True))
        body = resp.get_json()
        assert body["success"] is True
        assert body["updated_count"] == 1

    with tenant_ctx(org.id):
        db.session.refresh(appc)
        assert appc.lifecycle_status == "5. decommissioned"


def test_bulk_lifecycle_rejects_unknown_stage(admin_client, app, tenant_ctx, db_session):
    org, client, user = admin_client
    from app import db
    from app.models.application_portfolio import ApplicationComponent

    with tenant_ctx(org.id):
        appc = ApplicationComponent(name="Bulk LC Reject Target")
        db.session.add(appc)
        db.session.commit()
        app_id = appc.id

    _login(client, user.id)

    resp = client.post(
        "/applications/api/bulk-lifecycle",
        json={"ids": [app_id], "lifecycle_stage": "not-a-real-stage"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
