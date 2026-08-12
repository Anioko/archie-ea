"""Dashboard two-mode regression tests (shell-overhaul Wave 1, Task 5).

A brand-new, sparse org used to render the same "Health Score 5 / six red 0%
bars / 8 all-zero Solution Pipeline rows" report card as an established one —
the product owner's screenshot evidence for a cluttered, broken-looking UI.
`/dashboard/overview` (app/modules/dashboard/v2/routes/dashboard_views.py)
now computes ``dashboard_mode`` server-side from counts it already fetches:
guided (a setup journey, no red, no fabricated zeros) for an org with fewer
than 5 applications AND zero capability mappings; data (health score +
visualizations) otherwise.

Login pattern follows tests/test_sidebar_render.py::_login (the proven
`client.session_transaction()` + Flask-Login g-cache-clear pattern for this
route). All fixture rows are seeded *before* `_login()` runs: the db_session
fixture keeps one app context open for the whole test (so `client.get(...)`
reuses it rather than pushing a fresh one — see test_ba_tenant_and_authz.py's
`_login` docstring), and creating ORM rows *after* login but before the first
real request left a stale anonymous user cached on that shared `g` in one
manual trial here — seeding first sidesteps it entirely and matches every
other adopter of this pattern in the suite.
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


def _make_user(db_session, make_org, label, enterprise_role="platform_admin"):
    from app.models.user import User

    org = make_org(f"dash-{label}")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"dash-{label}-{suffix}@example.com",
        first_name="Dash",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role=enterprise_role,
        is_org_admin=True,
    )
    db_session.add(user)
    db_session.flush()
    return user, org


def test_sparse_org_gets_guided_setup(app, db_session, make_org):
    """0 applications, 0 mappings -> guided mode: setup card, no health score,
    no red 0% score bars."""
    user, _org = _make_user(db_session, make_org, "sparse")

    client = app.test_client()
    _login(client, user.id)

    resp = client.get("/dashboard/overview")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert 'data-testid="guided-setup"' in html
    assert 'data-testid="health-score-value"' not in html
    # No red-styled 0% figure (the "six red 0% bars" defect).
    assert "text-destructive\">0%" not in html


def test_established_org_gets_data_mode(app, db_session, make_org):
    """>=5 applications and >=1 capability mapping -> data mode: health score
    leads, no guided setup card."""
    from sqlalchemy import insert

    from app.models.application_capability import ApplicationCapabilityMapping
    from app.models.application_portfolio import ApplicationComponent
    from app.models.archimate_core import ArchiMateElement
    from app.models.business_capabilities import BusinessCapability

    user, org = _make_user(db_session, make_org, "established")

    # Several before_insert listeners (e.g. archimate_relationship_sync's
    # auto-created "serving" relationship on an ApplicationCapabilityMapping)
    # pull organization_id from g.current_org_id rather than the triggering
    # row, same as the real per-request path -- set it here since this fixture
    # runs outside a request.
    from flask import g

    g.current_org_id = org.id

    apps = []
    for i in range(6):
        app_component = ApplicationComponent(
            name=f"Test App {i}-{uuid.uuid4().hex[:6]}",
            organization_id=org.id,
        )
        db_session.add(app_component)
        apps.append(app_component)
    db_session.flush()

    # BusinessCapability's before_insert listener auto-creates an
    # ArchiMateElement via a raw Core insert that never sets organization_id
    # (app/models/business_capabilities.py create_capability_archimate_element)
    # -- unrelated pre-existing schema-drift bug (archimate_elements.organization_id
    # is NOT NULL at the DB level but absent from the ORM model entirely). Pre-set
    # archimate_element_id here so that listener's no-op branch is taken instead.
    cap_name = f"Test Capability {uuid.uuid4().hex[:6]}"
    elem_id = db_session.execute(
        insert(ArchiMateElement.__table__).values(
            name=cap_name, type="Capability", layer="Strategy", organization_id=org.id
        )
    ).inserted_primary_key[0]
    db_session.flush()

    capability = BusinessCapability(
        name=cap_name,
        level=1,
        organization_id=org.id,
        archimate_element_id=elem_id,
    )
    db_session.add(capability)
    db_session.flush()

    mapping = ApplicationCapabilityMapping(
        application_component_id=apps[0].id,
        business_capability_id=capability.id,
        organization_id=org.id,
    )
    db_session.add(mapping)
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)

    resp = client.get("/dashboard/overview")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert 'data-testid="health-score-value"' in html
    assert 'data-testid="guided-setup"' not in html
