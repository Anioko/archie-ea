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

import uuid

import pytest


@pytest.fixture
def org_client(app, db_session, make_org, login_as):
    from app.models.user import User

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
