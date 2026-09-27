"""E2E-3: the "Solution blueprint" deliverable showed "Tool unavailable"
unconditionally -- the output the journey was asked to produce could never
be produced.

Root cause: "solution_blueprint" was a real, selectable deliverable
(JOURNEY_DELIVERABLE_OPTIONS) with a real, working page behind it
(solution_design.view_solution, "Blueprint page ships ON by default") --
it was simply never added to DELIVERABLE_TOOL_ENDPOINTS at all, so
_available_deliverable_tools() never even looked for it.

It needs a solution_id, unlike the other deliverable tools here (plain
index pages), which an ArchitectureJourney only has once one is actually
linked (see E2E-2's ArchitectureJourney/Solution split) -- so the fix
reports the tool as available exactly when the journey has a solution to
show a blueprint for, and correctly still reports it unavailable
otherwise (a journey with no linked solution genuinely has no blueprint
to show; that message is honest for that case, not a defect).
"""
import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def test_solution_blueprint_tool_is_offered_once_a_solution_is_linked(app, client):
    from app import db
    from app.models.architecture_journey import ArchitectureJourney
    from app.models.solution_models import Solution

    with app.app_context():
        org_id = make_org(db, "BlueprintTool")
        owner_id = make_user(
            db, org_id, "blueprinttool", enterprise_role="enterprise_architect",
            role_name="Architect",
        )
        solution = Solution(name="Blueprint test solution", organization_id=org_id)
        db.session.add(solution)
        db.session.flush()
        journey = ArchitectureJourney(
            owner_id=owner_id,
            organization_id=org_id,
            title="Blueprint tool test %s" % uuid.uuid4().hex[:8],
            intent="architecture_assessment",
            selected_layers=["business"],
            selected_deliverables=["solution_blueprint"],
            outcome_type="solution",
            evidence_manifest=[],
            journey_state={},
            solution_id=solution.id,
        )
        db.session.add(journey)
        db.session.commit()
        journey_id = journey.id
        solution_id = solution.id

    login(client, owner_id)
    response = client.get("/architecture-journey/work/%d" % journey_id)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Tool unavailable" not in body, (
        "the Solution blueprint deliverable still reports unavailable even "
        "though this journey has a linked solution"
    )
    assert "/solutions/%d" % solution_id in body


def test_solution_blueprint_tool_is_honestly_unavailable_with_no_linked_solution(app, client):
    from app import db
    from app.models.architecture_journey import ArchitectureJourney

    with app.app_context():
        org_id = make_org(db, "BlueprintNoSol")
        owner_id = make_user(
            db, org_id, "blueprintnosol", enterprise_role="enterprise_architect",
            role_name="Architect",
        )
        journey = ArchitectureJourney(
            owner_id=owner_id,
            organization_id=org_id,
            title="No-solution blueprint test %s" % uuid.uuid4().hex[:8],
            intent="architecture_assessment",
            selected_layers=["business"],
            selected_deliverables=["solution_blueprint"],
            outcome_type="undecided",
            evidence_manifest=[],
            journey_state={},
        )
        db.session.add(journey)
        db.session.commit()
        journey_id = journey.id

    login(client, owner_id)
    response = client.get("/architecture-journey/work/%d" % journey_id)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Tool unavailable" in body, (
        "a journey with no linked solution has no blueprint to show -- "
        "reporting it unavailable here is honest, not a regression"
    )
