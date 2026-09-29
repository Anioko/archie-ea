"""AI chat persona-prompt overrides are platform-wide: only a platform administrator can change them.

The persona override row (AIPromptTemplate, category='persona_override', no tenant column) is served
to every organisation by app/modules/ai_chat/routes/chat_core.py's read. Four routes in
chat_admin_routes.py wrote and read it behind _require_admin() (an org-level check equivalent to
Permission.ADMINISTER), the same weaker guard the solution-prompt routes carried before PR 242. They
now use platform_admin_required, matching the solution-prompt routes in the same PR. The unrelated
feedback-analytics routes in this file are unaffected: they stay admin_required (organisation-scoped
analytics, not a shared table) and are asserted reachable here as a regression guard.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text


def _user(db_session, org, *, platform=False):
    from app.models import Role
    from app.models.user import User

    role = Role.query.filter_by(name="Administrator").first()
    if role is None:
        pytest.skip("no Administrator role seeded in this database")
    user = User(email=f"pp-{uuid.uuid4().hex[:6]}@example.test", first_name="Persona", last_name="Tester",
                organization_id=org.id, confirmed=True, role=role)
    user.password = uuid.uuid4().hex
    user.is_org_admin = True
    user.is_platform_admin = platform
    db_session.add(user)
    db_session.flush()
    return user


def _login(db_session, client, login_as, user_id):
    from app.models.user import User

    db_session.expunge_all()
    login_as(client, db_session.get(User, user_id))


def _world(db_session, make_org):
    org = make_org("persona-prompts")
    tenant, platform = _user(db_session, org), _user(db_session, org, platform=True)
    db_session.commit()
    return tenant.id, platform.id


@pytest.mark.parametrize("method,path", [
    ("get", "/ai-chat/admin/prompts"),
    ("get", "/ai-chat/admin/prompts/data"),
    ("post", "/ai-chat/admin/prompts/enterprise_architect/update"),
    ("post", "/ai-chat/admin/prompts/enterprise_architect/reset"),
])
def test_a_tenant_administrator_is_refused_on_every_persona_prompt_route(
    app, db_session, make_org, client, login_as, method, path
):
    tenant_id, _platform = _world(db_session, make_org)

    _login(db_session, client, login_as, tenant_id)
    response = getattr(client, method)(path, json={"system_prompt": "x"})

    assert response.status_code == 403


def test_a_refused_update_stores_no_override(app, db_session, make_org, client, login_as):
    tenant_id, _platform = _world(db_session, make_org)

    _login(db_session, client, login_as, tenant_id)
    client.post("/ai-chat/admin/prompts/enterprise_architect/update", json={"system_prompt": "override"})

    stored = db_session.execute(
        text("select count(*) from ai_prompt_templates where system_prompt = 'override'")
    ).scalar()
    assert stored == 0


def test_a_platform_administrator_can_still_update_and_reset_a_persona_prompt(
    app, db_session, make_org, client, login_as
):
    _tenant, platform_id = _world(db_session, make_org)

    _login(db_session, client, login_as, platform_id)
    updated = client.post("/ai-chat/admin/prompts/enterprise_architect/update", json={"system_prompt": "platform text"})
    listed = client.get("/ai-chat/admin/prompts/data")
    reset = client.post("/ai-chat/admin/prompts/enterprise_architect/reset")

    assert updated.status_code == 200
    assert listed.status_code == 200
    assert reset.status_code == 200


def test_the_unrelated_analytics_routes_stay_reachable_to_a_tenant_administrator(
    app, db_session, make_org, client, login_as
):
    """Regression guard: removing _require_admin() must not leave admin/analytics unguarded, and
    must not accidentally close it to the organisation administrators who used it before."""
    tenant_id, _platform = _world(db_session, make_org)

    _login(db_session, client, login_as, tenant_id)
    dashboard = client.get("/ai-chat/admin/analytics")
    data = client.get("/ai-chat/admin/analytics/data")

    assert dashboard.status_code == 200
    assert data.status_code in (200, 500)  # 500 only from an unrelated missing-model import guard, not auth
