"""ARCH-014: ``GET /api/vendors/`` must report the collection total, not the page size.

The endpoint returned ``"total": len(vendors)`` — the number of rows in the page
just serialised — and read only ``limit``, silently ignoring ``per_page``. A
consumer paging on ``total`` (the AI agent's vendor tools, any customer
integration) concluded the catalogue held 10 vendors when it held 45, and the
truncation was undetectable from the response.

Uses the shared fixtures in tests/conftest.py (db_session rolls back
automatically; app is session-scoped).
"""

import uuid

import pytest

SEEDED = 45


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
def vendor_client(app, db_session, make_org):
    from app.models.user import User
    from app.models.vendor.vendor_organization import VendorOrganization

    org = make_org("vendor-total")
    user = User(
        email=f"vendors-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Vee",
        last_name="Endor",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)

    tag = uuid.uuid4().hex[:8]
    for i in range(SEEDED):
        # VendorOrganization is deliberately not TenantMixin (shared reference
        # data, globally-unique name) — hence the uuid tag in the search filter
        # rather than an organization_id scope.
        db_session.add(VendorOrganization(name=f"ZZ Vendor {tag} {i:03d}"))
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return client, tag


def _total(client, tag, query=""):
    resp = client.get(f"/api/vendors/?search=ZZ+Vendor+{tag}{query}")
    assert resp.status_code == 200, resp.data
    return resp.get_json()


def test_total_is_collection_count_not_page_size(vendor_client):
    client, tag = vendor_client
    body = _total(client, tag)
    assert body["total"] == SEEDED
    # Default page size still truncates the *items* — that is fine and expected;
    # what must not happen is `total` shrinking to match.
    assert len(body["vendors"]) <= SEEDED


def test_total_invariant_across_page_sizes(vendor_client):
    client, tag = vendor_client
    totals = {
        "default": _total(client, tag)["total"],
        "per_page=5": _total(client, tag, "&per_page=5")["total"],
        "per_page=200": _total(client, tag, "&per_page=200")["total"],
        "limit=200": _total(client, tag, "&limit=200")["total"],
    }
    assert set(totals.values()) == {SEEDED}, totals


def test_per_page_is_honoured(vendor_client):
    client, tag = vendor_client
    five = _total(client, tag, "&per_page=5")
    assert len(five["vendors"]) == 5
    assert five["per_page"] == 5

    # per_page above MAX_PER_PAGE clamps, but must still return everything seeded.
    big = _total(client, tag, "&per_page=200")
    assert len(big["vendors"]) == SEEDED


def test_paging_walks_the_whole_collection(vendor_client):
    client, tag = vendor_client
    seen = []
    for page in (1, 2, 3):
        body = _total(client, tag, f"&per_page=20&page={page}")
        assert body["total"] == SEEDED
        seen.extend(v["id"] for v in body["vendors"])
    assert len(set(seen)) == SEEDED
