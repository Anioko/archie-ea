"""T-14 regression: the admin org-users table can be sorted by URL param.

GET /admin/organizations/<id>?sort=<col>&dir=asc|desc orders by real User
columns; name sorts by (first_name, last_name) since full_name() is a Python
method, not something SQL can order by directly.
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


def test_sort_by_name_ascending(client, app):
    from app import db
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "OrgUserSort")
        admin_uid = _make_user_id(db, org, "SortAdmin", enterprise_role="platform_admin")
        # give admin_uid the real super-admin flag so it can reach this route
        admin = db.session.get(User, admin_uid)
        admin.is_platform_admin = True
        u1 = _make_user_id(db, org, "Zebra")
        db.session.get(User, u1).first_name = "Zebra"
        u2 = _make_user_id(db, org, "Alpha")
        db.session.get(User, u2).first_name = "Alpha"
        db.session.commit()
        other_ids = [u1, u2]
    try:
        with app.app_context():
            _login(client, admin_uid)
            r = client.get(f"/admin/organizations/{org}?sort=name&dir=asc")
            assert r.status_code == 200
            body = r.get_data(as_text=True)
            assert body.index("Alpha") < body.index("Zebra")
    finally:
        with app.app_context():
            _cleanup_ids(db, User, other_ids + [admin_uid])
            _cleanup_ids(db, Organization, [org])


def test_unrecognised_sort_key_falls_back_safely(client, app):
    from app import db
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "OrgUserSort2")
        admin_uid = _make_user_id(db, org, "SortAdmin2", enterprise_role="platform_admin")
        db.session.get(User, admin_uid).is_platform_admin = True
        db.session.commit()
    try:
        with app.app_context():
            _login(client, admin_uid)
            r = client.get(f"/admin/organizations/{org}?sort=bogus&dir=asc")
            assert r.status_code == 200
    finally:
        with app.app_context():
            _cleanup_ids(db, User, [admin_uid])
            _cleanup_ids(db, Organization, [org])
