"""The OAuth consent screen, driven by a real browser as a signed-in person.

The API-level tests in app/modules/oauth_provider/tests POST form data
directly, with CSRF off, and never render the page. That is exactly the gap
that let the consent form ship with no csrf_token field at all: nothing
before this walked the same path a browser actually takes — GET the page,
read the rendered form, click Allow.
"""

import base64
import hashlib
import secrets
import urllib.parse

import pytest
from playwright.sync_api import expect

from tests.smoke.conftest import PASSWORD

PAGE_TIMEOUT = 30000


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").click()
    page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _register_client(app):
    from app.extensions import db
    from app.modules.oauth_provider.models import OAuthClient

    with app.app_context():
        client = OAuthClient.register(
            client_name="Smoke Journey Client",
            redirect_uris="http://localhost/callback",
        )
        db.session.commit()
        return client.client_id


@pytest.mark.smoke
@pytest.mark.journey
def test_consent_screen_renders_and_allow_grants_access(browser, live_server, seeded, app):
    """A signed-in person opens the consent screen, sees the requested
    permission described in plain language, and clicking Allow redirects
    back to the client with an authorization code — the real control, not
    an API-level simulation of it."""
    client_id = _register_client(app)
    _verifier, challenge = _pkce_pair()

    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    try:
        _login(page, live_server, seeded["emails"]["cto"])

        auth_params = {
            "client_id": client_id,
            "redirect_uri": "http://localhost/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "mcp:read",
            "state": "smoke-journey-state",
        }
        page.goto(
            live_server + "/oauth/authorize?" + urllib.parse.urlencode(auth_params),
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        expect(page.get_by_text("Read your architecture data")).to_be_visible(timeout=PAGE_TIMEOUT)
        allow_button = page.get_by_role("button", name="Allow")
        expect(allow_button).to_be_visible(timeout=PAGE_TIMEOUT)

        # A real click through the rendered form, not a direct POST — this is
        # what would have failed on the missing csrf_token field.
        with page.expect_navigation(timeout=PAGE_TIMEOUT):
            allow_button.click()

        assert "localhost/callback" in page.url
        assert "code=" in page.url
        assert "state=smoke-journey-state" in page.url
    finally:
        context.close()


@pytest.mark.smoke
@pytest.mark.journey
def test_consent_screen_deny_redirects_without_a_code(browser, live_server, seeded, app):
    """Clicking Deny redirects to the client's own registered URI with
    error=access_denied and no authorization code — never a raw link built
    from unvalidated, unescaped request data."""
    client_id = _register_client(app)
    _verifier, challenge = _pkce_pair()

    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    try:
        _login(page, live_server, seeded["emails"]["cto"])

        auth_params = {
            "client_id": client_id,
            "redirect_uri": "http://localhost/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "mcp:read",
        }
        page.goto(
            live_server + "/oauth/authorize?" + urllib.parse.urlencode(auth_params),
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT,
        )

        deny_button = page.get_by_role("button", name="Deny")
        expect(deny_button).to_be_visible(timeout=PAGE_TIMEOUT)

        with page.expect_navigation(timeout=PAGE_TIMEOUT):
            deny_button.click()

        assert "localhost/callback" in page.url
        assert "error=access_denied" in page.url
        assert "code=" not in page.url
    finally:
        context.close()
