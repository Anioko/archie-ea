"""Capability Map on the screen system (shell-overhaul Wave 2, Task 3).

Product design review pinned three structural defects:

- `/capability-map/` and `/capability-map/hierarchy` disagreed on the total
  capability count (500 vs 495) — they used two independent counting
  queries. `/capability-map/` (via ``api_unified_domains``) did a flat
  ``BusinessCapability.query.count()``; `/capability-map/hierarchy`'s Alpine
  ``countAll()`` walked only the subtree reachable from level-1 roots, so
  capabilities orphaned from that tree were silently dropped from the
  second count. Both pages now render the total from a single function,
  ``count_business_capabilities`` (app/modules/capabilities/services/
  capability_count_service.py).
- two competing rows of 9+ view-mode switchers (page-links row PLUS an
  11-tab in-page Alpine strip) — consolidated into one segmented control
  (the true view modes) plus a "Lens" dropdown for the rest.
- red gap-dots with no legend — a ``data-testid="capability-legend"``
  element now documents color -> meaning wherever dots render.
"""

from __future__ import annotations

import re
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

    org = make_org(f"cap-map-shell-{label}")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"cap-map-shell-{label}-{suffix}@example.com",
        first_name="Cap",
        last_name="Shell",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    user.password = "Sup3rSecret!23"
    db_session.add(user)
    db_session.flush()
    db_session.commit()
    return user.id, org


def _seed_capabilities(db_session, org, count):
    """Seed ``count`` BusinessCapability rows: a level-1 root plus
    ``count - 1`` level-2 children under it, all reachable from the root so
    both the flat count and the old tree-walk would (if it still ran) agree
    — the point of this fixture is a known, unambiguous total."""
    from app.models.business_capabilities import BusinessCapability

    root = BusinessCapability(
        name=f"Root Capability {uuid.uuid4().hex[:8]}",
        level=1,
        business_domain="Operations",
        organization_id=org.id,
    )
    db_session.add(root)
    db_session.flush()

    for i in range(count - 1):
        child = BusinessCapability(
            name=f"Child Capability {i}-{uuid.uuid4().hex[:8]}",
            level=2,
            business_domain="Operations",
            parent_capability_id=root.id,
            organization_id=org.id,
        )
        db_session.add(child)
    db_session.commit()


def _get(app, db_session, make_org, label, path, seed_count=7):
    user_id, org = _make_user(db_session, make_org, label)
    _seed_capabilities(db_session, org, seed_count)
    client = app.test_client()
    _login(client, user_id)
    resp = client.get(path)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:2000]
    return resp.get_data(as_text=True)


def _extract_capability_total(html):
    """Pull the total-capabilities figure. `/capability-map/` renders it in
    `<span id="unified-cap-count">N</span>`; `/capability-map/hierarchy`
    renders it as "N capabilities" in the coverage banner. Both are now
    sourced from the same server-side counting function."""
    match = re.search(r'id="unified-cap-count">\s*(\d+)\s*<', html)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s+capabilities", html)
    assert match, "could not find a '<N> capabilities' figure in the page"
    return int(match.group(1))


def test_index_and_hierarchy_report_the_same_total(app, db_session, make_org):
    """The historical bug: /capability-map/ said 500, /capability-map/hierarchy
    said 495. Seed a known count and assert both pages report it."""
    user_id, org = _make_user(db_session, make_org, "same-total")
    _seed_capabilities(db_session, org, 11)

    client = app.test_client()
    _login(client, user_id)

    index_html = client.get("/capability-map/").get_data(as_text=True)
    hierarchy_html = client.get("/capability-map/hierarchy").get_data(as_text=True)

    index_total = _extract_capability_total(index_html)
    hierarchy_total = _extract_capability_total(hierarchy_html)

    assert index_total == 11, index_total
    assert hierarchy_total == 11, hierarchy_total
    assert index_total == hierarchy_total


def test_index_page_has_exactly_one_h1(app, db_session, make_org):
    html = _get(app, db_session, make_org, "one-h1", "/capability-map/")
    assert html.count("<h1") == 1


def test_legend_exists_for_gap_dot_indicators(app, db_session, make_org):
    """A legend must exist wherever the red/amber/emerald gap-dots render —
    on both the index page's Capability Model tab and the hierarchy page's
    coverage dots."""
    index_html = _get(app, db_session, make_org, "legend-index", "/capability-map/")
    assert 'data-testid="capability-legend"' in index_html

    hierarchy_html = _get(
        app, db_session, make_org, "legend-hierarchy", "/capability-map/hierarchy"
    )
    assert 'data-testid="capability-legend"' in hierarchy_html


def test_single_view_switcher_row(app, db_session, make_org):
    """The old page had two competing rows of 9+ view-mode switchers — one
    page-link row and one 11-button Alpine tab strip. There must now be
    exactly one segmented-control row (data-testid="capability-view-switcher")
    and the old tab-strip's per-tab role="tab" buttons must be gone."""
    html = _get(app, db_session, make_org, "switcher", "/capability-map/")
    assert html.count('data-testid="capability-view-switcher"') == 1
    assert 'role="tab" id="tab-' not in html, "the old 11-button tab strip must be gone"
    assert 'id="capability-lens"' in html, "the Lens dropdown must replace it"
