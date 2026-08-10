"""Regression tests for the shared ORM bug that 500'd six ADM phase APIs.

WHAT WAS BROKEN
----------------
``WorkflowArchiMateContextService.get_phase_elements`` (used by every
``/api/ea*/phase-*/viewpoint`` endpoint) filtered on ``ArchiMateElement.plateau
== phase_code``. On the real (non-fast-init) model,
``app.models.models.ArchiMateElement.plateau`` is a *relationship* backref
created by ``Plateau.archimate_element`` (see
``app/models/implementation_migration.py``), not the TOGAF plateau string
column — that column was deliberately mapped to the Python attribute
``togaf_plateau`` to dodge exactly this name collision. Comparing the
relationship with ``==`` raised
``InvalidRequestError: Can't compare a collection to an object or collection;
use contains() to test for membership.`` on every call, independent of
whether any rows existed, because the error occurs at filter-construction
time, not from the data.

Separately, ``ArchitectureComplianceMatrixService._get_arb_review_status``
filtered ``ARBReviewItem.query.filter_by(application_id=...)``, but
``arb_review_items`` has no ``application_id`` column at all — a review item
links to a ``Solution`` (``solution_id``), and a ``Solution`` links to
applications via the ``solution_applications`` junction. That raised
``InvalidRequestError: Entity namespace for "arb_review_items" has no
property "application_id"`` whenever at least one ApplicationComponent
existed to trigger the lookup.

This file hits all six previously-broken endpoints as an authenticated user
and asserts none of them return a 5xx.
"""

import uuid

import pytest


@pytest.fixture(scope="module")
def app():
    from app import create_app, db

    application = create_app("testing")
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False

    with application.app_context():
        db.create_all()

    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _make_org_id(db, label):
    from app.models.organization import Organization

    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"{label} Org {suffix}", slug=f"{label.lower()}-org-{suffix}")
    db.session.add(org)
    db.session.flush()
    db.session.commit()
    return org.id


def _make_user_id(db, org_id, label):
    from app.models.user import User

    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"{label.lower()}-{suffix}@example.com",
        first_name=label,
        last_name="Tester",
        organization_id=org_id,
        confirmed=True,
        enterprise_role="procurement",
    )
    db.session.add(user)
    db.session.flush()
    db.session.commit()
    return user.id


def _login(client, user_id):
    """Standard Flask-Login test-client pattern; see tests/test_ba_tenant_and_authz.py::_login
    for why the g-cache clear below is required in this test harness."""
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
def logged_in_client(app, client):
    """A client logged in as a user belonging to an org that owns one
    ApplicationComponent — enough to exercise the (fixed) compliance-matrix
    application lookup, not just the empty-list path."""
    from app import db
    from app.models.application_portfolio import ApplicationComponent

    with app.app_context():
        org_id = _make_org_id(db, "adm-phase")
        user_id = _make_user_id(db, org_id, "adm-phase")

        app_component = ApplicationComponent(
            name=f"ADM Phase Test App {uuid.uuid4().hex[:8]}",
            organization_id=org_id,
        )
        db.session.add(app_component)
        db.session.commit()

    _login(client, user_id)
    return client


ENDPOINTS = [
    "/api/ea-workflows/ba/viewpoint",
    "/api/ea/phase-a/viewpoint",
    "/api/ea/phase-d/viewpoint",
    "/api/ea/phase-f/viewpoint",
    "/api/ea/phase-g/viewpoint",
]


@pytest.mark.parametrize("path", ENDPOINTS)
def test_phase_viewpoint_endpoints_do_not_500(logged_in_client, path):
    """The shared get_phase_elements() helper must not raise InvalidRequestError
    comparing the ArchiMateElement.plateau relationship with `==`."""
    resp = logged_in_client.get(path)
    assert resp.status_code < 500, (
        f"{path} returned {resp.status_code}: {resp.get_data(as_text=True)[:2000]}"
    )


def test_phase_g_compliance_matrix_does_not_500(logged_in_client):
    """ArchitectureComplianceMatrixService must not filter ARBReviewItem by a
    nonexistent application_id column."""
    resp = logged_in_client.get("/api/ea/phase-g/compliance-matrix")
    assert resp.status_code < 500, (
        f"compliance-matrix returned {resp.status_code}: "
        f"{resp.get_data(as_text=True)[:2000]}"
    )
    body = resp.get_json()
    assert "matrix" in body
    # The application seeded in logged_in_client should be scored, and since
    # it has no linked ARB review, its status must be the honest default
    # rather than a fabricated value.
    row = next((r for r in body["matrix"] if r.get("arb_review_status") is not None), None)
    assert row is not None
    assert row["arb_review_status"] == "not_reviewed"
