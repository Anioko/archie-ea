"""Journey: can an architect record and see an enterprise risk?

The QA audit of 30 Aug 2026 recorded /risks/ as "a non-functional stub":

    "DOM inspection shows the 'Add Risk' button is a bare <button type='button'>
     with no onclick, no Alpine x-on directive, and no href -- no event handler
     of any kind is wired up. There is also no risk list/table anywhere on the
     page, only a placeholder line of text. The entire Risk Register feature is
     unusable -- no risks can be created, viewed, filtered, or searched."

Nothing was missing underneath: the Risk model, RiskStatus, the computed
risk_score/risk_level and GET/POST/PATCH /api/risks all existed, and the page's
own route already passed `risks`, `grid` and `total` into the template. Only the
UI was absent, which is precisely the shape a status-code assertion cannot see:
/risks/ returned 200 throughout.

So this asserts the outcome rather than the status -- the risk persists, it is
scored, and it is visible on the page the architect looks at next.
"""

import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def test_an_architect_records_a_risk_and_sees_it_on_the_register(app, client):
    """The persona's write: a risk that persists, scores, and is visible."""
    from app import db
    from app.models.risk import Risk

    with app.app_context():
        org_id = make_org(db, "RiskReg")
        architect_id = make_user(
            db, org_id, "riskea", enterprise_role="enterprise_architect",
            role_name="Architect",
        )

    login(client, architect_id)
    title = "Vendor lock-in on the billing platform %s" % uuid.uuid4().hex[:8]

    response = client.post(
        "/api/risks",
        json={
            "title": title,
            "description": "Single supplier, no exit path modelled.",
            "likelihood": 4,
            "impact": 5,
            "owner": "Platform team",
        },
    )
    assert response.status_code == 201, response.data[:300]

    payload = response.get_json()
    # The score is derived, not stored: likelihood x impact, banded into a level.
    assert payload["risk_score"] == 20
    assert payload["risk_level"] == "critical"

    # PERSISTED -- read the database, not the response the route just built.
    with app.app_context():
        db.session.expunge_all()
        row = db.session.execute(
            db.select(Risk).filter_by(title=title)
        ).scalar_one()
        assert row.likelihood == 4
        assert row.impact == 5
        assert row.owner == "Platform team"
        # A risk with no organization_id is a risk every tenant can see.
        assert row.organization_id == org_id

    # VISIBLE -- on the register itself, which is the whole point: this page
    # returned 200 for its entire life while showing a placeholder paragraph.
    page = client.get("/risks/")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert title in body
    assert "Critical" in body
    # And the control that creates one is actually wired to something.
    assert "openCreate()" in body


def test_the_register_refuses_a_risk_with_no_title(app, client):
    """Title, likelihood and impact are required; the refusal must be explicit."""
    from app import db
    from app.models.risk import Risk

    with app.app_context():
        org_id = make_org(db, "RiskBad")
        architect_id = make_user(
            db, org_id, "riskbad", enterprise_role="enterprise_architect",
            role_name="Architect",
        )

    login(client, architect_id)
    before = None
    with app.app_context():
        before = db.session.execute(db.select(db.func.count(Risk.id))).scalar()

    response = client.post("/api/risks", json={"likelihood": 3, "impact": 3})
    assert response.status_code == 400
    assert "title" in (response.get_json() or {}).get("error", "").lower()

    with app.app_context():
        after = db.session.execute(db.select(db.func.count(Risk.id))).scalar()
        assert after == before, "a refused risk must not be written"
