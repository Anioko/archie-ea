"""RAID log (Assumption/Issue/Dependency) — the 2 Sep 2026 Capgemini
delivery-team dry-run found the register was Risk-only, 1 of 4 RAID
categories. These tests pin the FULL round trip — create via the real API,
then read it back both via the API and via the register page's own render —
not just that a row lands in the database. That distinction is the exact
lesson from this session's plateau-tagging bug (write worked, nothing could
ever read it back): a feature is not done until a human can see what they
just recorded, and that is what these tests actually check.
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
def ea_user(app):
    from app import db
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "Raid")
        uid = _make_user_id(db, org, "RaidEA", enterprise_role="enterprise_architect")
        yield uid, org
        from app.models.raid_item import RaidItem
        _cleanup_ids(db, RaidItem, [i.id for i in RaidItem.query.filter_by(organization_id=org).all()])
        _cleanup_ids(db, User, [uid])
        _cleanup_ids(db, Organization, [org])


def test_create_then_read_back_via_api(client, app, ea_user):
    """The exact round trip a real user needs: create a Dependency, then GET
    it back — not just assert a DB row exists."""
    uid, org = ea_user
    with app.app_context():
        _login(client, uid)
        r = client.post("/api/raid", json={
            "kind": "dependency",
            "title": "S/4HANA landscape build blocks Order-to-Cash dual-run",
            "owner": "Marcus Reed",
            "target_date": "2026-05-30",
            "programme_name": "Constellation",
        })
        assert r.status_code == 201, r.get_data(as_text=True)
        created = r.get_json()
        assert created["kind"] == "dependency"

        # Read back — this is the check the plateau bug skipped.
        r2 = client.get("/api/raid")
        assert r2.status_code == 200
        titles = [i["title"] for i in r2.get_json()]
        assert "S/4HANA landscape build blocks Order-to-Cash dual-run" in titles

        r3 = client.get("/api/raid?kind=dependency")
        kinds = {i["kind"] for i in r3.get_json()}
        assert kinds == {"dependency"}


def test_create_then_read_back_via_register_page_render(client, app, ea_user):
    """Not just the API — the actual HTML the register page renders, which is
    what a human looking at the screen actually sees."""
    uid, org = ea_user
    with app.app_context():
        _login(client, uid)
        r = client.post("/api/raid", json={
            "kind": "issue",
            "title": "Year-end close overlaps cutover window",
        })
        assert r.status_code == 201

        page = client.get("/risks/")
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert "Year-end close overlaps cutover window" in html
        assert "issue" in html.lower()


def test_status_transition_round_trips(client, app, ea_user):
    uid, org = ea_user
    with app.app_context():
        _login(client, uid)
        r = client.post("/api/raid", json={"kind": "assumption", "title": "Northwind stays on current AWS region"})
        item_id = r.get_json()["id"]

        r2 = client.patch(f"/api/raid/{item_id}", json={"status": "resolved"})
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "resolved"

        # Read back independently — the update actually persisted, not just echoed.
        r3 = client.get("/api/raid")
        match = next(i for i in r3.get_json() if i["id"] == item_id)
        assert match["status"] == "resolved"


def test_invalid_kind_rejected_not_silently_dropped(client, app, ea_user):
    uid, org = ea_user
    with app.app_context():
        _login(client, uid)
        r = client.post("/api/raid", json={"kind": "bogus", "title": "X"})
        assert r.status_code == 400
        assert "error" in r.get_json()
