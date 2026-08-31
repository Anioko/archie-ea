"""The capability search must return capabilities, not an apology.

The owner opened /capability-maturity/search and got a working-looking page
carrying "This page could not load its data ... Error searching capabilities.
Please try again."

Three defects in one handler, all caused by hand-written SQL:

1. It selected `capability_type`, which does not exist on business_capability.
   Postgres raised UndefinedColumn, the bare `except` flashed the error and
   rendered an empty page -- with HTTP 200. That status is why it survived an
   audit of 21,978 page loads: every gate in the estate reads status codes or
   source, and a page that says "I am broken" with a 200 is invisible to both.
2. Every statement carried a `# tenant-filtered` comment and none of them was.
   Raw SQL never reaches do_orm_execute, so the search read across every
   organisation in the database. The comment asserted the opposite of the truth.
3. The count was produced by str.replace() against a SELECT list that had since
   gained two columns. The replacement silently matched nothing, so the "total"
   was whatever scalar() happened to pull off the first row.

The handler is now ORM-based, which fixes all three mechanically rather than by
patching a string: TenantMixin applies the org predicate, and the mapper
validates the column list.

These tests pin the outcome a user cares about -- the page finds the capability
they typed -- plus the tenant boundary, because that defect was invisible from
the screen.
"""

import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey

SEARCH = "/capability-maturity/search"


def _make_capability(db, org_id, name, domain="Operations", importance="high"):
    from app.models.business_capabilities import BusinessCapability

    capability = BusinessCapability(
        organization_id=org_id,
        name=name,
        description="Seeded by the capability search journey.",
        business_domain=domain,
        strategic_importance=importance,
        current_maturity_level=2,
        target_maturity_level=4,
    )
    db.session.add(capability)
    db.session.commit()
    return capability.id


def test_the_search_finds_a_capability_and_shows_no_error(app, client):
    """The defect exactly as the owner hit it."""
    from app import db

    with app.app_context():
        org_id = make_org(db, "CapSearch")
        analyst_id = make_user(
            db, org_id, "capsearch", enterprise_role="business_architect",
            role_name="Architect",
        )
        name = "Order Fulfilment %s" % uuid.uuid4().hex[:8]
        _make_capability(db, org_id, name)

    login(client, analyst_id)
    response = client.get(SEARCH, query_string={"q": name[:14]})
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    # The page must not apologise. This is the assertion that was missing.
    assert "could not load its data" not in body, "the search still reports a load failure"
    assert "Error searching capabilities" not in body, body[:400]

    # And it must actually find the row, not merely render without complaint.
    assert name in body, "the capability the user searched for is not on the page"


def test_the_search_does_not_read_another_organisations_capabilities(app, client):
    """The raw SQL claimed to be tenant-filtered and was not."""
    from app import db

    with app.app_context():
        org_a = make_org(db, "CapTenantA")
        org_b = make_org(db, "CapTenantB")
        user_a = make_user(
            db, org_a, "captenanta", enterprise_role="business_architect",
            role_name="Architect",
        )
        shared_token = uuid.uuid4().hex[:8]
        mine = "Mine %s" % shared_token
        theirs = "Theirs %s" % shared_token
        _make_capability(db, org_a, mine)
        _make_capability(db, org_b, theirs)

    login(client, user_a)
    response = client.get(SEARCH, query_string={"q": shared_token})
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert mine in body, "the user cannot see their own capability"
    assert theirs not in body, (
        "another organisation's capability is visible in the search results"
    )


def test_an_empty_search_is_an_empty_state_not_an_error(app, client):
    """A search with no matches is the product working, and must read that way."""
    from app import db

    with app.app_context():
        org_id = make_org(db, "CapEmpty")
        analyst_id = make_user(
            db, org_id, "capempty", enterprise_role="business_architect",
            role_name="Architect",
        )

    login(client, analyst_id)
    response = client.get(SEARCH, query_string={"q": "no-such-capability-" + uuid.uuid4().hex})
    assert response.status_code == 200
    body = response.get_data(as_text=True)

    assert "could not load its data" not in body
    assert "Error searching capabilities" not in body
