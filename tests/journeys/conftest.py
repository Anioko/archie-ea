"""Shared harness for persona journey tests.

pytest.ini has declared this gate since before the open-source release:

    journey: End-to-end journey tests - one per user persona, CI-enforced gate

No such test existed, in the working tree or anywhere in git history. These are
the first. They exist because a static reading of this codebase cannot tell you
whether an archetype can do its job: on 2026-07-30 static analysis found 43
endpoints that were present in source and raised TypeError on every call.

A journey asserts an archetype can complete the work it exists to do, end to
end, over real HTTP - not that a route is registered.
"""

import uuid

import pytest


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


def make_org(db, label):
    """A real Organization row.

    slug is NOT NULL and has no default, so it must be supplied explicitly -
    omitting it raises NotNullViolation on commit rather than at construction.
    """
    from app.models.organization import Organization

    suffix = uuid.uuid4().hex[:8]
    org = Organization(
        name="%s Org %s" % (label, suffix),
        slug="%s-org-%s" % (label.lower().replace(" ", "-"), suffix),
    )
    db.session.add(org)
    db.session.flush()
    db.session.commit()
    return org.id


def make_user(db, org_id, label, enterprise_role, role_name="Administrator"):
    """A user pinned to *org_id* and carrying *enterprise_role*.

    enterprise_role is the field ENTERPRISE_ROLE_SECTION_MAP keys on, so it is
    what actually determines the archetype's navigation.

    organization_id is set explicitly: User has a before_insert listener that
    reassigns an unset organization_id to the shared default org, which would
    silently break any tenancy assertion in a journey.

    role_name attaches a Role, because the test app only runs db.create_all()
    and never Role.insert_roles() - so users otherwise have no role at all and
    every @require_roles route returns 403 before the journey reaches anything
    worth asserting.
    """
    from app.models.user import Role, User

    suffix = uuid.uuid4().hex[:8]
    user = User(
        email="%s-%s@example.com" % (label.lower(), suffix),
        first_name=label,
        last_name="Journey",
        organization_id=org_id,
        confirmed=True,
        enterprise_role=enterprise_role,
    )
    db.session.add(user)
    db.session.flush()

    if role_name:
        role = Role.query.filter_by(name=role_name).first()
        if role is None:
            role = Role(name=role_name)
            db.session.add(role)
            db.session.flush()
        user.role = role

    db.session.commit()
    return user.id


def login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def cleanup(db, model, ids):
    for i in ids:
        if i is None:
            continue
        try:
            obj = db.session.get(model, i)
            if obj is not None:
                db.session.delete(obj)
                db.session.commit()
        except Exception:
            db.session.rollback()


def reachable(client, path):
    """True when a path resolves to something the app serves.

    404 means the route is not registered at all. A redirect is reachable -
    Flask emits 308 for a missing trailing slash and 302 for auth flows, and
    neither means the capability is absent.
    """
    resp = client.get(path, follow_redirects=False)
    return resp.status_code != 404, resp.status_code
