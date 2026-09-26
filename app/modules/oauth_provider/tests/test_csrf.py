"""Any test about CSRF or authentication mode runs with WTF_CSRF_ENABLED=True."""
import re
from urllib.parse import parse_qs, urlsplit

import pytest

REDIRECT_URI = "http://127.0.0.1:9999/callback"
RESOURCE = "https://mcp-test.example/mcp"


def _csrf_token_from_page(html: bytes) -> str:
    match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', html)
    return match.group(1).decode() if match else ""


@pytest.fixture
def csrf_enabled(app):
    app.config["WTF_CSRF_ENABLED"] = True
    yield app
    app.config["WTF_CSRF_ENABLED"] = False


class TestCsrf:
    def test_token_endpoint_works_without_csrf_token(self, csrf_enabled, logged_in_client, client, oauth_client):
        consent_page = logged_in_client.get("/oauth/authorize", query_string={
            "response_type": "code", "client_id": oauth_client.client_id,
            "redirect_uri": REDIRECT_URI, "scope": "mcp:read", "state": "s", "resource": RESOURCE,
        })
        csrf_token = _csrf_token_from_page(consent_page.data)
        # The consent POST itself stays CSRF-protected — pass a real token
        # here so the assertion below is actually about /oauth/token, not
        # an incidental 400 from the consent step.
        resp = logged_in_client.post("/oauth/authorize", data={"decision": "allow", "csrf_token": csrf_token})
        code = parse_qs(urlsplit(resp.headers["Location"]).query)["code"][0]

        token_resp = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        })
        assert token_resp.status_code == 200

    def test_revoke_works_without_csrf_token(self, csrf_enabled, client):
        resp = client.post("/oauth/revoke", data={"token": "whatever"})
        assert resp.status_code == 200

    def test_register_works_without_csrf_token(self, csrf_enabled, client):
        resp = client.post("/oauth/register", json={
            "client_name": "CSRF-test client",
            "redirect_uris": ["https://example.test/callback"],
        })
        assert resp.status_code == 201

    def test_consent_post_without_csrf_token_is_refused(self, csrf_enabled, logged_in_client, oauth_client):
        logged_in_client.get("/oauth/authorize", query_string={
            "response_type": "code", "client_id": oauth_client.client_id,
            "redirect_uri": REDIRECT_URI, "scope": "mcp:read", "state": "s", "resource": RESOURCE,
        })
        resp = logged_in_client.post("/oauth/authorize", data={"decision": "allow"})
        assert resp.status_code == 400

    def test_mcp_works_with_bearer_and_no_csrf_token(self, csrf_enabled, logged_in_client, client, oauth_client):
        consent_page = logged_in_client.get("/oauth/authorize", query_string={
            "response_type": "code", "client_id": oauth_client.client_id,
            "redirect_uri": REDIRECT_URI, "scope": "mcp:read", "state": "s", "resource": RESOURCE,
        })
        csrf_token = _csrf_token_from_page(consent_page.data)
        resp = logged_in_client.post("/oauth/authorize", data={"decision": "allow", "csrf_token": csrf_token})
        code = parse_qs(urlsplit(resp.headers["Location"]).query)["code"][0]
        tokens = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        }).get_json()

        mcp_resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": f"Bearer {tokens['access_token']}", "Mcp-Protocol-Version": "2025-06-18"},
        )
        assert mcp_resp.status_code == 200
