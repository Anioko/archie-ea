"""Account settings: change-password is a real write path with no prior coverage.

Login/logout are already exercised implicitly by every persona fixture in
conftest.py's `_login` helper, and account creation/confirmation is a
separate onboarding flow out of scope here. But /account/manage/change-password
is a genuine, previously-untested write: this proves the new password is the
one that actually works by logging out and back in with it, not merely that
the form round-tripped with a flashed message.

This test rotates its subject's password by design (that is the whole point
of the assertion), so it must never run against a persona any other smoke
test relies on: `seeded` is session-scoped, and there is no cleanup step that
could safely restore a password without depending on ordering. Instead this
test creates its own disposable user, following the same
`User(...); user.password = PASSWORD` construction `seeded` uses in
conftest.py, so rotating this user's password can never poison another
test's sign-in.
"""
import uuid

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT, PASSWORD
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _create_disposable_user(organization_id):
    """A user that belongs to no other test - safe to rotate the password of.

    Mirrors tests/smoke/conftest.py's `seeded` per-archetype user creation
    (same app-context/create_app("testing") pattern, same
    `User(...); user.password = PASSWORD` construction) but is never added to
    `seeded['emails']`, so no other test file's `_login` helper can ever be
    handed this user's (about to be rotated) credentials.
    """
    from app import create_app, db
    from app.models.user import Role, User

    app = create_app("testing")
    with app.app_context():
        architect_role = Role.query.filter_by(name="Architect").one()
        suffix = uuid.uuid4().hex[:8]
        email = "smoke.password-change.%s@example.com" % suffix
        user = User(
            email=email, first_name="Smoke", last_name="PasswordChange",
            organization_id=organization_id, enterprise_role="business_architect",
            confirmed=True,
        )
        user.role = architect_role
        user.is_platform_admin = False
        user.is_org_admin = False
        user.password = PASSWORD
        db.session.add(user)
        db.session.commit()
        return email


def test_change_password_and_relogin_with_new_password(browser, live_server, seeded):
    page = browser.new_page()
    new_password = "SmokeJourneyRotated!2026"
    email = _create_disposable_user(seeded['ids']['org'])
    try:
        _login(page, live_server, email)

        response = page.goto(live_server + '/account/manage/change-password', timeout=PAGE_TIMEOUT)
        assert response.status == 200

        page.get_by_label('Old password', exact=True).fill(PASSWORD)
        page.get_by_label('New password', exact=True).fill(new_password)
        page.get_by_label('Confirm new password', exact=True).fill(new_password)
        page.get_by_role('button', name='Update password', exact=True).click()

        # A successful change redirects to main.index with a flashed message;
        # a validation/business-rule failure re-renders the same form.
        page.wait_for_load_state('domcontentloaded', timeout=PAGE_TIMEOUT)
        assert '/account/manage/change-password' not in page.url, (
            'Password change did not redirect away -- the form likely failed validation'
        )

        # ---- Log out, then prove the NEW password (not the old one) works ----
        page.goto(live_server + '/account/logout', timeout=PAGE_TIMEOUT)
        page.goto(live_server + '/account/login', wait_until='domcontentloaded', timeout=PAGE_TIMEOUT)
        page.fill('#email', email)
        page.fill('#password', new_password)
        page.locator('#submit').dispatch_event('click')
        page.wait_for_url(lambda url: '/account/login' not in url, timeout=PAGE_TIMEOUT)
        assert '/account/login' not in page.url
    finally:
        page.close()
