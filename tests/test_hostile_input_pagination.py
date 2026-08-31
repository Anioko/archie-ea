"""Hostile query-string input must produce an honest answer, never a 500.

An adversarial sweep found ~55 endpoints that returned HTTP 500 on trivially
malformed pagination: ``?limit=-1`` reached PostgreSQL as a negative OFFSET
(``psycopg2.errors.InvalidRowCountInResultOffsetClause``), and ``?limit=abc`` /
``?limit=`` hit a bare ``int(request.args.get(...))`` and raised ``ValueError``.
One of them, ``/architecture/search``, is a user-facing page, so paging back
from page 1 handed the user a raw server error.

The fix is a single helper, ``app.utils.pagination.safe_int_arg``, applied at
every call site: unparseable input falls back to the site's own default, and
the result is clamped into range before it can reach a query. These tests pin
both halves - the helper's contract directly, and a sample of real endpoints
across different blueprints end-to-end.

Note what is asserted: **not 5xx**. A hostile value may legitimately produce a
200 with an empty page, a 400, a 403 or a 404 depending on the endpoint and the
fixture data. What it must never produce is a server error, and a page beyond
the end of the result set must be an empty 200 rather than a 500 or a 404.
"""

from __future__ import annotations

import pytest

from app.utils.pagination import MAX_PAGE_SIZE, safe_int_arg

# ---------------------------------------------------------------------------
# The helper's contract
# ---------------------------------------------------------------------------

HOSTILE_VALUES = [
    "-1",
    "0",
    "abc",
    "",
    "   ",
    "1e9",
    "99999999999999999999",
    "-99999999999999999999",
    "NaN",
    "null",
    "1; DROP TABLE users",
    "٣",  # Arabic-Indic digit three - int() accepts it, bounds still apply
]


@pytest.mark.parametrize("raw", HOSTILE_VALUES)
def test_safe_int_arg_page_is_always_at_least_one(raw):
    """``page`` must never reach a query as <= 0 - that is the negative OFFSET."""
    value = safe_int_arg("page", 1, minimum=1, args={"page": raw})
    assert isinstance(value, int)
    assert value >= 1


@pytest.mark.parametrize("raw", HOSTILE_VALUES)
def test_safe_int_arg_per_page_is_bounded(raw):
    """``limit``/``per_page`` must land inside [1, MAX_PAGE_SIZE]."""
    value = safe_int_arg("limit", 20, minimum=1, maximum=MAX_PAGE_SIZE, args={"limit": raw})
    assert isinstance(value, int)
    assert 1 <= value <= MAX_PAGE_SIZE


@pytest.mark.parametrize("raw", HOSTILE_VALUES)
def test_safe_int_arg_offset_is_never_negative(raw):
    value = safe_int_arg("offset", 0, minimum=0, args={"offset": raw})
    assert isinstance(value, int)
    assert value >= 0


def test_safe_int_arg_missing_parameter_uses_the_default():
    assert safe_int_arg("page", 7, minimum=1, args={}) == 7


def test_safe_int_arg_valid_value_passes_through_unchanged():
    assert safe_int_arg("page", 1, minimum=1, args={"page": "42"}) == 42
    assert (
        safe_int_arg("limit", 20, minimum=1, maximum=MAX_PAGE_SIZE, args={"limit": "50"})
        == 50
    )


def test_safe_int_arg_preserves_a_none_default():
    """A call site whose default is None means "unset"; do not invent a number."""
    assert safe_int_arg("limit", None, minimum=1, args={}) is None


def test_safe_int_arg_never_raises_on_a_broken_source():
    class Exploding:
        def get(self, name):
            raise RuntimeError("boom")

    assert safe_int_arg("page", 1, minimum=1, args=Exploding()) == 1


# ---------------------------------------------------------------------------
# Real endpoints, end to end
# ---------------------------------------------------------------------------

# One entry per blueprint we can reach without fixture data. Every one of the
# first four returned 500 before the fix (captured against a clean checkout at
# dd0e8d8f); the rest are the same code shape in other blueprints.
HOSTILE_URLS = [
    "/api/enterprise/applications?limit=-1",
    "/api/enterprise/applications?limit=abc",
    "/api/enterprise/applications?limit=",
    "/api/enterprise/applications?page=-1",
    "/api/enterprise/entities?limit=-1",
    "/api/enterprise/initiatives?limit=-1",
    "/api/enterprise/projects?page=-5",
    "/api/enterprise/systems?limit=abc",
    "/api/acm/capabilities?page=-1",
    "/api/archimate/elements?page=-1",
    "/architecture/search?page=-1&q=test",
    "/usage-analytics/api/events?page=-1",
    "/api/v2/enterprise/kg/elements?limit=-1",
    "/capability-map/api/archimate/relationship-suggestions?limit=-1",
    "/dashboard/api/capability-heatmap?limit=-1",
    "/api/enterprise/applications?limit=99999999999999999999",
    "/api/enterprise/applications?page=0&limit=0",
]


@pytest.fixture
def hostile_client(app, db_session, make_org, login_as):
    """A logged-in client that re-establishes identity before every request.

    ``login_as`` is mandatory here, not decoration: ``db_session`` holds one app
    context open for the whole test, so flask_login caches the resolved user on
    ``g._login_user`` and a cookie written by hand is simply ignored. Without it
    every request below runs anonymous and 401s - which would still satisfy a
    "not 5xx" assertion and quietly make these tests prove nothing.
    """
    from app.models.user import User

    org = make_org("hostile")
    user = User(
        email=f"hostile-{org.id}@example.com",
        first_name="Hostile",
        last_name="Probe",
        organization_id=org.id,
        # Unconfirmed users are bounced to the login page with a 302, which
        # would make every assertion below vacuous.
        confirmed=True,
    )
    if hasattr(user, "enterprise_role"):
        user.enterprise_role = "enterprise_architect"
    db_session.add(user)
    db_session.flush()

    raw = app.test_client()

    class _Client:
        def get(self, url, **kwargs):
            login_as(raw, user)
            return raw.get(url, **kwargs)

        def post(self, url, **kwargs):
            login_as(raw, user)
            return raw.post(url, **kwargs)

    return _Client()


@pytest.mark.parametrize("url", HOSTILE_URLS)
def test_hostile_pagination_never_500s(hostile_client, url):
    """No malformed paging value may reach the database as a bad OFFSET/LIMIT."""
    response = hostile_client.get(url)
    assert response.status_code != 401, (
        f"{url} answered 401 - the request never reached the paging code, so "
        f"this assertion would prove nothing"
    )
    assert response.status_code < 500, (
        f"{url} returned {response.status_code}; hostile input must produce an "
        f"honest error, not a server error"
    )


def test_page_beyond_the_end_is_an_empty_200(hostile_client):
    """Past the last page is an empty page, not a 500 and not a 404."""
    response = hostile_client.get("/api/enterprise/applications?page=999999&limit=25")
    assert response.status_code == 200


def test_user_facing_search_page_survives_page_zero(hostile_client):
    """/architecture/search is a rendered page - a raw 500 is user-visible."""
    response = hostile_client.get("/architecture/search?q=test&page=-1")
    assert response.status_code < 500
