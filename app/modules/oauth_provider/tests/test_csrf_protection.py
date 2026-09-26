"""CSRF behaviour for the OAuth/MCP surface under a config that actually
enforces it.

The shared ``app`` fixture runs with ``WTF_CSRF_ENABLED = False`` (like the
rest of the test suite), which is exactly the condition that let the token
endpoint, the MCP endpoint and the consent form's missing hidden field all
ship broken at once: nothing in the suite ever exercised the enforced path.
These tests flip ``WTF_CSRF_ENABLED`` on for the current app instance —
flask-wtf reads that flag live on every request, so no second app needs to
be booted — and restore it afterwards.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import urllib.parse

import pytest

from app.modules.oauth_provider.tests.conftest import make_user as _make_user


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


@pytest.fixture
def csrf_enabled(app):
    """Force real CSRF enforcement for the duration of one test."""
    previous = app.config["WTF_CSRF_ENABLED"]
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        yield app
    finally:
        app.config["WTF_CSRF_ENABLED"] = previous


class TestTokenEndpointExemptUnderCsrf:
    """POST /oauth/token has no session cookie to carry a CSRF token."""

    def test_token_exchange_succeeds_with_csrf_enabled(
        self, csrf_enabled, client, db_session, make_org, login_as
    ):
        org = make_org("csrf")
        user = _make_user(db_session, org, "csrf-token@example.com")
        login_as(client, user)

        from app.modules.oauth_provider.models import OAuthClient

        oauth_client = OAuthClient.register(
            client_name="CSRF Test Client",
            redirect_uris="http://localhost/callback",
        )
        verifier, challenge = _pkce_pair()

        consent_page = client.get(
            f"/oauth/authorize?client_id={oauth_client.client_id}"
            f"&redirect_uri=http://localhost/callback"
            f"&code_challenge={challenge}&code_challenge_method=S256&scope=mcp:read"
        )
        csrf_token = _extract_csrf_token(consent_page.get_data(as_text=True))
        assert csrf_token is not None

        resp = client.post(
            "/oauth/authorize",
            data={
                "client_id": oauth_client.client_id,
                "redirect_uri": "http://localhost/callback",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "scope": "mcp:read",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302, resp.get_data(as_text=True)
        location = resp.headers["Location"]
        auth_code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)["code"][0]

        # The exchange itself carries no session-derived CSRF token at all —
        # this is the request that must succeed unconditionally.
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": "http://localhost/callback",
                "client_id": oauth_client.client_id,
                "code_verifier": verifier,
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert "access_token" in resp.get_json()


class TestMcpEndpointExemptUnderCsrf:
    """POST /mcp is bearer-only; it must not be rejected by CSRF either."""

    def test_tools_list_succeeds_with_csrf_enabled(self, csrf_enabled, client):
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        resp = client.post("/mcp", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 200, resp.get_data(as_text=True)


class TestConsentFormStillRequiresCsrf:
    """/oauth/authorize is NOT exempt: the consent POST must carry a token."""

    def test_consent_post_without_csrf_token_is_rejected(
        self, csrf_enabled, client, db_session, make_org, login_as
    ):
        org = make_org("csrf-consent")
        user = _make_user(db_session, org, "csrf-consent@example.com")
        login_as(client, user)

        from app.modules.oauth_provider.models import OAuthClient

        oauth_client = OAuthClient.register(
            client_name="Consent CSRF Client",
            redirect_uris="http://localhost/callback",
        )
        _verifier, challenge = _pkce_pair()

        # No csrf_token field at all — must be rejected, not redirected with a code.
        resp = client.post(
            "/oauth/authorize",
            data={
                "client_id": oauth_client.client_id,
                "redirect_uri": "http://localhost/callback",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "scope": "mcp:read",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400, resp.get_data(as_text=True)

    def test_rendered_consent_page_carries_csrf_token(
        self, csrf_enabled, client, db_session, make_org, login_as
    ):
        """The template regression this whole defect started from: the
        rendered form must actually contain the hidden csrf_token input."""
        org = make_org("csrf-render")
        user = _make_user(db_session, org, "csrf-render@example.com")
        login_as(client, user)

        from app.modules.oauth_provider.models import OAuthClient

        oauth_client = OAuthClient.register(
            client_name="Render Client",
            redirect_uris="http://localhost/callback",
        )
        _verifier, challenge = _pkce_pair()

        resp = client.get(
            f"/oauth/authorize?client_id={oauth_client.client_id}"
            f"&redirect_uri=http://localhost/callback"
            f"&code_challenge={challenge}&code_challenge_method=S256&scope=mcp:read"
        )
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert _extract_csrf_token(html) is not None, \
            "consent form is missing its csrf_token hidden field"


def _extract_csrf_token(html: str) -> str | None:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    return match.group(1) if match else None
