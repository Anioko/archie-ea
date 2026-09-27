"""User-visible outcomes for governance controls backed by real workflows."""

from __future__ import annotations

from datetime import datetime
import uuid

import pytest


pytestmark = pytest.mark.usefixtures("db_session")


def _user(db_session, org):
    from app.models.user import User

    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"governance-controls-{suffix}@example.com",
        first_name="Governance",
        last_name="User",
        organization_id=org.id,
        enterprise_role="enterprise_architect",
        confirmed=True,
    )
    user.password = "Sup3rSecret!123"
    db_session.add(user)
    db_session.flush()
    return user


def test_governance_shortcuts_send_users_to_the_real_workflows(
    db_session, make_org, client, login_as
):
    """A shortcut must take the user to the canonical workflow, not a stub page."""
    org = make_org("governance-controls")
    user = _user(db_session, org)
    login_as(client, user)

    for shortcut, destination in (
        ("/governance/adr-list", "/architecture/decisions/"),
        ("/governance/arb-reviews", "/arb/reviews"),
        ("/governance/risk-register", "/risks/"),
    ):
        response = client.get(shortcut, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith(destination)


def test_arb_decision_titles_open_the_canonical_decision_detail(
    db_session, make_org, client, login_as
):
    """A decision title in the register must open that decision's persisted detail."""
    from app.models.architecture_decision import ArchitectureDecision

    org = make_org("arb-decision-link")
    user = _user(db_session, org)
    decision = ArchitectureDecision(
        decision_id=f"AD-{uuid.uuid4().hex[:8]}",
        title="Move payments to the shared platform",
        organization_id=org.id,
    )
    db_session.add(decision)
    db_session.flush()

    login_as(client, user)
    response = client.get("/arb/decisions")

    assert response.status_code == 200
    assert (
        f'href="/architecture/decisions/{decision.id}"'
        in response.get_data(as_text=True)
    )


def test_governance_dashboard_offers_only_a_real_review_destination(
    db_session, make_org, client, login_as
):
    """Recent-review View opens its solution; an unavailable standard editor is not a button."""
    from app.models.solution_governance import SolutionARBReview
    from app.models.solution_models import Solution

    org = make_org("governance-dashboard")
    user = _user(db_session, org)
    solution = Solution(name="Payments modernisation", organization_id=org.id)
    db_session.add(solution)
    db_session.flush()
    db_session.add(
        SolutionARBReview(
            solution_id=solution.id,
            organization_id=org.id,
            submitted_at=datetime.utcnow(),
        )
    )
    db_session.flush()

    login_as(client, user)
    dashboard = client.get("/governance/dashboard")
    assert dashboard.status_code == 200
    body = dashboard.get_data(as_text=True)
    assert ':href="review.solution_url"' in body
    assert "Editing unavailable" in body
    assert ">Edit</button>" not in body

    reviews = client.get("/governance/api/reviews/recent")
    assert reviews.status_code == 200
    payload = reviews.get_json()
    assert payload[0]["solution_url"] == f"/solutions/{solution.id}"
