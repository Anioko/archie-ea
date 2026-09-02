"""F-14 regression: the risk register can be sorted, server-side, by URL param.

The 2 Sep 2026 audit found the risk register (one of six tables with no sort at
all) always ordered by Risk.id. GET /risks/?sort=<col>&dir=asc|desc now orders by
the requested column, defaulting safely to id for an unrecognised key so a
stale/hand-edited URL can't 500 the page.
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


def _make_risks(app, org_id):
    from app import db
    from app.models.risk import Risk

    with app.app_context():
        rows = [
            Risk(title="Zebra risk", likelihood=1, impact=1, organization_id=org_id),
            Risk(title="Alpha risk", likelihood=5, impact=5, organization_id=org_id),
            Risk(title="Mid risk", likelihood=3, impact=3, organization_id=org_id),
        ]
        db.session.add_all(rows)
        db.session.commit()
        return [r.id for r in rows]


def test_sort_by_title_ascending(client, app):
    from app import db
    from app.models.organization import Organization
    from app.models.risk import Risk
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "RiskSort")
        uid = _make_user_id(db, org, "RiskSortUser", enterprise_role="enterprise_architect")
    ids = _make_risks(app, org)
    try:
        with app.app_context():
            _login(client, uid)
            r = client.get("/risks/?sort=title&dir=asc")
            assert r.status_code == 200
            body = r.get_data(as_text=True)
            # ascending: Alpha before Mid before Zebra
            assert body.index("Alpha risk") < body.index("Mid risk") < body.index("Zebra risk")
    finally:
        with app.app_context():
            _cleanup_ids(db, Risk, ids)
            _cleanup_ids(db, User, [uid])
            _cleanup_ids(db, Organization, [org])


def test_unrecognised_sort_key_falls_back_safely(client, app):
    from app import db
    from app.models.organization import Organization
    from app.models.risk import Risk
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "RiskSort2")
        uid = _make_user_id(db, org, "RiskSortUser2", enterprise_role="enterprise_architect")
    ids = _make_risks(app, org)
    try:
        with app.app_context():
            _login(client, uid)
            r = client.get("/risks/?sort='; DROP TABLE risks;--&dir=asc")
            assert r.status_code == 200  # never 500s on a bad/malicious key
    finally:
        with app.app_context():
            _cleanup_ids(db, Risk, ids)
            _cleanup_ids(db, User, [uid])
            _cleanup_ids(db, Organization, [org])
