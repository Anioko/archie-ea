"""F-04 regression: the programme wizard is gated at entry, not after six steps.

The 2 Sep 2026 browser audit found a Solution Architect could complete the whole
six-step "New Programme" wizard and only then be rejected with the raw code
'programme_create_not_authorised'. The create command's CREATE_ROLES check is
correct (programmes are EA/CTO/admin-owned; solution architects deliver within
them) — the defect was UX: authorise at the door too.

Pins: the public can_create_programme() mirrors CREATE_ROLES; the GET entry
redirects a non-creator away with a message; the POST refuses a non-creator with
a human message (JSON 403), never the raw code.
"""

import pytest

from tests.test_ba_tenant_and_authz import (
    _cleanup_ids,
    _login,
    _make_org_id,
    _make_user_id,
)


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


def test_can_create_programme_mirrors_create_roles(app):
    from app.models.user import User
    from app.modules.transformation_room.programme_service import (
        CREATE_ROLES,
        TransformationProgrammeService,
    )

    with app.app_context():
        assert "enterprise_architect" in CREATE_ROLES
        assert "solution_architect" not in CREATE_ROLES
        ea = User(email="ea@example.com", enterprise_role="enterprise_architect")
        sa = User(email="sa@example.com", enterprise_role="solution_architect")
        assert TransformationProgrammeService.can_create_programme(ea) is True
        assert TransformationProgrammeService.can_create_programme(sa) is False


@pytest.fixture
def solution_architect(app):
    from app import db
    from app.models.organization import Organization
    from app.models.user import User

    with app.app_context():
        org = _make_org_id(db, "Wiz")
        uid = _make_user_id(db, org, "SolArch",
                            enterprise_role="solution_architect", role_name="Architect")
        yield uid
        _cleanup_ids(db, User, [uid])
        _cleanup_ids(db, Organization, [org])


def test_non_creator_is_turned_away_at_the_door(client, app, solution_architect):
    from flask import url_for

    with app.app_context():
        _login(client, solution_architect)
        with app.test_request_context():
            entry = url_for("solution_design.new_programme")
            home = url_for("solution_design.list_solutions")
        r = client.get(entry)
        assert r.status_code == 302, "a non-creator must be redirected, not shown the wizard"
        assert r.headers["Location"].endswith(home)


def test_non_creator_post_gets_human_403_not_raw_code(client, app, solution_architect):
    from flask import url_for

    with app.app_context():
        _login(client, solution_architect)
        with app.test_request_context():
            create = url_for("solution_design.create_programme")
        r = client.post(create, json={"name": "X"}, headers={"Idempotency-Key": "k"})
        assert r.status_code == 403
        body = r.get_json()
        assert body["success"] is False
        assert "programme_create_not_authorised" not in body["error"]
        assert "Enterprise Architects" in body["error"]
