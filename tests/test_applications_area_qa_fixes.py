"""Regression tests for the Applications-area QA findings (Sep 2026 Fortune-500 walkthrough).

Covers the behavioural fixes for:

* D5  — bulk "Lifecycle" action actually updates ``lifecycle_status``.
* D6  — bulk Export respects the selected ``ids`` instead of exporting the whole portfolio.
* D7  — the Data Enrichment table round-trips cost/owner/criticality (save then reload).
* D12 — the vendor "Type" filter is populated from stored vendor types, not a hard-coded list.

Written against the shared fixtures in ``tests/conftest.py`` (``db_session`` rolls the whole
test back), per the project convention. D4 (frozen pagination getters in
``static/js/components/data_table.js``) and D13 (count-label wording in
``list_simple.html``) are front-end-only changes with no Python surface to assert here.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")


def _make_user(db_session, org_id):
    from app.models.user import User

    user = User(
        email=f"apps-qa-{uuid.uuid4().hex[:10]}@example.test",
        organization_id=org_id,
        confirmed=True,
        enterprise_role="enterprise_architect",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_app(db_session, org_id, name, **kwargs):
    from app.models.application_portfolio import ApplicationComponent

    row = ApplicationComponent(name=name, organization_id=org_id, **kwargs)
    db_session.add(row)
    db_session.flush()
    return row


# ─────────────────────────────────────────────────────────────── D5 lifecycle


def test_bulk_lifecycle_updates_selected_apps(db_session, make_org, client, login_as):
    org = make_org("d5")
    user = _make_user(db_session, org.id)
    a = _make_app(db_session, org.id, "D5 App A", lifecycle_status="2.2 tactical")
    b = _make_app(db_session, org.id, "D5 App B", lifecycle_status="2.2 tactical")

    login_as(client, user)
    resp = client.post(
        "/applications/api/bulk-lifecycle",
        json={"ids": [a.id, b.id], "lifecycle_stage": "3. sunset"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    payload = resp.get_json()
    assert payload["success"] is True
    assert payload["updated_count"] == 2

    db_session.expire_all()
    assert a.lifecycle_status == "3. sunset"
    assert b.lifecycle_status == "3. sunset"


def test_bulk_lifecycle_rejects_invalid_stage(db_session, make_org, client, login_as):
    org = make_org("d5b")
    user = _make_user(db_session, org.id)
    a = _make_app(db_session, org.id, "D5 App C", lifecycle_status="2.2 tactical")

    login_as(client, user)
    resp = client.post(
        "/applications/api/bulk-lifecycle",
        json={"ids": [a.id], "lifecycle_stage": "not-a-real-stage"},
    )
    assert resp.status_code == 400
    db_session.expire_all()
    assert a.lifecycle_status == "2.2 tactical"  # unchanged


# ───────────────────────────────────────────────────────────────── D6 export


def test_export_csv_respects_selection(db_session, make_org, client, login_as):
    org = make_org("d6")
    user = _make_user(db_session, org.id)
    keep = _make_app(db_session, org.id, "D6 Keep Me")
    _make_app(db_session, org.id, "D6 Exclude Me")

    login_as(client, user)
    resp = client.get(f"/applications/export/csv?ids={keep.id}")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "D6 Keep Me" in body
    assert "D6 Exclude Me" not in body


# ──────────────────────────────────────────────────────────────── D7 enrich


def test_enrich_roundtrips_to_candidates(db_session, make_org, client, login_as):
    """Save cost/owner/criticality, then confirm the reload endpoint returns them."""
    org = make_org("d7")
    user = _make_user(db_session, org.id)
    app_row = _make_app(db_session, org.id, "D7 Enrich Target")

    login_as(client, user)
    save = client.post(
        f"/applications/rationalization/api/enrich/{app_row.id}",
        json={
            "total_cost_of_ownership": 123456,
            "application_owner": "Enterprise Architecture",
            "business_criticality": "High",
        },
    )
    assert save.status_code == 200, save.get_data(as_text=True)
    assert save.get_json()["success"] is True

    login_as(client, user)
    reload = client.get("/applications/rationalization/api/enrich-candidates?limit=200")
    assert reload.status_code == 200
    apps = {a["id"]: a for a in reload.get_json()["applications"]}
    assert app_row.id in apps, "saved app must appear in the reload payload"
    got = apps[app_row.id]
    assert got["total_cost_of_ownership"] == 123456
    assert got["application_owner"] == "Enterprise Architecture"
    assert got["business_criticality"] == "High"


# ──────────────────────────────────────────────────────────── D12 vendor type


def test_vendor_type_filter_uses_stored_values(db_session, make_org, client, login_as):
    from app.models.vendor.vendor_organization import VendorOrganization

    org = make_org("d12")
    user = _make_user(db_session, org.id)

    marker = f"Systems Integrator {uuid.uuid4().hex[:6]}"
    code = f"VEND-D12-{uuid.uuid4().hex[:8].upper()}"
    vendor = VendorOrganization(
        name=f"D12 Vendor {uuid.uuid4().hex[:6]}",
        code=code,
        seed_source_id=f"test:{code}",
        vendor_type=marker,
        status="active",
    )
    db_session.add(vendor)
    db_session.flush()

    login_as(client, user)
    resp = client.get("/applications/vendors")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_data(as_text=True)
    # The stored type is offered as a filter option ...
    assert f'value="{marker}"' in body
    # ... and the old hard-coded vendor-type vocabulary is gone. ("Cloud" is not
    # asserted: an unrelated domain filter legitimately offers "Cloud Infrastructure".)
    assert 'value="Hybrid"' not in body
    assert 'value="Enterprise"' not in body
