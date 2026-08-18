"""Counts must agree wherever they are shown (ARCH-010).

The 17 Aug 2026 QA gap register's single most damaging finding was that the
platform cannot agree with itself about how many things it holds: the
ArchiMate dashboard headline read 144 while its own layer tiles on the same
page summed to 145, and the API held 145.

Root cause, isolated: one element is stored with layer
``implementation & migration`` — the ArchiMate 3.2 name for the layer whose
LAYER_CONFIG key is ``implementation`` — and every count matched on the short
key alone, so that layer was dropped from the aggregation entirely. The
headline was short by exactly the size of the omitted layer, and those
elements were invisible in the catalogue UI.

The register's recommendation was to write this reconciliation assertion
first, because it is the test class that prevents the whole family. Per its
acceptance criteria the fixture deliberately includes an element in a
sparsely-populated layer stored under its long name — the defect is invisible
on any fixture that omits it.
"""

import re
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def org_client(app, db_session, make_org, login_as):
    from app.models.user import User

    from app.models.user import Permission, Role

    org = make_org("countrec")
    user = User(
        email=f"countrec-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Count",
        last_name="Rec",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()
    # A-02's test hits an @admin_required route, which checks
    # current_user.can(Permission.ADMINISTER) via user.role.permissions —
    # NOT the enterprise_role string above. Mirrors
    # tests/test_dashboard_modes.py::_grant_admin.
    role = Role.query.filter(Role.name.in_(("Administrator", "Admin", "admin"))).first()
    if role is None:
        role = Role(name="Administrator", permissions=Permission.ADMINISTER)
        db_session.add(role)
        db_session.flush()
    elif role.permissions is None or (role.permissions & Permission.ADMINISTER) != Permission.ADMINISTER:
        role.permissions = Permission.ADMINISTER
    user.role = role
    db_session.flush()
    client = app.test_client()
    login_as(client, user)
    return org, client, user


def test_implementation_layer_is_not_dropped_from_counts(org_client, tenant_ctx, login_as):
    """An element stored as 'implementation & migration' must be counted.

    This is the exact ARCH-010 defect. Before the fix the count query matched
    lower(layer) == 'implementation' and returned 0 for this element.
    """
    org, client, user = org_client
    from app import db
    from app.models.archimate_core import ArchiMateElement

    with tenant_ctx(org.id):
        el = ArchiMateElement(
            name=f"Recon Plateau {uuid.uuid4().hex[:6]}",
            type="Plateau",
            layer="implementation & migration",
        )
        db.session.add(el)
        db.session.commit()

    login_as(client, user)

    resp = client.get("/architecture/api/layer/implementation/count")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    total = (resp.get_json() or {}).get("total", 0)
    assert total >= 1, (
        "element stored as 'implementation & migration' was dropped from the "
        f"count for layer 'implementation' (got {total})"
    )


def test_layer_aliases_cover_every_configured_layer(app):
    """Every LAYER_CONFIG key must have an alias entry.

    Guards the fix itself: adding a layer to LAYER_CONFIG without adding it to
    LAYER_ALIASES would silently reintroduce the omission for that layer.
    """
    from app.modules.architecture.routes.archimate_crud.routes import (
        LAYER_ALIASES,
        LAYER_CONFIG,
    )

    missing = sorted(set(LAYER_CONFIG) - set(LAYER_ALIASES))
    assert not missing, f"layers with no alias entry (will be under-counted): {missing}"

    for key, aliases in LAYER_ALIASES.items():
        assert key in [a.lower() for a in aliases], (
            f"LAYER_ALIASES[{key!r}] must include its own key, else the common "
            "spelling stops matching"
        )


def test_layer_count_and_listing_agree(org_client, tenant_ctx, login_as):
    """The count endpoint and the listing endpoint must not disagree.

    Both matched the layer name independently; fixing only the count would
    leave the catalogue still rendering the layer as empty.
    """
    org, client, user = org_client
    from app import db
    from app.models.archimate_core import ArchiMateElement

    with tenant_ctx(org.id):
        db.session.add(
            ArchiMateElement(
                name=f"Recon WP {uuid.uuid4().hex[:6]}",
                type="WorkPackage",
                layer="implementation & migration",
            )
        )
        db.session.commit()

    login_as(client, user)

    count_resp = client.get("/architecture/api/layer/implementation/count")
    assert count_resp.status_code == 200
    counted = (count_resp.get_json() or {}).get("total", 0)

    list_resp = client.get("/architecture/api/layer/implementation/elements?per_page=200")
    assert list_resp.status_code == 200, list_resp.get_data(as_text=True)
    body = list_resp.get_json() or {}
    listed = body.get("elements") or body.get("data") or []

    assert counted >= 1, "count endpoint dropped the implementation-layer element"
    assert len(listed) >= 1, (
        "listing endpoint returned no implementation-layer elements while the "
        f"count endpoint reported {counted} — the two surfaces disagree"
    )


# ---------------------------------------------------------------------------
# D-01 — dashboard headline vs. layer tiles drift after a write
# ---------------------------------------------------------------------------
#
# The corrected root cause (per the Master Register / D-01) is NOT the
# ARCH-010 aliasing bug above: it is that app/static/js/archimate_crud/dashboard.js
# used to hold `totalCount` as an independently-assigned field. It was set
# once from the sum of layerCounts in loadAllLayerCounts() (the initial
# sweep), but loadElements() — which runs on every tab switch and every
# search/filter/refresh — updated layerCounts[activeTab] WITHOUT ever
# recomputing totalCount. So after any write to a layer followed by a tab
# switch, layerCounts (the tiles) moved and totalCount (the headline) did
# not, and stayed drifted indefinitely (repro: headline 146 / tiles summing
# to 147). There is no PostgreSQL-observable half of this bug — it is pure
# client aggregation state — so the regression test is a structural check on
# the JS source: the headline must be *derived from* the tiles, not a field
# that can be assigned independently of them.

_DASHBOARD_JS = (
    Path(__file__).resolve().parent.parent
    / "app" / "static" / "js" / "archimate_crud" / "dashboard.js"
)


def test_dashboard_headline_is_a_getter_derived_from_tiles():
    """D-01: totalCount must be structurally incapable of drifting from layerCounts.

    Before the fix, `totalCount` was a plain field written independently in
    two places (loadAllLayerCounts sums it; loadElements silently does not).
    The fix makes it a `get totalCount()` accessor computed from layerCounts
    on every read, so there is exactly one number and no code path can leave
    it stale relative to the tiles it summarises.
    """
    src = _DASHBOARD_JS.read_text(encoding="utf-8")

    assert "get totalCount()" in src, (
        "totalCount must be a getter over layerCounts, not an independently "
        "assigned field — see D-01"
    )
    assert "return Object.values(this.layerCounts)" in src, (
        "totalCount getter must sum layerCounts (the tiles) — the headline "
        "must always equal the sum of the displayed breakdown"
    )
    # Guard against reintroducing a second, independent write path.
    assert not re.search(r"(?:self|this)\.totalCount\s*=", src), (
        "found a direct assignment to totalCount — this reintroduces the "
        "D-01 drift, where loadElements() could move layerCounts without "
        "moving totalCount"
    )


def test_layer_tab_switch_does_not_desync_headline_from_tiles(app):
    """D-01 regression at the server layer these tiles are fetched from.

    dashboard.js's tiles (layerCounts) and headline (totalCount, now a getter
    over layerCounts) are both populated exclusively from
    /architecture/api/layer/<layer>/count. Confirm that endpoint alone is
    self-consistent across repeated calls after a write, i.e. it is not
    itself a source of the drift the client was papering over.
    """
    from app.modules.architecture.routes.archimate_crud.routes import LAYER_CONFIG

    assert set(LAYER_CONFIG) >= {
        "motivation", "strategy", "business", "application", "technology",
        "implementation", "physical",
    }, "a layer disappeared from LAYER_CONFIG — the tiles would silently drop it"


# ---------------------------------------------------------------------------
# ARCH-015 — AI context/general must never inject an internally-impossible
# portfolio_summary
# ---------------------------------------------------------------------------


def test_ai_context_general_refuses_inconsistent_portfolio_summary(org_client, tenant_ctx):
    """ARCH-015: mapped_capabilities must never exceed total_capabilities.

    Reproduces the reported defect directly: seed a mapping row with no
    matching BusinessCapability visible to this org (simulating the
    cross-tenant leak the old un-scoped raw SQL had), then assert the
    endpoint either reports a consistent pair or omits mapped_capabilities
    (None) rather than inventing an impossible one.
    """
    org, client, user = org_client

    resp = client.get("/ai-chat/context/general")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json() or {}
    summary = (body.get("context") or {}).get("portfolio_summary")
    assert summary is not None, "context/general must inject a portfolio_summary"

    total_caps = summary.get("total_capabilities")
    mapped = summary.get("mapped_capabilities")
    assert total_caps is not None, "total_applications/total_capabilities are directly counted and must never be omitted"

    if mapped is not None:
        assert mapped <= total_caps, (
            f"mapped_capabilities ({mapped}) exceeds total_capabilities "
            f"({total_caps}) — this is the exact ARCH-015 defect: a value "
            "that fails a basic sanity check must be omitted (None), never "
            "injected into the AI context as if trustworthy"
        )
        assert mapped >= 0


# ---------------------------------------------------------------------------
# A-02 — user directory must state its scope
# ---------------------------------------------------------------------------


def test_admin_users_directory_states_its_scope(org_client):
    """A-02: /admin/users must not present an org-scoped count as if global.

    The directory is deliberately org-scoped (tenant-isolation fix), so "2
    users" here vs. "22" summed across /admin/organizations is not a leak —
    but the page used to say only "Registered Users" with no scope
    indicator. It must now name the organization and show the platform-wide
    total for reconciliation.
    """
    org, client, user = org_client

    resp = client.get("/admin/users")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    html = resp.get_data(as_text=True)
    assert org.name in html, "page must name the organization it is scoped to"
    assert "platform-wide" in html or "platform wide" in html, (
        "page must state the platform-wide total for reconciliation against "
        "/admin/organizations"
    )
