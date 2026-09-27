"""Journey: can the enterprise_architect persona model a capability?

Level 9, docs/TESTING_STANDARD.md. The persona exists to build and maintain the
capability model, so the journey is: create a capability, confirm it persisted,
and confirm it is visible on the surface the architect looks at next.

The user carries role_name="Architect", not "Administrator". An admin session
normalises to the "admin" role and would satisfy every require_roles guard on
the way through, hiding exactly the authorisation defect this level exists to
find (TESTING_STANDARD rule 4).
"""

import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def _create(client, name):
    return client.post(
        "/enterprise/capabilities",
        json={
            "name": name,
            "type": "operational",
            "description": "Created by the enterprise architect journey.",
            "level": 1,
        },
    )


def test_enterprise_architect_creates_a_capability_and_sees_it(app, client):
    """The persona's core write: a capability that persists and is visible."""
    from app import db
    from app.models.business_capabilities import BusinessCapability

    with app.app_context():
        org_id = make_org(db, "EA")
        ea_id = make_user(
            db, org_id, "ea", enterprise_role="enterprise_architect",
            role_name="Architect",
        )

    login(client, ea_id)
    name = "Journey Capability %s" % uuid.uuid4().hex[:8]

    response = _create(client, name)
    assert response.status_code == 201, response.data[:400]

    # PERSISTED. Read the database, not the response body the route just built.
    with app.app_context():
        db.session.expunge_all()
        row = db.session.execute(
            db.select(BusinessCapability).filter_by(name=name)
        ).scalar_one_or_none()
        assert row is not None
        # A capability with no organization_id is a capability every tenant can
        # see. TenantMixin sets it on flush; assert it actually happened.
        assert row.organization_id == org_id

    # VISIBLE. GET /enterprise/capabilities is the list the capability screens
    # fetch to render, so it is literally what the architect sees next.
    page = client.get("/enterprise/capabilities")
    assert page.status_code == 200, page.status_code
    assert name in page.get_data(as_text=True)


def test_a_capability_created_in_one_org_is_invisible_to_another(app, client):
    """Two tenants must not see each other's capability model."""
    from app import db

    with app.app_context():
        org_a = make_org(db, "EAOrgA")
        org_b = make_org(db, "EAOrgB")
        ea_a = make_user(db, org_a, "eaA", enterprise_role="enterprise_architect",
                         role_name="Architect")
        ea_b = make_user(db, org_b, "eaB", enterprise_role="enterprise_architect",
                         role_name="Architect")

    name = "Tenant Scoped Capability %s" % uuid.uuid4().hex[:8]

    login(client, ea_a)
    assert _create(client, name).status_code == 201

    client_b = app.test_client()
    login(client_b, ea_b)
    page = client_b.get("/enterprise/capabilities")
    assert page.status_code == 200
    assert name not in page.get_data(as_text=True)
