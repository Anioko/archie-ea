"""A route given an id that does not exist must answer 404, not 200.

Why this file exists
--------------------
An adversarial sweep of every int-argument GET route found 78 answering 200 for
id ``999999999``, six of them rendering a full HTML page. The worst two:

* ``/solutions/999999999/completeness`` rendered "Completeness Report ·
  Solution 999999999" showing **0 / 100 — Incomplete**. A solution that does not
  exist was given a governance completeness score.
* ``/vendors/applications-portfolio/999999999`` synthesised a placeholder object
  named ``Vendor #999999999`` and reported "Total Applications: 0".

That is the CLAUDE.md "never invent data" rule verbatim: a ``0`` meaning "no such
thing" is indistinguishable from a measured ``0``, and the user acts on it. The
guards live in ``app/utils/route_guards.py``.

These tests hit the routes through the test client, so they measure the HTTP
answer rather than re-reading the fix.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.usefixtures("db_session")

# An id no fixture will ever allocate.
MISSING_ID = 999999999


def _make_admin(db_session, make_org):
    """A confirmed platform-admin user in a fresh org.

    ``is_platform_admin`` / ``is_org_admin`` are real Boolean columns.
    ``is_admin`` is a METHOD on ``User`` — assigning to it shadows the method and
    breaks every template that calls ``current_user.is_admin()``, so never do
    that here.
    """
    from app.models.user import User

    org = make_org("notfound")
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"notfound-{suffix}@example.com",
        first_name="Not",
        last_name="Found",
        organization_id=org.id,
        confirmed=True,
        enterprise_role="platform_admin",
    )
    user.password = "Sup3rSecret!23"
    user.is_platform_admin = True
    user.is_org_admin = True
    db_session.add(user)
    db_session.flush()
    return user, org


# Every HTML page that used to render for a nonexistent id.
HTML_ROUTES = [
    f"/solutions/{MISSING_ID}/completeness",
    f"/solutions/{MISSING_ID}/communications",
    f"/architecture-assistant/solution/{MISSING_ID}",
    f"/vendors/applications-portfolio/{MISSING_ID}",
    f"/vendors/technical/analytics/{MISSING_ID}",
    f"/dashboard/vendor-analysis/{MISSING_ID}",
]


@pytest.mark.parametrize("url", HTML_ROUTES)
def test_html_page_404s_for_nonexistent_id(app, db_session, make_org, client, login_as, url):
    user, _org = _make_admin(db_session, make_org)
    login_as(client, user)

    response = client.get(url)

    assert response.status_code == 404, (
        f"{url} answered {response.status_code}; a page for an id that does not "
        f"exist must 404, not render a report about it. "
        f"{response.get_data(as_text=True)[:400]}"
    )


@pytest.mark.parametrize("url", HTML_ROUTES)
def test_html_page_does_not_name_the_missing_id(
    app, db_session, make_org, client, login_as, url
):
    """The 404 body must not present the missing id as if it were a record.

    The original failure was not only the status code: the page put
    ``Solution 999999999`` in the title and ``Vendor #999999999`` in the
    breadcrumb, which reads as a real entity. Asserting the id is absent from
    any rendered heading keeps a future "friendly" error page from
    reintroducing the same fabrication.
    """
    user, _org = _make_admin(db_session, make_org)
    login_as(client, user)

    body = client.get(url).get_data(as_text=True)

    for fabricated in (f"Vendor #{MISSING_ID}", f"Solution {MISSING_ID}"):
        assert fabricated not in body, f"{url} still names a nonexistent entity: {fabricated}"


# JSON endpoints that used to answer 200 with an empty or zeroed payload.
# Paths containing "/api/" are converted to a JSON body by the app-wide
# HTTPException handler in app/_bootstrap/extensions.py; the rest return their
# own JSON 404.
JSON_ROUTES = [
    f"/api/solutions/{MISSING_ID}/completeness",
    f"/api/solutions/{MISSING_ID}/issues",
    f"/dashboard/api/vendor-analysis/{MISSING_ID}/export-history",
]


@pytest.mark.parametrize("url", JSON_ROUTES)
def test_json_endpoint_404s_for_nonexistent_id(
    app, db_session, make_org, client, login_as, url
):
    user, _org = _make_admin(db_session, make_org)
    login_as(client, user)

    response = client.get(url)

    assert response.status_code == 404, (
        f"{url} answered {response.status_code}; an empty payload for a parent "
        f"that does not exist is indistinguishable from a real parent with no "
        f"children. {response.get_data(as_text=True)[:400]}"
    )


def test_completeness_page_404s_rather_than_scoring_a_nonexistent_solution(
    app, db_session, make_org, client, login_as
):
    """The specific regression: a governance score for a solution that is not there."""
    user, _org = _make_admin(db_session, make_org)
    login_as(client, user)

    response = client.get(f"/solutions/{MISSING_ID}/completeness")
    body = response.get_data(as_text=True)

    assert response.status_code == 404
    assert "0 / 100" not in body
    assert "Incomplete" not in body


def test_guard_does_not_leak_across_tenants(app, db_session, make_org, client, login_as):
    """A solution belonging to another org must read as absent, not as forbidden.

    ``require_entity`` emits a real SELECT precisely so the tenant loader
    criteria apply — ``Query.get()`` would have returned the row from the
    identity map without one. 404 is the correct answer for a foreign row, and
    it is the same answer the caller got before this change, so the fix cannot
    have widened the route.
    """
    from app.models.solution_models import Solution

    owner, other_org = _make_admin(db_session, make_org)
    solution = Solution(name=f"Foreign {uuid.uuid4().hex[:8]}")
    solution.organization_id = other_org.id
    db_session.add(solution)
    db_session.flush()

    intruder, _intruder_org = _make_admin(db_session, make_org)
    assert intruder.organization_id != owner.organization_id
    login_as(client, intruder)

    response = client.get(f"/solutions/{solution.id}/completeness")

    assert response.status_code == 404, (
        "another organisation's solution must be invisible, not merely refused"
    )
