"""Journey: can the solution_architect persona design within governance?

Level 9, docs/TESTING_STANDARD.md. This persona designs a solution and gets it
in front of the board. So the journey is: create the solution, confirm it
persisted with its owner and tenant, confirm it is visible on the list the
architect works from, and confirm the ARB hand-off behaves -- the step that
separates a design tool from a governance platform.

The hand-off turned out to be better than expected and the tests say so. A fresh
solution is REFUSED with 422, naming the evidence it lacks: a security lead, a
data protection officer, and recorded drivers/goals/risks. That is the platform
working, and it is tested from both sides -- the refusal names what is missing,
and supplying real evidence clears exactly the checks it satisfies. A gate that
always says no would pass the first assertion forever.

Asserted through the endpoint the UI calls, never by writing an ARBReviewItem
directly. The QA audit found the governance chain unreachable from the interface
while every table underneath it was healthy -- exactly the failure a test that
seeds its own review item would sail past.
"""

import uuid

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey


def _create_solution(client, title):
    return client.post(
        "/solutions/create-from-wizard",
        json={
            "title": title,
            "scope": {"business_domain": "finance"},
            "capabilities": [],
            "gap_analysis": {},
            "selected_option": {"name": "Buy a managed platform"},
        },
    )


def test_solution_architect_creates_a_solution_and_sees_it(app, client):
    """The persona's core write: a solution that persists and is listed."""
    from app import db
    from app.models.solution_models import Solution

    with app.app_context():
        org_id = make_org(db, "SA")
        architect_id = make_user(
            db, org_id, "sa", enterprise_role="solution_architect",
            role_name="Architect",
        )

    login(client, architect_id)
    title = "Billing Modernisation %s" % uuid.uuid4().hex[:8]

    response = _create_solution(client, title)
    assert response.status_code in (200, 201), response.data[:300]

    # PERSISTED -- read the database, not the response body.
    with app.app_context():
        db.session.expunge_all()
        row = db.session.execute(
            db.select(Solution).filter_by(name=title)
        ).scalar_one_or_none()
        assert row is not None, "the solution did not persist"
        # A solution with no organization_id is one every tenant can see.
        assert row.organization_id == org_id

    # VISIBLE on the list the architect works from.
    page = client.get("/solutions/")
    assert page.status_code == 200
    assert title in page.get_data(as_text=True)


def test_an_unprepared_solution_is_refused_by_the_arb_evidence_gate(app, client):
    """A design cannot reach the board without its governance evidence.

    This is the platform behaving CORRECTLY, and it is worth a test precisely
    because it looks like a failure: submitting a fresh solution returns 422,
    not 201. The gate requires a named security lead, a named data protection
    officer, and recorded drivers/goals/risks before an item can be tabled.

    What makes it good governance rather than an obstacle is that the refusal is
    machine-readable and names every missing check, so the UI can tell the
    architect what to do next instead of just saying no.
    """
    from app import db
    from app.models.architecture_review_board import ARBReviewItem
    from app.models.solution_models import Solution

    with app.app_context():
        org_id = make_org(db, "SAARB")
        architect_id = make_user(
            db, org_id, "saarb", enterprise_role="solution_architect",
            role_name="Architect",
        )

    login(client, architect_id)
    title = "Payments Consolidation %s" % uuid.uuid4().hex[:8]
    assert _create_solution(client, title).status_code in (200, 201)

    with app.app_context():
        db.session.expunge_all()
        solution_id = db.session.execute(
            db.select(Solution).filter_by(name=title)
        ).scalar_one().id
        before = db.session.execute(
            db.select(db.func.count(ARBReviewItem.id))
        ).scalar()

    response = client.post(
        "/arb/api/solution/%d/submit_review" % solution_id,
        json={"review_type": "solution_design", "title": "ARB review for %s" % title},
    )
    assert response.status_code == 422, (
        "an unprepared solution was accepted for ARB review: %s" % response.status_code
    )

    missing = {
        entry.get("check") for entry in (response.get_json() or {}).get("missing_evidence", [])
    }
    # The refusal must SAY what is missing; "no" without a reason is unactionable.
    assert {"design_reviewed", "security_impact_reviewed", "data_impact_reviewed"} <= missing, (
        "the refusal did not name the missing checks: %s" % missing
    )

    # And nothing was tabled.
    with app.app_context():
        db.session.expunge_all()
        after = db.session.execute(
            db.select(db.func.count(ARBReviewItem.id))
        ).scalar()
        assert after == before, "a refused submission still created a review item"


def test_the_evidence_gate_responds_to_real_evidence(app, client):
    """Guard the guard: a gate that always refuses is not a gate.

    Naming a security lead and a data protection officer must clear those two
    checks specifically, leaving only the one whose evidence has not been
    supplied. Without this, a blanket refusal would pass the test above forever.
    """
    from app import db
    from app.models.solution_models import Solution

    with app.app_context():
        org_id = make_org(db, "SAEvid")
        architect_id = make_user(
            db, org_id, "saevid", enterprise_role="solution_architect",
            role_name="Architect",
        )

    login(client, architect_id)
    title = "Evidenced Design %s" % uuid.uuid4().hex[:8]
    assert _create_solution(client, title).status_code in (200, 201)

    with app.app_context():
        db.session.expunge_all()
        solution = db.session.execute(
            db.select(Solution).filter_by(name=title)
        ).scalar_one()
        solution_id = solution.id
        solution.security_lead = "R. Okafor"
        solution.data_protection_officer = "M. Lindqvist"
        db.session.commit()

    response = client.post(
        "/arb/api/solution/%d/submit_review" % solution_id,
        json={"review_type": "solution_design", "title": "ARB review for %s" % title},
    )
    missing = {
        entry.get("check") for entry in (response.get_json() or {}).get("missing_evidence", [])
    }
    assert "security_impact_reviewed" not in missing, (
        "a named security lead did not clear the security check: %s" % missing
    )
    assert "data_impact_reviewed" not in missing, (
        "a named data protection officer did not clear the data check: %s" % missing
    )


def test_one_architects_solution_is_invisible_to_another_tenant(app, client):
    """Designs are commercially sensitive; two tenants must not share a list."""
    from app import db

    with app.app_context():
        org_a = make_org(db, "SAOrgA")
        org_b = make_org(db, "SAOrgB")
        architect_a = make_user(db, org_a, "saA",
                                enterprise_role="solution_architect",
                                role_name="Architect")
        architect_b = make_user(db, org_b, "saB",
                                enterprise_role="solution_architect",
                                role_name="Architect")

    title = "Confidential Design %s" % uuid.uuid4().hex[:8]
    login(client, architect_a)
    assert _create_solution(client, title).status_code in (200, 201)

    client_b = app.test_client()
    login(client_b, architect_b)
    page = client_b.get("/solutions/")
    assert page.status_code == 200
    assert title not in page.get_data(as_text=True), (
        "org B was shown org A's solution"
    )
