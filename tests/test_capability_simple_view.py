"""/capability-map/simple must render real BusinessCapability data.

Pins the fix for the previous ``simple_view()`` route, which rendered a
612-line static template with no context at all — every tenant saw the same
invented "38 capabilities / 124 functions / 11 domains" and a fictional
"Digital Application Platform" taxonomy. The route now queries real
``BusinessCapability`` rows for the tenant, so this seeds two capabilities
in an isolated org and asserts they (not the old mock copy) appear.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


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


def _make_user(db_session, make_org):
    from app.models.user import User

    org = make_org("capsimple")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"capsimple-{suffix}@example.com",
        first_name="Cap",
        last_name="Simple",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    user.password = "Sup3rSecret!23"
    db_session.add(user)
    db_session.flush()
    db_session.commit()
    return user.id, org


def _seed_capabilities(db_session, org, tenant_ctx):
    """One level-1 root plus one level-2 child under it.

    Runs inside ``tenant_ctx(org.id)`` with ``g.current_org_id`` set: the
    BusinessCapability insert's ``before_insert`` listener also raw-inserts a
    matching ``ArchiMateElement`` row (see
    ``create_capability_archimate_element`` in
    ``app/models/business_capabilities.py``), which bypasses the ORM
    ``before_flush`` auto-set and relies on the column default
    (``_default_org_id``) reading ``g.current_org_id`` instead — set only
    inside a request context. See ``tests/test_capability_map_shell.py`` for
    the same pattern.
    """
    from app.models.business_capabilities import BusinessCapability

    with tenant_ctx(org.id):
        parent = BusinessCapability(
            name="Customer Engagement Test Capability",
            description="Top-level test capability for the simple view.",
            level=1,
            business_domain="Experience",
            organization_id=org.id,
        )
        db_session.add(parent)
        db_session.flush()

        child = BusinessCapability(
            name="Omni-Channel Support Test Capability",
            description="Sub-capability of the top-level test capability.",
            level=2,
            business_domain="Experience",
            parent_capability_id=parent.id,
            organization_id=org.id,
        )
        db_session.add(child)
        db_session.commit()

    return parent, child


@pytest.fixture
def capability_setup(app, db_session, make_org, tenant_ctx):
    user_id, org = _make_user(db_session, make_org)
    parent, child = _seed_capabilities(db_session, org, tenant_ctx)

    client = app.test_client()
    _login(client, user_id)
    return client, parent, child


def test_simple_view_renders_real_capabilities(capability_setup):
    client, parent, child = capability_setup
    resp = client.get("/capability-map/simple")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    body = resp.get_data(as_text=True)
    assert parent.name in body
    assert child.name in body


def test_simple_view_has_no_mock_content(capability_setup):
    client, _parent, _child = capability_setup
    resp = client.get("/capability-map/simple")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Digital Application Platform" not in body
