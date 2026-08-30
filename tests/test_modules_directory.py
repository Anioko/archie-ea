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


# ---------------------------------------------------------------------------
# 30 Aug 2026 — "only advertise doors that open".
#
# The tests above prove the page renders and lists things. Nothing asserted a
# listed row leads anywhere. Requesting all 101 advertised destinations with a
# logged-in client found:
#
#   * 1 hard 500 (capability_maturity/heatmap.html called `empty_state` with
#     `cta_label=`, a kwarg only the *other* macro of that name accepts, so the
#     page died on exactly the empty database a new tenant has);
#   * 1 permanently-404 row (a deprecated, feature-flagged-off module);
#   * 4 rows that 302 onto a page this same list already offered by its own name;
#   * 19 rows shown to an enterprise_architect that return a hard 403, because
#     the page unions every role's SIDEBAR_ZONES with no per-user filter.
#
# Each is re-measured below.
# ---------------------------------------------------------------------------


def _make_user(db_session, org, *, enterprise_role, platform_admin=False):
    from app.models.user import User

    user = User(email=f"{enterprise_role}-{org.id}@modules.test")
    user.organization_id = org.id
    user.enterprise_role = enterprise_role
    user.confirmed = True
    user.is_platform_admin = platform_admin
    user.password = "Directory!12345"
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def org(make_org):
    return make_org("modules-directory")


# --------------------------------------------------------------------------
# The page renders, and renders the search control its own subtitle promises.
# --------------------------------------------------------------------------


