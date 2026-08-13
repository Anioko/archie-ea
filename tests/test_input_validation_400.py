"""Bad user input must get a 4xx with a message, never a 500.

Pins the fixes from the 13 Aug 2026 validation audit: four write-handlers did
bare ``int()``/``float()`` on request data with no try/except anywhere in the
function, so ordinary fat-fingered input (``{"influence_level": "high"}``)
crashed into the generic 500 handler instead of telling the user which field
was wrong.

Uses the shared fixtures in tests/conftest.py (db_session rolls back
automatically; app is session-scoped).
"""

import uuid

import pytest


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
def admin_client(app, db_session, make_org):
    from app.models.user import User

    org = make_org("validation")
    user = User(
        email=f"validation-{uuid.uuid4().hex[:8]}@example.com",
        first_name="Val",
        last_name="Idator",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    db_session.add(user)
    db_session.flush()

    client = app.test_client()
    _login(client, user.id)
    return client


def test_stakeholder_create_bad_int_is_400(admin_client):
    resp = admin_client.post(
        "/api/stakeholders/",
        json={"name": "X", "influence_level": "high"},
    )
    assert resp.status_code == 400
    assert "influence_level" in resp.get_json()["error"]


def test_stakeholder_create_bad_solution_id_is_400(admin_client):
    resp = admin_client.post(
        "/api/stakeholders/",
        json={"name": "X", "solution_id": "not-a-number"},
    )
    assert resp.status_code == 400


def test_stakeholder_update_bad_int_is_400(admin_client):
    created = admin_client.post("/api/stakeholders/", json={"name": "Patch Target"})
    assert created.status_code == 201
    sid = created.get_json()["id"]

    resp = admin_client.patch(
        f"/api/stakeholders/{sid}", json={"influence_level": "very"}
    )
    assert resp.status_code == 400


def test_bulk_process_link_bad_threshold_is_400(admin_client, app):
    from flask import url_for

    with app.test_request_context():
        url = url_for("application_api.api_bulk_process_link")
    resp = admin_client.post(
        url, json={"application_ids": [], "confidence_threshold": "abc"}
    )
    assert resp.status_code == 400

    resp = admin_client.post(
        url, json={"application_ids": [], "confidence_threshold": 7}
    )
    assert resp.status_code == 400


def test_template_search_bad_limit_is_400(admin_client, app):
    from flask import url_for

    with app.test_request_context():
        url = url_for("application_mgmt.search_templates_advanced")
    resp = admin_client.post(url, json={"query": "x", "limit": "abc"})
    assert resp.status_code == 400


def test_billing_upgrade_bad_seats_is_not_500(admin_client, app):
    from flask import url_for

    with app.test_request_context():
        url = url_for("billing.billing_upgrade")
    resp = admin_client.post(url, data={"plan": "pro", "seats": "many"})
    # A plain HTML form: the fix redirects back with a flash, never a 500.
    assert resp.status_code < 500
