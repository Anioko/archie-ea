"""The All-modules directory page (shell-overhaul Wave 1, Task 3 fix round).

The persona sidebar diet moved dozens of real, working routes out of the DOM
for most roles. The design's stated long-tail fallback ("Ctrl-K search + one
new 'All modules' directory page") didn't actually exist before this round —
this file proves it now does: GET /modules 200s for an authenticated user and
surfaces both a zone-sourced link (Stakeholder Map, unioned from every role's
SIDEBAR_ZONES) and a curated "More tools" link (Batch Import, never in any
zone).

Follows the db_session + make_org + session-login pattern proven in
tests/test_remaining_500_routes.py and used by tests/test_sidebar_render.py
in this same wave.
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


def _make_logged_in_client(app, db_session, make_org, role="enterprise_architect"):
    from app.models.user import User

    org = make_org("modules-directory")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"modules-directory-{suffix}@example.com",
        first_name="Directory",
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


def test_modules_directory_returns_200(app, db_session, make_org):
    client = _make_logged_in_client(app, db_session, make_org)
    resp = client.get("/modules")
    assert resp.status_code == 200, (
        f"/modules returned {resp.status_code}: {resp.get_data(as_text=True)[:2000]}"
    )


def test_modules_directory_includes_zone_sourced_link(app, db_session, make_org):
    """Stakeholder Map now lives in the curated More-tools section (it isn't
    in any role's SIDEBAR_ZONES), but the directory must also surface real
    zone-sourced links — assert one that is unambiguously zone-only and
    common to most roles: ArchiMate Elements (library zone, every role)."""
    client = _make_logged_in_client(app, db_session, make_org)
    html = client.get("/modules").get_data(as_text=True)
    assert "ArchiMate Elements" in html


def test_modules_directory_includes_curated_more_tools(app, db_session, make_org):
    client = _make_logged_in_client(app, db_session, make_org)
    html = client.get("/modules").get_data(as_text=True)
    assert "Stakeholder Map" in html
    assert "Batch Import" in html


def test_modules_directory_requires_login(app, db_session, make_org):
    client = app.test_client()
    resp = client.get("/modules")
    assert resp.status_code in (302, 401, 403), (
        f"/modules must not be reachable anonymously, got {resp.status_code}"
    )
