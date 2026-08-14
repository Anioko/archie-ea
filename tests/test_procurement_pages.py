"""Smoke coverage for the procurement module's page-shell conversion.

The procurement templates (contracts_list, licenses_list, renewals_dashboard,
spend_analytics, compliance_dashboard) were converted onto the standard
platform shell (page_header macro, empty_state macro, em-dash nulls). This
file only asserts the pages render for an authenticated procurement user —
regressions in the underlying business logic are out of scope, this guards
against template errors (undefined macros/vars, broken url_for calls, etc).

Uses the shared fixtures in tests/conftest.py (db_session rolls back) and the
_clear_auth_caches pattern from tests/test_bounded_ai_endpoints.py.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def procurement_user(db_session, make_org, client):
    """A confirmed procurement-role user in a fresh org, logged into the test client."""
    from app.models.user import User

    org = make_org("procurement-pages")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"procurement-{suffix}@example.com",
        first_name="Procurement",
        last_name="Tester",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="procurement",
    )
    db_session.add(user)
    db_session.flush()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True

    _clear_auth_caches()
    return org


def _clear_auth_caches():
    """Anything that touches current_user on the shared app context re-caches
    an anonymous user in `g`; call this right before each test-client request."""
    from flask import g, has_app_context

    if has_app_context():
        for cached in ("_login_user", "_current_user", "current_org_id", "current_org"):
            if hasattr(g, cached):
                delattr(g, cached)


@pytest.mark.parametrize(
    "path",
    [
        "/procurement/contracts",
        "/procurement/licenses",
        "/procurement/renewals",
        "/procurement/spend",
        "/procurement/compliance",
    ],
)
def test_procurement_page_renders_for_authenticated_user(client, procurement_user, path):
    _clear_auth_caches()
    resp = client.get(path)
    assert resp.status_code != 401
    assert resp.status_code < 500, resp.data[:2000]


def test_procurement_index_redirects_to_contracts(client, procurement_user):
    _clear_auth_caches()
    resp = client.get("/procurement/")
    assert resp.status_code in (301, 302)


@pytest.mark.parametrize("path", ["/procurement/contracts/new", "/procurement/licenses/new"])
def test_procurement_create_forms_render(client, procurement_user, path):
    """Covers contract_form.html / license_form.html — the user-picker and the
    isSubmitting/confirmSubmit Alpine additions in particular."""
    _clear_auth_caches()
    resp = client.get(path)
    assert resp.status_code != 401
    assert resp.status_code < 500, resp.data[:2000]


def test_procurement_detail_pages_render_with_real_records(client, procurement_user, db_session):
    """contract_detail.html / license_detail.html / edit forms with a persisted
    row — the page_header breadcrumb + null-field rendering path that the
    empty-portfolio tests above never exercise."""
    import datetime as _dt

    from app.models.application_portfolio import VendorContract
    from app.models.license_entitlement import LicenseEntitlement

    contract = VendorContract(
        organization_id=procurement_user.id,
        contract_name="Test Contract",
        status="active",
        start_date=_dt.date.today(),
    )
    db_session.add(contract)
    db_session.flush()

    license_ = LicenseEntitlement(
        organization_id=procurement_user.id,
        contract_id=contract.id,
        product_name="Test Product",
        license_type="named_user",
        quantity_entitled=10,
        quantity_deployed=5,
        compliance_status="compliant",
    )
    db_session.add(license_)
    db_session.flush()

    _clear_auth_caches()
    resp = client.get(f"/procurement/contracts/{contract.id}")
    assert resp.status_code < 500, resp.data[:2000]

    _clear_auth_caches()
    resp = client.get(f"/procurement/contracts/{contract.id}/edit")
    assert resp.status_code < 500, resp.data[:2000]

    _clear_auth_caches()
    resp = client.get(f"/procurement/licenses/{license_.id}")
    assert resp.status_code < 500, resp.data[:2000]

    _clear_auth_caches()
    resp = client.get(f"/procurement/licenses/{license_.id}/edit")
    assert resp.status_code < 500, resp.data[:2000]

    # These list/dashboard pages now have at least one non-empty row, which
    # exercises the table/summary branches the empty-state tests above skip.
    for path in ("/procurement/contracts", "/procurement/licenses", "/procurement/compliance", "/procurement/spend"):
        _clear_auth_caches()
        resp = client.get(path)
        assert resp.status_code < 500, (path, resp.data[:2000])
