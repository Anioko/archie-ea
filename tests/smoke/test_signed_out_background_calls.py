"""A session that goes stale while a signed-in tab sits open and polling --
idle timeout or a server-side revocation (logout elsewhere, a forced password
reset) -- must send the user back to sign in the moment the page's own next
background call comes back 401, not leave it polling a session that will
never return, or blank its own fields forever.

Reproduces the exact server-side condition a real revocation leaves behind
(``session_registry.revoke_all_for_user``, the same function the real logout
and password-change paths already call) against a live, already-rendered
page, then waits for or triggers that page's own next background call and
asserts the browser is sent to the sign-in page with a ``next=`` parameter.

Covers two of the three background-call shapes: a 5-second poll
(``/admin/jira-settings``) and a 30-second poll triggered directly through
its own Alpine component method rather than waiting out the real interval
(``/batch-import/``). Both fail on an unpatched fetch wrapper: the page's own
background call still comes back 401, but nothing sends the browser to sign
in, so ``page.url`` never changes and the wait below times out.

There is no JS unit-test harness in this repository (``package.json``'s
``test`` script is ``playwright test``, i.e. this same browser layer) -- this
smoke test is the only coverage for the fetch wrapper's redirect behaviour.
"""

import pytest

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _revoke_session(email):
    """Revoke every active session for the user at *email* -- the same
    real-world event as signing out elsewhere or a forced password reset,
    while this tab stays open."""
    from app import create_app, db
    from app.models.user import User
    from app.services import session_registry

    app = create_app("testing")
    with app.app_context():
        user = User.query.filter_by(email=email).one()
        session_registry.revoke_all_for_user(user.id, "smoke-test-revocation")
        db.session.remove()


def test_jira_settings_poll_sends_revoked_session_to_sign_in(browser, live_server, seeded):
    """/admin/jira-settings polls its push-status endpoint every 5 seconds
    (jira_settings.html). Once the session behind an open tab is revoked,
    the next poll must redirect the browser to sign-in instead of leaving
    the fields blank forever."""
    page = browser.new_page()
    try:
        email = seeded["emails"]["platform_admin"]
        _login(page, live_server, email)
        response = page.goto(
            live_server + "/admin/jira-settings",
            wait_until="domcontentloaded", timeout=PAGE_TIMEOUT,
        )
        assert response is not None and response.status == 200

        _revoke_session(email)

        # The page's own poller fires every 5s; give it up to three ticks
        # so one slow tick cannot flake this.
        page.wait_for_url(lambda url: "/account/login" in url, timeout=17000)
        assert "next=" in page.url, (
            "redirected to sign-in with no next= to return to: %s" % page.url
        )
    finally:
        page.close()


def test_batch_import_poll_sends_revoked_session_to_sign_in(browser, live_server, seeded):
    """/batch-import/'s dashboard polls /api/batch-import/jobs every 30
    seconds through its own Alpine component's loadJobs() (dashboard.js).
    Once the session is revoked, the next poll must redirect to sign-in
    rather than leaving the table stuck behind a generic error toast.

    Triggers the real component method directly instead of waiting out the
    30-second interval -- this calls the exact same Platform.fetch the real
    timer would, it just does not wait for the clock."""
    page = browser.new_page()
    try:
        email = seeded["emails"]["application_manager"]
        _login(page, live_server, email)
        response = page.goto(
            live_server + "/batch-import/",
            wait_until="domcontentloaded", timeout=PAGE_TIMEOUT,
        )
        assert response is not None and response.status == 200
        page.wait_for_selector('[x-data="batchImportDashboard()"]')

        _revoke_session(email)

        # Do not await the call's own promise here: a correctly-patched
        # fetch wrapper returns one that never resolves once it starts the
        # redirect, and page.evaluate() waits for whatever it is handed back.
        page.evaluate(
            "() => { window.Alpine.$data("
            "document.querySelector('[x-data=\"batchImportDashboard()\"]')"
            ").loadJobs(true); return true; }"
        )

        page.wait_for_url(lambda url: "/account/login" in url, timeout=15000)
        assert "next=" in page.url, (
            "redirected to sign-in with no next= to return to: %s" % page.url
        )
    finally:
        page.close()
