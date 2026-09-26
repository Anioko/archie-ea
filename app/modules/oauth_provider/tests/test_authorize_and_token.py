from urllib.parse import parse_qs, urlsplit

import pytest

REDIRECT_URI = "http://127.0.0.1:9999/callback"
RESOURCE = "https://mcp-test.example/mcp"


def _authorize_query(oauth_client, scope="mcp:read", resource=RESOURCE, redirect_uri=REDIRECT_URI):
    return {
        "response_type": "code",
        "client_id": oauth_client.client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": "xyz123",
        "resource": resource,
    }


class TestAuthorizeGet:
    def test_requires_login(self, client, oauth_client):
        resp = client.get("/oauth/authorize", query_string=_authorize_query(oauth_client))
        assert resp.status_code in (302, 401)

    def test_unregistered_redirect_uri_is_not_redirected_to(self, logged_in_client, oauth_client):
        q = _authorize_query(oauth_client, redirect_uri="http://evil.example/callback")
        resp = logged_in_client.get("/oauth/authorize", query_string=q)
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid_request"

    def test_unknown_client(self, logged_in_client):
        q = {"response_type": "code", "client_id": "nope", "redirect_uri": REDIRECT_URI,
             "scope": "mcp:read", "state": "s", "resource": RESOURCE}
        resp = logged_in_client.get("/oauth/authorize", query_string=q)
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid_client"

    def test_resource_mismatch_redirects_with_invalid_target(self, logged_in_client, oauth_client):
        q = _authorize_query(oauth_client, resource="https://other.example/mcp")
        resp = logged_in_client.get("/oauth/authorize", query_string=q)
        assert resp.status_code == 302
        parsed = parse_qs(urlsplit(resp.headers["Location"]).query)
        assert parsed["error"] == ["invalid_target"]

    def test_scope_not_allowed_redirects_with_invalid_scope(self, logged_in_client, oauth_client):
        q = _authorize_query(oauth_client, scope="mcp:admin")
        resp = logged_in_client.get("/oauth/authorize", query_string=q)
        assert resp.status_code == 302
        parsed = parse_qs(urlsplit(resp.headers["Location"]).query)
        assert parsed["error"] == ["invalid_scope"]

    def test_valid_request_renders_consent(self, logged_in_client, oauth_client):
        resp = logged_in_client.get("/oauth/authorize", query_string=_authorize_query(oauth_client))
        assert resp.status_code == 200
        assert oauth_client.client_name.encode() in resp.data
        assert b"Allow" in resp.data
        assert b"Deny" in resp.data

    def test_read_only_scope_does_not_offer_propose_checkbox(self, logged_in_client, oauth_client):
        resp = logged_in_client.get("/oauth/authorize", query_string=_authorize_query(oauth_client, scope="mcp:read"))
        assert b"grant_propose" not in resp.data


class TestAuthorizeDecision:
    def test_deny_redirects_with_access_denied(self, logged_in_client, oauth_client):
        logged_in_client.get("/oauth/authorize", query_string=_authorize_query(oauth_client))
        resp = logged_in_client.post("/oauth/authorize", data={"decision": "deny"})
        assert resp.status_code == 302
        parsed = parse_qs(urlsplit(resp.headers["Location"]).query)
        assert parsed["error"] == ["access_denied"]
        assert parsed["state"] == ["xyz123"]

    def test_allow_redirects_with_code_and_preserves_existing_query(self, logged_in_client, oauth_client):
        from app.modules.oauth_provider.models import OAuthClient

        oauth_client.redirect_uris = [REDIRECT_URI + "?existing=1"]
        from app import db
        db.session.commit()

        q = _authorize_query(oauth_client, redirect_uri=REDIRECT_URI + "?existing=1")
        logged_in_client.get("/oauth/authorize", query_string=q)
        resp = logged_in_client.post("/oauth/authorize", data={"decision": "allow"})
        assert resp.status_code == 302
        location = urlsplit(resp.headers["Location"])
        parsed = parse_qs(location.query)
        assert parsed["existing"] == ["1"]
        assert "code" in parsed
        assert parsed["state"] == ["xyz123"]

    def test_no_pending_authorization_is_rejected(self, logged_in_client):
        resp = logged_in_client.post("/oauth/authorize", data={"decision": "allow"})
        assert resp.status_code == 400


