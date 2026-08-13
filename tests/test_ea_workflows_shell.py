"""EA Workflows dashboard on the screen system (shell-overhaul Wave 3, Task 4).

The P0 design review called the scenario-first framing on this dashboard --
"What integrations break when this platform is cut over?" and its four
siblings -- the best IA idea in the product. This task migrates the header
(page_header + a hand-rolled breadcrumb nav) onto page_shell and the stat
tiles onto stat_card, while KEEPING the scenario cards and ADM phase
coverage matrix verbatim in substance (restyled through the system, not
flattened).

/ea-workflows/journeys 500'd before the P0 wave on a None iteration_number
sort key (``sorted()`` cannot compare None with int). It is fixed via
``_sort_iteration_keys`` in app/main/routes_ea_workflows.py. This file pins
that fix with an HTTP-level regression guard.
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


def _make_user(db_session, make_org, label):
    from app.models.user import User

    org = make_org(f"ea-workflows-shell-{label}")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"ea-workflows-shell-{label}-{suffix}@example.com",
        first_name="EA",
        last_name="Workflows",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    user.password = "Sup3rSecret!23"
    db_session.add(user)
    db_session.flush()
    db_session.commit()
    return user.id, org


def test_dashboard_has_exactly_one_h1(app, db_session, make_org):
    user_id, _org = _make_user(db_session, make_org, "one-h1")

    client = app.test_client()
    _login(client, user_id)
    resp = client.get("/ea-workflows")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    html = resp.get_data(as_text=True)

    assert html.count("<h1") == 1


def test_dashboard_has_scenario_cards(app, db_session, make_org):
    """Scenario-first framing -- the P0 review's favourite IA idea -- must
    survive the page_shell migration verbatim, not get flattened into a
    generic list."""
    user_id, _org = _make_user(db_session, make_org, "scenario-cards")

    client = app.test_client()
    _login(client, user_id)
    html = client.get("/ea-workflows").get_data(as_text=True)

    assert 'data-scenario-card="PLATFORM_MIGRATION_SCOPING"' in html
    assert "What integrations break when this platform is cut over?" in html
    # Five scenario-first workflows in the coverage matrix, each its own card.
    assert html.count('data-scenario-card="') == 5


def test_dashboard_keeps_adm_phase_coverage_matrix(app, db_session, make_org):
    user_id, _org = _make_user(db_session, make_org, "adm-matrix")

    client = app.test_client()
    _login(client, user_id)
    html = client.get("/ea-workflows").get_data(as_text=True)

    assert "ADM Phase Coverage Matrix" in html
    assert 'data-workflow-row="ARB_PACK_GENERATION"' in html


def test_dashboard_actions_row_present(app, db_session, make_org):
    """page_shell's actions_caller slot carries the header actions -- pins
    the migration off page_header's separate actions block."""
    user_id, _org = _make_user(db_session, make_org, "page-actions")

    client = app.test_client()
    _login(client, user_id)
    html = client.get("/ea-workflows").get_data(as_text=True)

    assert 'data-testid="page-actions"' in html


def test_journeys_endpoint_returns_200(app, db_session, make_org):
    """Regression guard: /ea-workflows/journeys 500'd on a None
    iteration_number sort key before the P0 wave fixed it via
    _sort_iteration_keys. Must stay 200."""
    user_id, _org = _make_user(db_session, make_org, "journeys")

    client = app.test_client()
    _login(client, user_id)
    resp = client.get("/ea-workflows/journeys")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    data = resp.get_json()
    assert data["success"] is True
