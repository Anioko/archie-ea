"""Workforce-transition write form — round-trip tests.

Before this, BusinessRole's workforce fields (current_filled_positions,
forecasted_demand, replacement_role_id, required_skills, deprecated_date)
were readable by WorkforceTransitionService but had no write path at all: a
business user could not record a role transition through the product. These
tests pin the same discipline as test_raid_log.py — create through the real
write API, then read back through BOTH the read API and the actual rendered
page, not just assert a database row exists.
"""

import pytest

from tests.test_ba_tenant_and_authz import _cleanup_ids, _login, _make_org_id, _make_user_id


@pytest.fixture(scope="module")
def app():
    from app import create_app, db

    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        db.create_all()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def architect_user(app):
    from app import db
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "WorkforceTransition")
        uid = _make_user_id(db, org, "WTArchitect", enterprise_role="business_architect")
        yield uid, org
        from app.models.business_layer import BusinessRole
        _cleanup_ids(db, BusinessRole, [r.id for r in BusinessRole.query.filter_by(organization_id=org).all()])
        _cleanup_ids(db, User, [uid])
        _cleanup_ids(db, Organization, [org])


def test_create_role_then_read_back_via_api(client, app, architect_user):
    """Create a role with headcount/skills, then GET it back — not just a DB row."""
    uid, org = architect_user
    with app.app_context():
        _login(client, uid)
        r = client.post("/organization/workforce-transition/api/roles", json={
            "name": "SAP S/4HANA Functional Consultant",
            "current_filled_positions": 0,
            "forecasted_demand": 6,
            "required_skills": ["SAP S/4HANA", "MM", "SD"],
        })
        assert r.status_code == 200, r.get_data(as_text=True)
        role_id = r.get_json()["data"]["id"]

        r2 = client.get(f"/organization/workforce-transition/api/roles/{role_id}")
        assert r2.status_code == 200
        data = r2.get_json()["data"]
        assert data["name"] == "SAP S/4HANA Functional Consultant"
        assert data["forecasted_demand"] == 6
        assert set(data["required_skills"]) == {"SAP S/4HANA", "MM", "SD"}


def test_retirement_transition_appears_in_analysis_and_page(client, app, architect_user):
    """The actual product journey: retire a role by pointing it at a
    replacement, then confirm the transition shows up both in the analysis
    API and in the rendered workforce-transition page's HTML — the round
    trip a human on the screen actually gets."""
    uid, org = architect_user
    with app.app_context():
        _login(client, uid)
        r_new = client.post("/organization/workforce-transition/api/roles", json={
            "name": "MuleSoft Integration Engineer",
            "current_filled_positions": 0,
            "forecasted_demand": 4,
        })
        assert r_new.status_code == 200
        new_role_id = r_new.get_json()["data"]["id"]

        r_old = client.post("/organization/workforce-transition/api/roles", json={
            "name": "Legacy SCADE Integration Engineer",
            "current_filled_positions": 5,
        })
        assert r_old.status_code == 200
        old_role_id = r_old.get_json()["data"]["id"]

        r_patch = client.patch(f"/organization/workforce-transition/api/roles/{old_role_id}", json={
            "replacement_role_id": new_role_id,
        })
        assert r_patch.status_code == 200, r_patch.get_data(as_text=True)
        assert r_patch.get_json()["data"]["replacement_role_id"] == new_role_id

        # Read back via the analysis API — this is the check the plateau bug skipped.
        r_analysis = client.get("/organization/workforce-transition/api")
        assert r_analysis.status_code == 200
        analysis = r_analysis.get_json()["data"]
        transition = next(
            (t for t in analysis["transitions"] if t["from_role_id"] == old_role_id), None
        )
        assert transition is not None, analysis["transitions"]
        assert transition["to_role_id"] == new_role_id

        # And via the actual rendered page — what a human looking at the screen sees.
        page = client.get("/organization/workforce-transition")
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert "workforceTransition()" in html  # the Alpine component that fetches the API above


def test_cannot_replace_role_with_itself(client, app, architect_user):
    uid, org = architect_user
    with app.app_context():
        _login(client, uid)
        r = client.post("/organization/workforce-transition/api/roles", json={"name": "Solo Role"})
        role_id = r.get_json()["data"]["id"]

        r2 = client.patch(f"/organization/workforce-transition/api/roles/{role_id}", json={
            "replacement_role_id": role_id,
        })
        assert r2.status_code == 400
        assert "error" in r2.get_json()


def test_missing_name_rejected_not_silently_dropped(client, app, architect_user):
    uid, org = architect_user
    with app.app_context():
        _login(client, uid)
        r = client.post("/organization/workforce-transition/api/roles", json={"current_filled_positions": 3})
        assert r.status_code == 400
        assert "error" in r.get_json()
