"""T-14 regression: the Gap register can be sorted, server-side, by URL param.

Same pattern as tests/test_risk_register_sort.py — GET /enterprise/implementation/
gap-analysis?sort=<col>&dir=asc|desc orders by the requested column, falling back
safely to name for an unrecognised key.
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


def _make_gaps(org_id):
    from app import db
    from app.models.implementation_migration import Gap

    rows = [
        Gap(name="Zebra gap", organization_id=org_id),
        Gap(name="Alpha gap", organization_id=org_id),
        Gap(name="Mid gap", organization_id=org_id),
    ]
    db.session.add_all(rows)
    db.session.commit()
    return [r.id for r in rows]


def test_sort_by_name_ascending(client, app):
    from app import db
    from app.models.implementation_migration import Gap
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "GapSort")
        uid = _make_user_id(db, org, "GapSortUser", enterprise_role="enterprise_architect")
        ids = _make_gaps(org)
    try:
        with app.app_context():
            _login(client, uid)
            r = client.get("/enterprise/implementation/gap-analysis?sort=name&dir=asc")
            assert r.status_code == 200
            body = r.get_data(as_text=True)
            assert body.index("Alpha gap") < body.index("Mid gap") < body.index("Zebra gap")
    finally:
        with app.app_context():
            _cleanup_ids(db, Gap, ids)
            _cleanup_ids(db, User, [uid])
            _cleanup_ids(db, Organization, [org])


def test_unrecognised_sort_key_falls_back_safely(client, app):
    from app import db
    from app.models.implementation_migration import Gap
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "GapSort2")
        uid = _make_user_id(db, org, "GapSortUser2", enterprise_role="enterprise_architect")
        ids = _make_gaps(org)
    try:
        with app.app_context():
            _login(client, uid)
            r = client.get("/enterprise/implementation/gap-analysis?sort=bogus&dir=asc")
            assert r.status_code == 200
    finally:
        with app.app_context():
            _cleanup_ids(db, Gap, ids)
            _cleanup_ids(db, User, [uid])
            _cleanup_ids(db, Organization, [org])
