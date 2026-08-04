"""Who can reach what: the access matrix, observed rather than assumed.

291 routes carry an explicit role gate. This drives every archetype against the
persona-exclusive sections and asserts the result matches an expectation derived
from the decorators themselves:

    requires_procurement        -> procurement, portfolio_manager  (+ platform_admin)
    requires_application_owner  -> application_manager             (+ platform_admin)
    admin_required              -> platform_admin

platform_admin passes every gate by design - requires_role() grants it
unconditionally - so it is expected to reach all of them.

Why observe instead of reading the decorators: a decorator only tells you what
was intended. It does not tell you whether the blueprint is registered, whether
another route shadows the path, or whether the gate runs before the handler
touches data. Earlier in this codebase a decorator scan reported 1,590 unguarded
mutating routes when the real number was 1, and separately reported an
unauthenticated /api/gdpr/delete that turned out never to be registered. Only
driving it settles either question.
"""

import pytest

from .conftest import ARCHETYPES, PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

ALLOWED = "allowed"
DENIED = "denied"

# path -> the archetypes that should reach it, from the decorator definitions.
# platform_admin is added to every row because requires_role() grants it always.
POLICY = {
    "/procurement/contracts":  {"procurement", "portfolio_manager"},
    "/procurement/licenses":   {"procurement", "portfolio_manager"},
    "/procurement/compliance": {"procurement", "portfolio_manager"},
    "/my-applications/":       {"application_manager"},
    "/my-applications/list":   {"application_manager"},
    "/my-applications/health": {"application_manager"},
}
for _allowed in POLICY.values():
    _allowed.add("platform_admin")


def _login(page, base, email, _attempts=2):
    """Sign in, retrying once, and say which failure actually happened.

    This used to swallow the wait_for_url timeout with `except Exception: pass`
    and then assert on page.url, so a navigation that simply had not finished
    reported as "could not sign in as ...". That made one archetype fail
    intermittently in a full smoke run — and a DIFFERENT archetype each time,
    which is the signature of a timing race rather than a credentials or
    authorisation problem. In isolation the file passed 11/11 every time.

    The app has no login rate limiting or account lockout, so a slow response
    under the load of a full browser suite was the only remaining explanation.
    Retrying once absorbs that; distinguishing the two causes means the next
    person does not have to rediscover which one they are looking at.
    """
    for attempt in range(1, _attempts + 1):
        page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.fill("#email", email)
        page.fill("#password", PASSWORD)
        try:
            page.click("#submit", force=True, no_wait_after=True)
        except TypeError:
            page.locator("#submit").dispatch_event("click")

        timed_out = False
        try:
            page.wait_for_url(lambda u: "/account/login" not in u, timeout=PAGE_TIMEOUT)
        except Exception:
            timed_out = True

        if "/account/login" not in page.url:
            return
        # Still on the login page. An actual rejection renders a flash; a timing
        # failure does not. Only the latter is worth retrying.
        rejected = page.locator(".alert-danger, .flash-error, [role=alert]").count() > 0
        if rejected:
            raise AssertionError(
                f"sign-in REJECTED for {email} — the page rendered an error, so this is "
                f"a credentials or account-state problem, not a timing one"
            )
        if attempt == _attempts:
            raise AssertionError(
                f"sign-in for {email} never navigated away from /account/login after "
                f"{_attempts} attempts (wait_for_url timed out: {timed_out}). No error "
                f"was rendered, so the form was accepted but the response did not "
                f"arrive within {PAGE_TIMEOUT}ms."
            )


def _observe(page, base, path):
    """ALLOWED or DENIED, from what the server actually did."""
    response = page.goto(base + path, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    status = response.status if response else 0
    # A redirect back to login means the session was lost, not that the gate
    # refused - that would be a false DENIED and would hide a real leak.
    assert "/account/login" not in page.url, "session lost while probing %s" % path
    return ALLOWED if status < 400 else DENIED


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.set_default_timeout(PAGE_TIMEOUT)
    ctx.set_default_navigation_timeout(PAGE_TIMEOUT)
    pg = ctx.new_page()
    yield pg
    ctx.close()


@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_archetype_reaches_exactly_what_policy_permits(archetype, page, live_server, seeded):
    """One row of the matrix per archetype.

    Both directions matter. A DENIED that should be ALLOWED is a persona that
    cannot do its job - that is how Procurement and Application Manager shipped
    read-only. An ALLOWED that should be DENIED is a tenant or role boundary
    failure.
    """
    _login(page, live_server, seeded["emails"][archetype])

    wrong = []
    for path, permitted in sorted(POLICY.items()):
        expected = ALLOWED if archetype in permitted else DENIED
        actual = _observe(page, live_server, path)
        if actual != expected:
            wrong.append("%s: expected %s, got %s" % (path, expected, actual))

    assert not wrong, (
        "%s has the wrong access:\n  - %s\n\n"
        "An unexpected ALLOWED is a broken role boundary. An unexpected DENIED is "
        "a persona that cannot do its job." % (archetype, "\n  - ".join(wrong)))


def test_platform_admin_passes_every_gate(page, live_server, seeded):
    """requires_role() grants platform_admin unconditionally - hold it to that."""
    _login(page, live_server, seeded["emails"]["platform_admin"])
    denied = [p for p in sorted(POLICY) if _observe(page, live_server, p) == DENIED]
    assert not denied, (
        "platform_admin was refused %s. requires_role() is documented as always "
        "granting platform_admin; either the code or the documentation is wrong."
        % denied)


def test_no_archetype_reaches_another_personas_section_unauthenticated(page, live_server):
    """The gates must not be the only thing standing between anonymous and data."""
    leaked = []
    for path in sorted(POLICY):
        response = page.goto(live_server + path, wait_until="domcontentloaded",
                             timeout=PAGE_TIMEOUT)
        # Anonymous must be redirected to login or refused - never served.
        served = response and response.status < 400 and "/account/login" not in page.url
        if served:
            leaked.append(path)
    assert not leaked, "these are reachable without signing in at all: %s" % leaked
