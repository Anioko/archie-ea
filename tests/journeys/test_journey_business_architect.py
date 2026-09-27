"""Journey: can the business_architect persona assess and model the business?

Level 9, docs/TESTING_STANDARD.md. This persona connects strategy to the
capability model, so its two real writes are: record a capability's maturity
(current vs target), and model a value stream. Both must persist AND be visible
where the architect looks next.

Written because the suite it joins is 2,478 tests of which only 18% assert an
outcome at all, and half never construct a request. A capability whose maturity
assessment silently fails to save returns 200 to every one of them.

The maturity write matters twice over: capability health scores are derived from
current vs target, and a capability with neither is now correctly reported as
"Not assessed" rather than scored. So this journey also proves the input side of
that honesty fix.
"""

import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def _capability(db, org_id, name, **kwargs):
    from app.models.business_capabilities import BusinessCapability

    capability = BusinessCapability(name=name, organization_id=org_id, **kwargs)
    db.session.add(capability)
    db.session.commit()
    return capability.id


def test_business_architect_records_a_maturity_assessment(app, client):
    """The persona's core write: a maturity gap that persists and is scored."""
    from app import db
    from app.models.business_capabilities import BusinessCapability

    with app.app_context():
        org_id = make_org(db, "BA")
        architect_id = make_user(
            db, org_id, "ba", enterprise_role="business_architect",
            role_name="Architect",
        )
        name = "Customer Onboarding %s" % uuid.uuid4().hex[:8]
        capability_id = _capability(db, org_id, name)

    login(client, architect_id)

    response = client.post(
        "/capability-maturity/edit/%d" % capability_id,
        data={
            "current_maturity_level": "2",
            "target_maturity_level": "4",
            "assessment_notes": "Manual handoffs between sales and delivery.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200, response.status_code

    # PERSISTED -- read the database, not the response the route just rendered.
    with app.app_context():
        db.session.expunge_all()
        row = db.session.execute(
            db.select(BusinessCapability).filter_by(id=capability_id)
        ).scalar_one()
        assert row.current_maturity_level == 2
        assert row.target_maturity_level == 4

    # VISIBLE -- and now SCORED, where before the assessment it was withheld.
    with app.app_context():
        from flask import g

        from app.modules.capabilities.services.capability_health_service import (
            CapabilityHealthService,
        )

        g.current_org_id = org_id
        metrics = CapabilityHealthService().get_capability_health_metrics()
        item = next(
            h for h in metrics["health_by_capability"] if h["name"] == name
        )
        assert item["score"] is not None, (
            "an assessed capability must be scored; None means the assessment "
            "did not reach the health calculation"
        )
        assert item["status"] != "Not assessed"


def test_a_maturity_level_outside_one_to_five_is_refused(app, client):
    """The scale is 1-5. A 9 would score as a gap the model cannot represent."""
    from app import db
    from app.models.business_capabilities import BusinessCapability

    with app.app_context():
        org_id = make_org(db, "BABad")
        architect_id = make_user(
            db, org_id, "babad", enterprise_role="business_architect",
            role_name="Architect",
        )
        capability_id = _capability(db, org_id, "Out Of Range %s" % uuid.uuid4().hex[:8])

    login(client, architect_id)
    client.post(
        "/capability-maturity/edit/%d" % capability_id,
        data={"current_maturity_level": "9", "target_maturity_level": "4"},
        follow_redirects=True,
    )

    with app.app_context():
        db.session.expunge_all()
        row = db.session.execute(
            db.select(BusinessCapability).filter_by(id=capability_id)
        ).scalar_one()
        assert row.current_maturity_level != 9, (
            "a maturity level of 9 was stored on a 1-5 scale"
        )


def test_business_architect_models_a_value_stream_and_sees_it(app, client):
    """The other half of the persona's job: the value stream itself."""
    from app import db
    from app.models.unified_capability import ValueStream

    with app.app_context():
        org_id = make_org(db, "BAVS")
        architect_id = make_user(
            db, org_id, "bavs", enterprise_role="business_architect",
            role_name="Architect",
        )

    login(client, architect_id)
    name = "Order to Cash %s" % uuid.uuid4().hex[:8]

    response = client.post(
        "/value-streams/create",
        data={
            "name": name,
            "description": "From order capture to cash collection.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200, response.status_code

    with app.app_context():
        db.session.expunge_all()
        row = db.session.execute(
            db.select(ValueStream).filter_by(name=name)
        ).scalar_one_or_none()
        assert row is not None, "the value stream did not persist"
        # A value stream with no organization_id is one every tenant can see.
        assert row.organization_id == org_id

    page = client.get("/value-streams/")
    assert page.status_code == 200
    assert name in page.get_data(as_text=True)
