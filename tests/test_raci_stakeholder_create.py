"""F-08 regression: the RACI picker can create a stakeholder that doesn't exist yet.

The 2 Sep 2026 audit found the Add Stakeholder modal was search-only — no name
field, so a stakeholder that wasn't already a BusinessActor/BusinessRole/User could
never be added. POST /organization/raci/api/stakeholder creates a real BusinessActor
(an ArchiMate element via its before_insert listener) and returns the same
{type, id, name, sublabel} shape the search endpoint returns.
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


def test_creates_business_actor_and_archimate_element(client, app):
    from app import db
    from app.models.business_layer import BusinessActor
    from app.models.organization import Organization
    from app.models.user import Role, User

    with app.app_context():
        org = _make_org_id(db, "Raci")
        uid = _make_user_id(db, org, "RaciBA", enterprise_role="business_architect",
                            role_name="Administrator")
    actor_id = None
    try:
        with app.app_context():
            _login(client, uid)
            r = client.post("/organization/raci/api/stakeholder", json={"name": "Revenue Operations Lead"})
            assert r.status_code == 200, r.get_data(as_text=True)
            body = r.get_json()["data"]
            assert body["type"] == "actor"
            assert body["name"] == "Revenue Operations Lead"
            actor_id = body["id"]

            actor = db.session.get(BusinessActor, actor_id)
            assert actor is not None
            assert actor.archimate_element_id is not None  # joined the backbone
    finally:
        with app.app_context():
            if actor_id:
                _cleanup_ids(db, BusinessActor, [actor_id])
            _cleanup_ids(db, User, [uid])
            _cleanup_ids(db, Organization, [org])


def test_blank_name_is_rejected(client, app):
    from app import db
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "Raci")
        uid = _make_user_id(db, org, "RaciBA2", enterprise_role="business_architect",
                            role_name="Administrator")
    try:
        with app.app_context():
            _login(client, uid)
            r = client.post("/organization/raci/api/stakeholder", json={"name": "  "})
            assert r.status_code == 400
    finally:
        with app.app_context():
            _cleanup_ids(db, User, [uid])
            _cleanup_ids(db, Organization, [org])
