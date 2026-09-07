"""E2E-2: the "Solution design" journey completed but produced nothing
governed -- driving all five stages ended with 0 decisions, the final
"Journey ready to close" button firing a 200 with no terminal
Completed/Closed state, and no handover artifact.

Two real gaps closed here:
1. PATCH .../state had no route accepting a status transition at all, so a
   journey could never be marked done -- it now accepts {status:
   'completed'}, restricted to that one transition and only once the
   journey has actually reached its deliver stage.
2. The Decide stage had guidance text but no control to record a decision
   -- the workspace template now links to the real, working Decision
   Register create route when currentStage === 'decide' (verified live).
"""
import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def _make_journey(app, db, org_id, owner_id, stage="frame"):
    from app.models.architecture_journey import ArchitectureJourney

    journey = ArchitectureJourney(
        owner_id=owner_id,
        organization_id=org_id,
        title="Close test %s" % uuid.uuid4().hex[:8],
        intent="architecture_assessment",
        selected_layers=["business"],
        selected_deliverables=[],
        outcome_type="undecided",
        evidence_manifest=[],
        journey_state={},
        current_stage=stage,
    )
    db.session.add(journey)
    db.session.commit()
    return journey.id


def test_a_journey_not_yet_at_deliver_cannot_be_closed(app, client):
    from app import db

    with app.app_context():
        org_id = make_org(db, "CloseEarly")
        owner_id = make_user(
            db, org_id, "closeearly", enterprise_role="enterprise_architect",
            role_name="Architect",
        )
        journey_id = _make_journey(app, db, org_id, owner_id, stage="frame")

    login(client, owner_id)
    response = client.patch(
        "/architecture-journey/work/%d/state" % journey_id,
        json={"status": "completed"},
    )
    assert response.status_code == 400, (
        "a journey still on its first stage was allowed to close: %s"
        % response.get_data(as_text=True)[:300]
    )


def test_a_journey_at_deliver_can_be_closed_and_it_sticks(app, client):
    from app import db
    from app.models.architecture_journey import ArchitectureJourney

    with app.app_context():
        org_id = make_org(db, "CloseReady")
        owner_id = make_user(
            db, org_id, "closeready", enterprise_role="enterprise_architect",
            role_name="Architect",
        )
        journey_id = _make_journey(app, db, org_id, owner_id, stage="deliver")

    login(client, owner_id)
    response = client.patch(
        "/architecture-journey/work/%d/state" % journey_id,
        json={"status": "completed"},
    )
    assert response.status_code == 200, response.get_data(as_text=True)[:500]

    with app.app_context():
        db.session.expunge_all()
        row = db.session.get(ArchitectureJourney, journey_id)
        assert row.status == "completed", "the close did not persist"


def test_an_unsupported_status_value_is_refused(app, client):
    from app import db

    with app.app_context():
        org_id = make_org(db, "CloseBad")
        owner_id = make_user(
            db, org_id, "closebad", enterprise_role="enterprise_architect",
            role_name="Architect",
        )
        journey_id = _make_journey(app, db, org_id, owner_id, stage="deliver")

    login(client, owner_id)
    response = client.patch(
        "/architecture-journey/work/%d/state" % journey_id,
        json={"status": "archived"},
    )
    assert response.status_code == 400, (
        "the close route accepted a status other than 'completed': %s"
        % response.get_data(as_text=True)[:300]
    )


def test_the_decide_stage_offers_a_real_control_to_record_a_decision():
    with open(
        "app/templates/architecture_assistant/architecture_journey_workspace.html",
        encoding="utf-8",
    ) as fh:
        html = fh.read()
    assert 'data-testid="journey-decide-cta"' in html
    assert "arch_decisions.create_decision" in html
