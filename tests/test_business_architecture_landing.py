"""Tests for the Business Architecture practice landing page (BA-A3).

Three things must hold, and the third is the one that matters most:

1. The page renders for a business architect.
2. Every endpoint it can link to actually resolves — a ``url_for`` to a
   missing endpoint raises ``BuildError``, and because this repo registers
   blueprints non-fatally that would 500 *every* page rendering the sidebar.
3. It appears in the business architect's sidebar, which is the whole point:
   the twelve outputs existed and were unreachable.

Uses the shared fixtures in tests/conftest.py (``db_session`` rolls the whole
test back), not the hand-rolled module-scoped pattern in the older modules.
"""

from __future__ import annotations

import uuid

import pytest
from werkzeug.routing import BuildError

from app.models.user import ROLE_BUSINESS_ARCHITECT
from app.modules.business_architecture.routes import BA_OUTPUTS, iter_endpoints

LANDING_ENDPOINT = "business_architecture.index"


@pytest.fixture
def ba_user(db_session, make_org):
    """A confirmed business_architect in a fresh org."""
    from app.models.user import User

    org = make_org("ba")
    suffix = uuid.uuid4().hex[:10]
    user = User(
        email=f"ba-{suffix}@example.test",
        first_name="Bea",
        last_name="Archer",
        confirmed=True,
        organization_id=org.id,
        enterprise_role=ROLE_BUSINESS_ARCHITECT,
    )
    user.password = "test-password-not-secret"
    db_session.add(user)
    db_session.flush()
    return user


def test_landing_route_is_registered(app):
    """The blueprint is registered — 23 unregistered blueprints were deleted
    from this repo the day before this page was written."""
    assert LANDING_ENDPOINT in app.view_functions


def test_every_linked_endpoint_resolves(app):
    """The single biggest risk in this page: a BuildError here would 500 every
    page that renders the sidebar.

    Asserted twice over — present in ``view_functions`` *and* buildable by
    ``url_for``, since an endpoint can exist while requiring URL arguments the
    template does not pass.
    """
    missing = []
    unbuildable = []
    with app.test_request_context("/"):
        from flask import url_for

        for endpoint in iter_endpoints():
            if endpoint not in app.view_functions:
                missing.append(endpoint)
                continue
            try:
                url_for(endpoint)
            except BuildError:
                unbuildable.append(endpoint)

    assert not missing, f"endpoints named by the landing page do not exist: {missing}"
    assert not unbuildable, f"endpoints exist but need URL arguments: {unbuildable}"


def test_all_twelve_outputs_are_present():
    """The evaluating architect listed twelve outputs; the page owes him all
    twelve, including any it has no home for."""
    numbers = sorted(
        output["number"] for group in BA_OUTPUTS for output in group["outputs"]
    )
    assert numbers == list(range(1, 13))


def test_each_output_states_a_question_not_a_screen():
    for group in BA_OUTPUTS:
        for output in group["outputs"]:
            question = output["question"]
            assert question.endswith("?"), f"{output['title']} does not ask a question"
            assert output["action"], f"{output['title']} has no call to action"


def test_page_renders_for_a_business_architect(app, ba_user, login_as):
    client = app.test_client()
    login_as(client, ba_user)
    resp = client.get("/business-architecture/")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Business Architecture" in body
    # A representative output from each of the three groups.
    assert "Capability maps" in body
    assert "Capability maturity" in body
    assert "Gap analysis &amp; roadmaps" in body


def test_rendered_page_links_to_every_available_output(app, ba_user, login_as):
    """The template guards each link on view_functions; with every endpoint
    present, every guard must have opened."""
    client = app.test_client()
    login_as(client, ba_user)
    body = client.get("/business-architecture/").get_data(as_text=True)

    with app.test_request_context("/"):
        from flask import url_for

        for endpoint in iter_endpoints():
            url = url_for(endpoint)
            assert f'href="{url}"' in body, f"{endpoint} ({url}) is not linked on the page"


def test_page_claims_no_statistics(app, ba_user, login_as):
    """``fabricated-data`` is at 0. This page computes nothing, so a card must
    never render a "Not yet available" state while an endpoint exists, nor
    show a count of anything."""
    client = app.test_client()
    login_as(client, ba_user)
    body = client.get("/business-architecture/").get_data(as_text=True)

    assert "Not yet available" not in body, (
        "every output currently has a real home; a 'Not yet available' badge "
        "here means an endpoint stopped resolving"
    )


def test_landing_page_is_in_the_business_architect_sidebar():
    from app.utils.role_access import SIDEBAR_ZONES

    endpoints = [
        link["endpoint"]
        for zone in SIDEBAR_ZONES[ROLE_BUSINESS_ARCHITECT]
        for link in zone["links"]
    ]
    assert LANDING_ENDPOINT in endpoints


def test_landing_page_is_in_the_platform_admin_sidebar():
    """platform_admin is the default enterprise_role for every user who never
    picked one (see the column comment in app/models/user.py), so this is the
    role that decides whether most real accounts can find the page at all."""
    from app.models.user import ROLE_PLATFORM_ADMIN
    from app.utils.role_access import SIDEBAR_ZONES

    endpoints = [
        link["endpoint"]
        for zone in SIDEBAR_ZONES[ROLE_PLATFORM_ADMIN]
        for link in zone["links"]
    ]
    assert LANDING_ENDPOINT in endpoints


def test_no_role_exceeds_the_sidebar_link_budget():
    """The link budget is a hard constraint on this change: enterprise_architect
    was already at the sidebar_links ratchet's ceiling, which is why it does not
    get the landing-page link."""
    from app.utils.role_access import SIDEBAR_LINK_BUDGET, SIDEBAR_ZONES

    for role, zones in SIDEBAR_ZONES.items():
        total = sum(len(zone["links"]) for zone in zones)
        assert total <= SIDEBAR_LINK_BUDGET, (
            f"{role} now has {total} sidebar links, over the budget of "
            f"{SIDEBAR_LINK_BUDGET}"
        )
