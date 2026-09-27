"""Journey: can the portfolio_manager persona record a disposition?

Level 9, docs/TESTING_STANDARD.md. The persona is the TIME/7R rationalization
steward: given a scored application, decide what happens to it -- retain,
replatform, retire -- and have that decision stick and show up on the
application's planning page.

Writing this journey found the action unreachable. POST
/applications/rationalization/api/bulk-review implemented a "set_disposition"
branch, but "set_disposition" was missing from the endpoint's valid_actions set,
so every request for the persona's core action was rejected with 400 before
reaching it. The branch also set review_status="approved" unconditionally, which
would have let a portfolio manager retire an application with no ARB decision --
through RAT-112, the governance rule the model itself declares.
"""

import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey

BULK = "/applications/rationalization/api/bulk-review"


def _scored_application(db, org_id, name):
    """An application carrying a rationalization score, ready to be dispositioned."""
    from app.models.application_portfolio import ApplicationComponent
    from app.models.application_rationalization import ApplicationRationalizationScore

    component = ApplicationComponent(name=name, organization_id=org_id)
    db.session.add(component)
    db.session.flush()

    score = ApplicationRationalizationScore(
        application_component_id=component.id,
        organization_id=org_id,
        review_status="reviewed",
        # Both NOT NULL with no server default; omitting either fails at flush.
        overall_health_score=62.0,
        rationalization_action="TOLERATE",
    )
    db.session.add(score)
    db.session.commit()
    return component.id


def _score_for(db, app_id):
    from app.models.application_rationalization import ApplicationRationalizationScore

    db.session.expunge_all()
    return db.session.execute(
        db.select(ApplicationRationalizationScore).filter_by(
            application_component_id=app_id
        )
    ).scalar_one()


def test_portfolio_manager_records_a_disposition_and_sees_it(app, client):
    """An ungoverned disposition is recorded, approved and visible."""
    from app import db

    with app.app_context():
        org_id = make_org(db, "PM")
        pm_id = make_user(db, org_id, "pm", enterprise_role="portfolio_manager",
                          role_name="Architect")
        name = "Journey App %s" % uuid.uuid4().hex[:8]
        app_id = _scored_application(db, org_id, name)

    login(client, pm_id)
    response = client.post(
        BULK,
        json={
            "app_ids": [app_id],
            "action": "set_disposition",
            "disposition": "replatform",
            "notes": "Moving to the managed PaaS in FY27.",
        },
    )
    assert response.status_code == 200, response.data[:400]
    assert response.get_json()["summary"]["processed"] == 1

    # PERSISTED
    with app.app_context():
        score = _score_for(db, app_id)
        assert score.disposition_action == "replatform"
        assert score.disposition_confidence == "manual"
        assert score.review_status == "approved"
        assert "Moving to the managed PaaS in FY27." in (score.review_notes or "")

    # VISIBLE on the planning page for that application.
    page = client.get("/applications/rationalization/planning/%d" % app_id)
    assert page.status_code == 200, page.status_code
    assert "replatform" in page.get_data(as_text=True).lower()


def test_a_governed_disposition_is_not_approved_without_arb(app, client):
    """RAT-112: retire/replace/consolidate need an ARB decision first."""
    from app import db

    with app.app_context():
        org_id = make_org(db, "PMGov")
        pm_id = make_user(db, org_id, "pmgov", enterprise_role="portfolio_manager",
                          role_name="Architect")
        app_id = _scored_application(db, org_id, "Governed App %s" % uuid.uuid4().hex[:8])

    login(client, pm_id)
    response = client.post(
        BULK,
        json={
            "app_ids": [app_id],
            "action": "set_disposition",
            "disposition": "retire",
            "notes": "End of life.",
        },
    )
    assert response.status_code == 200, response.data[:400]

    with app.app_context():
        score = _score_for(db, app_id)
        # The disposition IS recorded -- the steward's judgement is not lost.
        assert score.disposition_action == "retire"
        # But it is NOT approved, and it is flagged for the board.
        assert score.review_status != "approved"
        assert score.arb_required is True
        assert score.approved_at is None


def test_bulk_approve_cannot_bypass_arb_on_a_governed_disposition(app, client):
    """The other route to "approved" is gated by the same rule."""
    from app import db

    with app.app_context():
        org_id = make_org(db, "PMBulk")
        pm_id = make_user(db, org_id, "pmbulk", enterprise_role="portfolio_manager",
                          role_name="Architect")
        app_id = _scored_application(db, org_id, "Bulk App %s" % uuid.uuid4().hex[:8])
        score = _score_for(db, app_id)
        score.disposition_action = "retire"
        db.session.commit()

    login(client, pm_id)
    response = client.post(
        BULK,
        json={"app_ids": [app_id], "action": "approve", "notes": "Sign off."},
    )
    assert response.status_code == 200, response.data[:400]
    payload = response.get_json()
    assert payload["summary"]["processed"] == 0
    assert payload["summary"]["skipped"] == 1
    assert "ARB" in payload["results"]["skipped"][0]["reason"]

    with app.app_context():
        assert _score_for(db, app_id).review_status != "approved"


def test_an_unknown_disposition_is_rejected(app, client):
    """A free-text disposition would poison the 7R taxonomy silently."""
    from app import db

    with app.app_context():
        org_id = make_org(db, "PMBad")
        pm_id = make_user(db, org_id, "pmbad", enterprise_role="portfolio_manager",
                          role_name="Architect")
        app_id = _scored_application(db, org_id, "Bad App %s" % uuid.uuid4().hex[:8])

    login(client, pm_id)
    response = client.post(
        BULK,
        json={"app_ids": [app_id], "action": "set_disposition", "disposition": "sunset"},
    )
    assert response.status_code == 400

    with app.app_context():
        assert _score_for(db, app_id).disposition_action is None