def _get_code(logged_in_client, oauth_client, scope="mcp:read", grant_propose=False):
    logged_in_client.get("/oauth/authorize", query_string=_authorize_query(oauth_client, scope=scope))
    data = {"decision": "allow"}
    if grant_propose:
        data["grant_propose"] = "on"
    resp = logged_in_client.post("/oauth/authorize", data=data)
    parsed = parse_qs(urlsplit(resp.headers["Location"]).query)
    return parsed["code"][0]


class TestToken:
    def test_authorization_code_exchange(self, logged_in_client, client, oauth_client):
        code = _get_code(logged_in_client, oauth_client)
        resp = client.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["token_type"] == "Bearer"
        assert body["scope"] == "mcp:read"
        assert "access_token" in body and "refresh_token" in body

    def test_code_is_single_use(self, logged_in_client, client, oauth_client):
        code = _get_code(logged_in_client, oauth_client)
        params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        }
        first = client.post("/oauth/token", data=params)
        assert first.status_code == 200
        second = client.post("/oauth/token", data=params)
        assert second.status_code == 400
        assert second.get_json()["error"] == "invalid_grant"

    def test_missing_resource_is_invalid_target(self, client, oauth_client):
        resp = client.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "code": "whatever",
            "redirect_uri": REDIRECT_URI,
            "client_id": oauth_client.client_id,
        })
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid_target"

    def test_unsupported_grant_type(self, client, oauth_client):
        resp = client.post("/oauth/token", data={"grant_type": "password", "resource": RESOURCE})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "unsupported_grant_type"

    def test_refresh_token_rotates(self, logged_in_client, client, oauth_client):
        code = _get_code(logged_in_client, oauth_client)
        first = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        }).get_json()

        refreshed = client.post("/oauth/token", data={
            "grant_type": "refresh_token",
            "refresh_token": first["refresh_token"],
            "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        })
        assert refreshed.status_code == 200
        second = refreshed.get_json()
        assert second["access_token"] != first["access_token"]

        # Old refresh token cannot be reused after rotation.
        reuse = client.post("/oauth/token", data={
            "grant_type": "refresh_token",
            "refresh_token": first["refresh_token"],
            "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        })
        assert reuse.status_code == 400

    def test_revoke_then_bearer_call_is_401(self, logged_in_client, client, oauth_client):
        code = _get_code(logged_in_client, oauth_client)
        tokens = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        }).get_json()

        revoke_resp = client.post("/oauth/revoke", data={"token": tokens["access_token"]})
        assert revoke_resp.status_code == 200

        mcp_resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "Mcp-Protocol-Version": "2025-06-18",
            },
        )
        assert mcp_resp.status_code == 401

    def test_revoke_unknown_token_still_returns_200(self, client):
        resp = client.post("/oauth/revoke", data={"token": "not-a-real-token"})
        assert resp.status_code == 200


class TestProposeScope:
    def test_propose_requires_checkbox_and_permission(self, logged_in_client, client, oauth_client):
        code = _get_code(logged_in_client, oauth_client, scope="mcp:read mcp:propose", grant_propose=True)
        tokens = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        }).get_json()
        assert "mcp:propose" in tokens["scope"].split(" ")

    def test_propose_not_granted_without_checkbox(self, logged_in_client, client, oauth_client):
        code = _get_code(logged_in_client, oauth_client, scope="mcp:read mcp:propose", grant_propose=False)
        tokens = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "client_id": oauth_client.client_id,
            "resource": RESOURCE,
        }).get_json()
        assert "mcp:propose" not in tokens["scope"].split(" ")
