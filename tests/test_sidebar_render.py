"""Render regression tests for the persona sidebar (shell-overhaul Wave 1, Task 3).

`app/templates/components/admin_sidebar.html` used to render one identical,
~102-link navigation for every role (see `test_sidebar_role_filtering.py`'s
docstring for the parallel history of `admin_sidebar_northstar_phase2.html`,
which was fixed first). This file proves the rewritten template actually
renders `app.utils.role_access.get_sidebar_zones(current_user)` — not a
hand-maintained parallel list — by hitting the real, highest-traffic route
(`/dashboard/overview`, `layouts/admin_base.html`) as a logged-in user of each
flagship persona and counting `<a ` tags inside the `data-testid="sidebar"`
container.

Follows the `client.get(...)` + session-login pattern already proven in
`tests/test_remaining_500_routes.py::_login` / `_make_logged_in_client`.
"""

from __future__ import annotations

import re
import uuid

import pytest

from app.utils.role_access import SIDEBAR_LINK_BUDGET

pytestmark = pytest.mark.usefixtures("db_session")

SIDEBAR_BUDGET = SIDEBAR_LINK_BUDGET


def _login(client, user_id):
    """Standard Flask-Login test-client pattern (see test_remaining_500_routes.py)."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True

    from flask import g, has_app_context

    if not has_app_context():
        return
    for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
        if hasattr(g, cached):
            delattr(g, cached)


def _make_logged_in_client(app, db_session, make_org, role, label):
    from app.models.user import User

    org = make_org(f"sidebar-{label}")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"sidebar-{label}-{suffix}@example.com",
        first_name="Sidebar",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role=role,
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return client


_SIDEBAR_RE = re.compile(
    r'data-testid="sidebar".*?</aside>', re.DOTALL,
)


def _sidebar_html(app, db_session, make_org, role, label):
    client = _make_logged_in_client(app, db_session, make_org, role, label)
    resp = client.get("/dashboard/overview")
    assert resp.status_code == 200, (
        f"/dashboard/overview returned {resp.status_code} for role={role}: "
        f"{resp.get_data(as_text=True)[:2000]}"
    )
    html = resp.get_data(as_text=True)
    match = _SIDEBAR_RE.search(html)
    assert match, "sidebar container (data-testid=\"sidebar\") not found in response"
    return match.group(0)


@pytest.mark.parametrize(
    "role,label",
    [
        ("solution_architect", "sa"),
        ("enterprise_architect", "ea"),
        ("cto", "cto"),
    ],
)
def test_flagship_persona_sidebar_within_budget(app, db_session, make_org, role, label):
    sidebar_html = _sidebar_html(app, db_session, make_org, role, label)
    link_count = len(re.findall(r"<a ", sidebar_html))
    assert link_count <= SIDEBAR_BUDGET, (
        f"{role} sidebar renders {link_count} links, budget is {SIDEBAR_BUDGET}"
    )


def test_procurement_sidebar_excludes_arb_dashboard(app, db_session, make_org):
    sidebar_html = _sidebar_html(app, db_session, make_org, "procurement", "proc")
    assert "ARB Dashboard" not in sidebar_html, (
        "procurement is not a board role and must not see the ARB dashboard link"
    )


def test_enterprise_architect_sidebar_includes_arb_dashboard(app, db_session, make_org):
    sidebar_html = _sidebar_html(app, db_session, make_org, "enterprise_architect", "ea-arb")
    assert "ARB Dashboard" in sidebar_html, (
        "enterprise_architect is a board role and must see the ARB dashboard link"
    )


def test_platform_admin_hits_the_link_budget_exactly(app, db_session, make_org):
    """Task 3 fix round (coordinator review): platform_admin's two new
    admin-zone links (Salesforce Integration, Power Platform) plus the
    mandatory All-modules directory fallback (rendered in the sidebar footer
    for platform_admin — see admin_sidebar.html's `ns.has_all_modules` check)
    bring it to exactly SIDEBAR_LINK_BUDGET (26) real, visible links: header
    logo + 23 zone links + footer All-modules + footer logout. An equality
    assertion, not <=, so this — the role with zero headroom — pins the
    number precisely rather than letting future drift hide inside slack that
    does not exist.
    """
    sidebar_html = _sidebar_html(app, db_session, make_org, "platform_admin", "pa-budget")
    link_count = len(re.findall(r"<a ", sidebar_html))
    assert link_count == SIDEBAR_BUDGET, (
        f"platform_admin sidebar renders {link_count} links, expected exactly "
        f"{SIDEBAR_BUDGET} (0 headroom left — see role_access.py's "
        f"SIDEBAR_LINK_BUDGET comment)"
    )


@pytest.mark.parametrize(
    "role,label",
    [
        ("enterprise_architect", "ea-allmod"),
        ("procurement", "proc-allmod"),
    ],
)
def test_sidebar_includes_all_modules_link(app, db_session, make_org, role, label):
    """The design's stated long-tail fallback ('Ctrl-K search + one new
    "All modules" directory page') must actually exist and be reachable from
    every role's sidebar — this was the Critical finding in the Task 3
    review: surfaces reachable from no sidebar on any role, with no working
    fallback. EA gets it via the Library zone; procurement too (only
    platform_admin uses the footer fallback — see
    test_platform_admin_hits_the_link_budget_exactly)."""
    sidebar_html = _sidebar_html(app, db_session, make_org, role, label)
    assert "All modules" in sidebar_html, (
        f"{role} sidebar has no reachable link to the All-modules directory"
    )
