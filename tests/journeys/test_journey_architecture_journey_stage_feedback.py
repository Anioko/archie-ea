"""E2E-1: "Complete this stage" advanced server-side but the UI never
updated, so a user got no feedback, clicked again, and both clicks landed --
silently skipping a stage (verified live, stages 1->2->3->4->5).

Root cause: the workspace template rendered "Stage X of Y" and the progress
stepper from server-side Jinja (home.stage.index/label/stages), while the
button's own advance() already updated Alpine's reactive currentStage/
stageIndex correctly -- the visible text just never read from it. This is
the same class of defect as the Risk Register's window.RISK_ROWS bug this
session: correct server data, correct client logic, but the template never
wired them together, so nothing red shows up anywhere except a live click.

A server-rendered-HTML test cannot observe client-side reactivity (the
rendered markup is identical either way -- only runtime behaviour differs),
so this asserts what a unit/journey test CAN prove: the PATCH endpoint
really persists the stage server-side, one stage at a time, and the
template no longer contains the dead home.stage.index/label markup that a
future edit could reintroduce. The actual client-side re-render was
verified live via Playwright against production.
"""
import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def test_the_workspace_template_reads_stage_from_reactive_state_not_stale_server_text():
    with open(
        "app/templates/architecture_assistant/architecture_journey_workspace.html",
        encoding="utf-8",
    ) as fh:
        html = fh.read()
    assert "home.stage.index" not in html, (
        "the stage progress text is back to reading a value that only "
        "changes on a full page reload -- see E2E-1"
    )
    assert 'x-text="stageLabel"' in html
    assert "stageIndex + 1" in html


def test_advancing_a_stage_persists_one_stage_at_a_time(app, client):
    """The PATCH itself must move exactly one stage, not silently coalesce
    two rapid calls into a multi-stage jump (the second half of E2E-1's
    reported symptom -- 'both clicks had advanced it, skipping Discover')."""
    from app import db
    from app.models.architecture_journey import ArchitectureJourney

    with app.app_context():
        org_id = make_org(db, "JourneyStage")
        owner_id = make_user(
            db, org_id, "journeystage", enterprise_role="enterprise_architect",
            role_name="Architect",
        )
        journey = ArchitectureJourney(
            owner_id=owner_id,
            organization_id=org_id,
            title="Stage feedback test %s" % uuid.uuid4().hex[:8],
            intent="architecture_assessment",
            selected_layers=["business"],
            selected_deliverables=[],
            outcome_type="undecided",
            evidence_manifest=[],
            journey_state={},
        )
        db.session.add(journey)
        db.session.commit()
        journey_id = journey.id

    login(client, owner_id)

    response = client.patch(
        "/architecture-journey/work/%d/state" % journey_id,
        json={"current_stage": "discover"},
    )
    assert response.status_code == 200, response.get_data(as_text=True)[:500]

    with app.app_context():
        db.session.expunge_all()
        row = db.session.get(ArchitectureJourney, journey_id)
        assert row.current_stage == "discover", (
            "one PATCH call must land on exactly the requested stage, "
            f"got {row.current_stage!r}"
        )