def test_directory_renders_and_is_searchable(app, db_session, org, client, login_as):
    """The subtitle has always said "grouped and searchable" — assert the
    control exists and carries an accessible name (a placeholder is not one)."""
    user = _make_user(db_session, org, enterprise_role="enterprise_architect")
    login_as(client, user)

    response = client.get("/modules/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert 'data-testid="modules-directory-search"' in html
    assert 'for="modules-directory-search"' in html, "search input has no <label>"
    assert "Search modules by name" in html
    assert "modulesDirectory()" in html, "Alpine component not wired to the page"


def test_every_rendered_row_has_a_real_href(app, db_session, org, client, login_as):
    """No row may ship `href="#"`, an empty href, or an unresolved URL: the
    route resolves each endpoint itself and drops the ones it cannot build."""
    import re

    user = _make_user(db_session, org, enterprise_role="enterprise_architect")
    login_as(client, user)
    html = client.get("/modules/").get_data(as_text=True)

    body = html.split('data-testid="modules-directory"', 1)[1]
    hrefs = re.findall(r'<li x-show="matches\([^)]*\)">\s*<a href="([^"]*)"', body)
    assert hrefs, "directory rendered no rows at all"
    assert all(h.startswith("/") for h in hrefs), f"non-navigating rows: {hrefs}"
    assert "#" not in hrefs


# --------------------------------------------------------------------------
# Every advertised destination actually opens for the user it is shown to.
# --------------------------------------------------------------------------


def _rendered_hrefs(client):
    import re

    html = client.get("/modules/").get_data(as_text=True)
    body = html.split('data-testid="modules-directory"', 1)[1]
    return re.findall(r'<li x-show="matches\([^)]*\)">\s*<a href="([^"]*)"', body)


@pytest.mark.parametrize(
    "enterprise_role",
    ["enterprise_architect", "solution_architect", "business_architect"],
)
def test_no_advertised_destination_is_forbidden(
    app, db_session, org, client, login_as, enterprise_role
):
    """A directory row the viewer cannot open is a dead button. This is the
    regression guard for the 19 hard-403 rows an enterprise_architect was
    shown before the role filter existed."""
    user = _make_user(db_session, org, enterprise_role=enterprise_role)
    login_as(client, user)

    forbidden = []
    for href in _rendered_hrefs(client):
        login_as(client, user)
        status = client.get(href).status_code
        if status in (401, 403, 404):
            forbidden.append((href, status))
    assert not forbidden, f"{enterprise_role} was offered unopenable rows: {forbidden}"


def test_role_exclusive_sections_are_hidden_from_other_personas(
    app, db_session, org, client, login_as
):
    """The admin / procurement / my-applications zones are EXCLUSIVE_SECTIONS
    in role_access.py. The directory unions every role's zones, so without a
    filter it advertised all three to everyone."""
    user = _make_user(db_session, org, enterprise_role="enterprise_architect")
    login_as(client, user)

    hrefs = _rendered_hrefs(client)
    leaked = [
        h
        for h in hrefs
        if h.startswith(("/admin/", "/procurement/", "/my-applications/"))
    ]
    assert not leaked, f"role-exclusive surfaces shown to a non-owner: {leaked}"


def test_platform_admin_still_sees_the_admin_zone(
    app, db_session, org, client, login_as
):
    """The filter must not be a blanket removal — the directory is still the
    long-tail answer for the persona that owns those sections."""
    user = _make_user(
        db_session, org, enterprise_role="platform_admin", platform_admin=True
    )
    login_as(client, user)

    hrefs = _rendered_hrefs(client)
    assert any(h.startswith("/admin/") for h in hrefs), (
        "platform admin lost the Admin zone entirely"
    )


# --------------------------------------------------------------------------
# _NOT_RENDERED: each entry is a recorded measurement, not an assumption.
# --------------------------------------------------------------------------


def test_not_rendered_entries_are_still_dead_or_duplicate(
    app, db_session, org, client, login_as
):
    """Every endpoint suppressed by `_NOT_RENDERED` must still be either a
    hard error or a redirect. If one becomes a live 200 page in its own right
    this fails, and the entry must be reinstated rather than staying hidden."""
    from flask import url_for

    from app.modules.modules_directory.routes import _NOT_RENDERED

    user = _make_user(
        db_session, org, enterprise_role="platform_admin", platform_admin=True
    )
    login_as(client, user)

    with app.test_request_context():
        urls = {ep: url_for(ep) for ep in _NOT_RENDERED}

    now_live = []
    for endpoint, url in urls.items():
        login_as(client, user)
        response = client.get(url)
        if response.status_code == 200:
            now_live.append((endpoint, url))
    assert not now_live, (
        "_NOT_RENDERED endpoints that now serve a real page and should be "
        f"listed again: {now_live}"
    )


def test_not_rendered_endpoints_are_absent_from_the_page_and_search(
    app, db_session, org, client, login_as
):
    """Suppressed modules must vanish from both surfaces that read the list —
    the directory page and the global-search index (which now calls
    visible_module_links(), not all_module_links())."""
    from flask import url_for
    from flask_login import login_user

    from app.modules.modules_directory.routes import (
        _NOT_RENDERED,
        all_module_links,
        visible_module_links,
    )

    user = _make_user(
        db_session, org, enterprise_role="platform_admin", platform_admin=True
    )
    login_as(client, user)

    with app.test_request_context():
        suppressed_urls = {url_for(endpoint) for endpoint in _NOT_RENDERED}

    hrefs = set(_rendered_hrefs(client))
    assert not (hrefs & suppressed_urls), (
        f"suppressed rows still rendered: {hrefs & suppressed_urls}"
    )

    with app.test_request_context("/"):
        login_user(user)
        searchable = {link["endpoint"] for link in visible_module_links()}
        known = {link["endpoint"] for link in all_module_links()}

    assert not (searchable & set(_NOT_RENDERED)), (
        "suppressed modules are still returned by global search"
    )
    # all_module_links() must keep knowing about them, or
    # tests/test_module_discoverability.py reports five phantom orphan modules.
    assert set(_NOT_RENDERED) <= known


# --------------------------------------------------------------------------
# The 500 that started this: an empty_state kwarg the macro does not accept.
# --------------------------------------------------------------------------


def test_maturity_heatmap_renders_with_no_capabilities(
    app, db_session, org, client, login_as
):
    """capability_maturity/heatmap.html imports `empty_state` from
    components/empty_state.html, whose CTA kwargs are `cta_text`/`cta_href` —
    it was calling it with `cta_label`, which raises TypeError inside Jinja and
    500s the page. The branch only renders when there are no capabilities, i.e.
    for every brand-new tenant."""
    user = _make_user(db_session, org, enterprise_role="enterprise_architect")
    login_as(client, user)

    response = client.get("/capability-maturity/heatmap")
    assert response.status_code == 200
