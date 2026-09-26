from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

REDIRECT_URI = "http://127.0.0.1:9999/callback"
RESOURCE = "https://mcp-test.example/mcp"


def _token_row_for(access_token):
    from app.modules.oauth_provider.models import OAuthToken, hash_token

    return OAuthToken.query.filter_by(access_token_hash=hash_token(access_token)).one()


def _issue_access_token(logged_in_client, client, oauth_client, scope="mcp:read"):
    logged_in_client.get("/oauth/authorize", query_string={
        "response_type": "code", "client_id": oauth_client.client_id,
        "redirect_uri": REDIRECT_URI, "scope": scope, "state": "s", "resource": RESOURCE,
    })
    resp = logged_in_client.post("/oauth/authorize", data={"decision": "allow"})
    code = parse_qs(urlsplit(resp.headers["Location"]).query)["code"][0]
    tokens = client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": REDIRECT_URI, "client_id": oauth_client.client_id,
        "resource": RESOURCE,
    }).get_json()
    return tokens["access_token"]


class TestBearerIdentity:
    def test_bearer_on_non_mcp_route_is_anonymous(self, logged_in_client, client, oauth_client):
        access_token = _issue_access_token(logged_in_client, client, oauth_client)
        # A fresh, session-less client sending a bearer to an ordinary page
        # must not be authenticated by it.
        resp = client.get("/account/manage", headers={"Authorization": f"Bearer {access_token}"})
        assert resp.status_code in (302, 401, 404)  # never a 200 as the token's user

    def test_unknown_token_is_401(self, client):
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": "Bearer not-a-real-token", "Mcp-Protocol-Version": "2025-06-18"},
        )
        assert resp.status_code == 401
        assert "resource_metadata=" in resp.headers["WWW-Authenticate"]

    def test_expired_token_is_401(self, logged_in_client, client, oauth_client, db_session):
        from app.modules.oauth_provider.models import OAuthToken

        access_token = _issue_access_token(logged_in_client, client, oauth_client)
        row = _token_row_for(access_token)
        row.access_token_expires_at = datetime.utcnow() - timedelta(seconds=1)
        db_session.commit()

        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": f"Bearer {access_token}", "Mcp-Protocol-Version": "2025-06-18"},
        )
        assert resp.status_code == 401

    def test_organization_mismatch_is_401(self, logged_in_client, client, oauth_client, db_session, organization):
        from app.models.organization import Organization
        from app.modules.oauth_provider.models import OAuthToken

        import uuid

        access_token = _issue_access_token(logged_in_client, client, oauth_client)
        other_org = Organization(name="Other Org", slug=f"other-org-oauth-{uuid.uuid4().hex[:10]}")
        db_session.add(other_org)
        db_session.flush()

        row = _token_row_for(access_token)
        row.organization_id = other_org.id
        db_session.commit()

        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": f"Bearer {access_token}", "Mcp-Protocol-Version": "2025-06-18"},
        )
        assert resp.status_code == 401

    def test_no_set_cookie_on_bearer_authenticated_response(self, logged_in_client, client, oauth_client):
        access_token = _issue_access_token(logged_in_client, client, oauth_client)
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers={"Authorization": f"Bearer {access_token}", "Mcp-Protocol-Version": "2025-06-18"},
        )
        # This app sets an analytics-session Set-Cookie on every response
        # (even a plain, anonymous GET /) — that's pre-existing, unrelated
        # app behaviour, not a login session, so its mere presence isn't the
        # thing to check. What must never happen is a *live* session cookie
        # (one that would keep a browser "logged in" as this bearer's user);
        # an empty/cleared cookie (Max-Age=0, no value) is fine.
        for cookie_header in resp.headers.getlist("Set-Cookie"):
            if cookie_header.split(";", 1)[0].strip().startswith("session="):
                assert "session=;" in cookie_header or "Max-Age=0" in cookie_header, (
                    f"bearer-authenticated response set a live session cookie: {cookie_header!r}"
                )

    def test_last_used_at_updates_at_most_once_a_minute(self, logged_in_client, client, oauth_client, db_session):
        from app.modules.oauth_provider.models import OAuthToken

        access_token = _issue_access_token(logged_in_client, client, oauth_client)
        headers = {"Authorization": f"Bearer {access_token}", "Mcp-Protocol-Version": "2025-06-18"}

        client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=headers)
        first_seen = _token_row_for(access_token).last_used_at

        client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
        second_seen = _token_row_for(access_token).last_used_at

        assert first_seen == second_seen
