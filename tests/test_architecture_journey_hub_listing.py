"""The hub's journey list: find, filter and page through your own work.

The hub showed at most eight active journeys as cards, with no count, no filter, no
sort and no pagination. Two consequences, both silent:

- A user with nine journeys saw eight and was told nothing about the ninth. There
  was no total, so the list looked complete when it was not. A truncated list that
  does not admit to being truncated is a lie of omission on a screen whose whole job
  is "resume your work".
- The query filtered `status="active"`, so a completed or archived journey vanished
  with no way to reach it. Nothing in the product ever set a non-active status, so
  the filter was invisible in practice -- until the day something does.

These follow the Applications list's established patterns: state lives in the URL,
the server is the source of truth, and a filtered empty result is distinguishable
from a genuinely empty one.
"""

from __future__ import annotations

import uuid

import pytest



# NOTE ON THE QUERY PARAMETER NAME
#
# The list filter is `intent_filter`, not `intent`. `?intent=` is already spoken
# for: /business-architecture/ redirects to
# /architecture-journey/?intent=business-transformation to PRESELECT the start
# form's purpose, and a test pins that 301 exactly. Reusing `intent` for the list
# filter would have made arriving from Business Architecture silently filter the
# resume list to one purpose as well -- two meanings for one parameter, and the
# second one invisible.


@pytest.fixture
def hub_user(db_session, make_org):
    from app.models.user import User

    org = make_org("journey-hub")
    user = User(
        email=f"hub-{uuid.uuid4().hex[:10]}@example.test",
        first_name="Hub",
        last_name="User",
        confirmed=True,
        organization_id=org.id,
        enterprise_role="business_architect",
    )
    user.password = "test-password-not-secret"
    db_session.add(user)
    db_session.flush()
    return user


def _seed(db_session, owner, count, *, intent="operating_model", stage="frame", status="active"):
    from app.models.architecture_journey import ArchitectureJourney

    made = []
    for index in range(count):
        row = ArchitectureJourney(
            owner_id=owner.id,
            organization_id=owner.organization_id,
            title=f"{intent}-{stage}-{index}",
            intent=intent,
            selected_layers=["business"],
            current_stage=stage,
            status=status,
        )
        db_session.add(row)
        made.append(row)
    db_session.flush()
    db_session.commit()
    return made


def _get(app, login_as, user, query=""):
    client = app.test_client()
    login_as(client, user)
    response = client.get(f"/architecture-journey/{query}")
    assert response.status_code == 200, response.get_data(as_text=True)[:400]
    return response.get_data(as_text=True)


def test_hub_states_how_many_journeys_exist(app, db_session, hub_user, login_as):
    """A truncated list must admit to being truncated."""
    _seed(db_session, hub_user, 11)
    html = _get(app, login_as, hub_user)

    assert 'data-testid="journey-total"' in html
    assert "11" in html, "the hub must say how many journeys exist, not just show a page of them"


def test_hub_paginates_and_the_second_page_differs(app, db_session, hub_user, login_as):
    _seed(db_session, hub_user, 11)

    first = _get(app, login_as, hub_user)
    second = _get(app, login_as, hub_user, "?page=2")

    assert 'data-testid="journey-pagination"' in first
    assert first != second, "page 2 rendered the same journeys as page 1"


def test_hub_filters_by_intent(app, db_session, hub_user, login_as):
    _seed(db_session, hub_user, 2, intent="operating_model")
    _seed(db_session, hub_user, 3, intent="risk_and_compliance")

    html = _get(app, login_as, hub_user, "?intent_filter=risk_and_compliance")

    assert "risk_and_compliance-frame-0" in html
    assert "operating_model-frame-0" not in html


def test_hub_filters_by_stage(app, db_session, hub_user, login_as):
    _seed(db_session, hub_user, 2, stage="frame")
    _seed(db_session, hub_user, 2, stage="decide")

    html = _get(app, login_as, hub_user, "?stage=decide")

    assert "operating_model-decide-0" in html
    assert "operating_model-frame-0" not in html


def test_a_filtered_empty_result_is_not_the_same_as_having_no_journeys(
    app, db_session, hub_user, login_as
):
    """The two empty states say different things and offer different next steps.

    Telling a user with nine journeys that they have none, because their filter
    matched nothing, sends them off to create a tenth.
    """
    _seed(db_session, hub_user, 3, intent="operating_model")

    filtered = _get(app, login_as, hub_user, "?intent_filter=portfolio_change")
    assert 'data-testid="journey-empty-filtered"' in filtered
    assert 'data-testid="journey-empty-none"' not in filtered

    genuinely_empty_user_html = filtered
    assert "clear" in genuinely_empty_user_html.lower(), (
        "a filtered empty state must offer a way back to the unfiltered list"
    )


def test_hub_shows_a_true_empty_state_when_there_are_no_journeys(
    app, db_session, hub_user, login_as
):
    html = _get(app, login_as, hub_user)

    assert 'data-testid="journey-empty-none"' in html
    assert 'data-testid="journey-empty-filtered"' not in html


def test_an_unknown_filter_value_is_refused_rather_than_silently_ignored(
    app, db_session, hub_user, login_as
):
    """Ignoring it would show the full list under a filter chip that lies."""
    _seed(db_session, hub_user, 2)

    client = app.test_client()
    login_as(client, hub_user)
    response = client.get("/architecture-journey/?intent_filter=not_a_real_intent")

    assert response.status_code == 400


def test_completed_journeys_are_reachable(app, db_session, hub_user, login_as):
    """They were invisible with no route to them at all."""
    _seed(db_session, hub_user, 2, status="completed", stage="deliver")

    active_only = _get(app, login_as, hub_user)
    assert "operating_model-deliver-0" not in active_only

    completed = _get(app, login_as, hub_user, "?status=completed")
    assert "operating_model-deliver-0" in completed
