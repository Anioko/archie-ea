"""A genuinely bearer-only MCP client: no session cookie, ever.

Every other test in this package calls ``login_as`` before minting a token,
so the same client also carries a browser session cookie with a registered
``_sid`` — that cookie is what actually authenticates the nested
``call_internal_api()`` calls lens tools make, not the bearer token. These
tests mint the token straight from the model layer (the same thing the
token endpoint does internally) and never touch a session at all, so the
only credential in play is the ``Authorization`` header, matching a real
external assistant.
"""

from __future__ import annotations

import json

import pytest

from app.modules.mcp.tests.conftest import make_user as _make_user


def _make_element(db_session, org_id, name_hint, type_="ApplicationComponent"):
    from app.models import ArchiMateElement

    row = ArchiMateElement(
        name=f"E-{name_hint}", type=type_, layer="application", organization_id=org_id
    )
    db_session.add(row)
    db_session.flush()
    return row


def _mint_token_directly(db_session, org, user, scope="mcp:read") -> str:
    """Issue a token the same way the token endpoint does, without ever
    going through a browser session or the authorize/token HTTP routes."""
    from app.modules.oauth_provider.models import OAuthClient, OAuthToken

    oauth_client = OAuthClient.register(
        client_name="Bearer-only Test Client",
        redirect_uris="http://localhost/callback",
    )
    token = OAuthToken.issue(client_id=oauth_client.client_id, user_id=user.id, scope=scope)
    db_session.flush()
    return token.plaintext_access_token


def _mcp_call(client, token: str, tool_name: str, arguments: dict) -> "tuple[int, dict]":
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    resp = client.post(
        "/mcp",
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.status_code, resp.get_json()


class TestBearerOnlyToolCalls:
    """D2: a bearer-only client (no cookie at all) must be able to call tools."""

    def test_lens_tool_succeeds_with_bearer_only(self, app, client, db_session, make_org):
        """ask_impact works for a client that never logged in and carries no
        session cookie — only the Authorization header."""
        org = make_org("bearer")
        user = _make_user(db_session, org, "bearer-impact@example.com")
        element = _make_element(db_session, org.id, "bearer-impact")

        token = _mint_token_directly(db_session, org, user)

        status, body = _mcp_call(client, token, "ask_impact", {"element_id": element.id})
        assert status == 200, body
        result = json.loads(body["result"]["content"][0]["text"])
        assert result["success"] is True, result

    def test_get_element_succeeds_with_bearer_only(self, app, client, db_session, make_org):
        org = make_org("bearer")
        user = _make_user(db_session, org, "bearer-detail@example.com")
        element = _make_element(db_session, org.id, "bearer-detail")

        token = _mint_token_directly(db_session, org, user)

        status, body = _mcp_call(client, token, "get_element", {"element_id": element.id})
        assert status == 200, body
        result = json.loads(body["result"]["content"][0]["text"])
        assert result.get("name") == element.name

    def test_list_canvases_succeeds_with_bearer_only(self, app, client, db_session, make_org):
        """A tool that calls call_internal_api twice in one request (BMC list
        + business-case list) — the g-sharing fix must survive more than one
        nested call in a single tool execution."""
        org = make_org("bearer")
        user = _make_user(db_session, org, "bearer-canvas@example.com")

        token = _mint_token_directly(db_session, org, user)

        status, body = _mcp_call(client, token, "list_canvases", {})
        assert status == 200, body
        result = json.loads(body["result"]["content"][0]["text"])
        assert "business_model_canvases" in result
        assert "business_cases" in result


class TestScopeEnforcement:
    """D6: a token with no mcp:read scope must not authenticate at /mcp."""

    def test_token_without_mcp_read_scope_is_rejected(self, app, client, db_session, make_org):
        org = make_org("bearer-scope")
        user = _make_user(db_session, org, "bearer-scope@example.com")
        element = _make_element(db_session, org.id, "scope-test")

        token = _mint_token_directly(db_session, org, user, scope="something_else")

        status, body = _mcp_call(client, token, "ask_impact", {"element_id": element.id})
        assert status == 401, body


class TestNoBrowserSessionMinted:
    """D10: a bearer call must not create a session or remember-me cookie,
    and must not fire the login signal."""

    def test_mcp_response_sets_no_cookies(self, app, client, db_session, make_org):
        org = make_org("bearer-cookie")
        user = _make_user(db_session, org, "bearer-cookie@example.com")
        element = _make_element(db_session, org.id, "cookie-test")

        token = _mint_token_directly(db_session, org, user)

        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "ask_impact", "arguments": {"element_id": element.id}},
        }
        resp = client.post(
            "/mcp",
            data=json.dumps(payload),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        set_cookie_headers = resp.headers.get_all("Set-Cookie")
        # flask-login's own after_request hook unconditionally pops
        # session["_remember"], which marks an empty session "modified" and
        # makes Flask send a delete directive for a cookie the client never
        # had (Max-Age=0) — harmless noise present on any anonymous request,
        # not a live session. What must never appear is a cookie that
        # actually *sets* a value: a real session (non-deletion Set-Cookie
        # for "session") or any remember_token cookie at all.
        live_session_cookies = [
            h for h in set_cookie_headers
            if h.startswith("session=") and "Max-Age=0" not in h
        ]
        assert live_session_cookies == [], set_cookie_headers
        assert not any("remember_token" in h for h in set_cookie_headers), set_cookie_headers

    def test_mcp_call_does_not_fire_login_signal(self, app, client, db_session, make_org):
        from flask_login import user_logged_in

        org = make_org("bearer-signal")
        user = _make_user(db_session, org, "bearer-signal@example.com")
        element = _make_element(db_session, org.id, "signal-test")
        token = _mint_token_directly(db_session, org, user)

        fired = []

        def _on_login(sender, user):
            fired.append(user)

        user_logged_in.connect(_on_login, app)
        try:
            status, _body = _mcp_call(client, token, "ask_impact", {"element_id": element.id})
            assert status == 200
        finally:
            user_logged_in.disconnect(_on_login, app)

        assert fired == [], "login signal must not fire for a bearer-only tool call"


class TestUnauthenticatedResponseShape:
    """D11: 401s carry WWW-Authenticate; D14: no raw exception text leaks."""

    def test_missing_bearer_returns_www_authenticate(self, client):
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        resp = client.post("/mcp", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 401
        header = resp.headers.get("WWW-Authenticate", "")
        assert header.startswith("Bearer"), header
        assert "resource_metadata=" in header

    def test_invalid_bearer_returns_www_authenticate_not_raw_error(self, client):
        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "ask_impact", "arguments": {"element_id": 1}},
        }
        resp = client.post(
            "/mcp",
            data=json.dumps(payload),
            content_type="application/json",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers


class TestToolExistenceCheckedAfterAuth:
    """D15: an unknown tool name must not be distinguishable from a known
    one before authentication — both return the same 401."""

    def test_unknown_tool_without_auth_returns_401_not_404(self, client):
        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "definitely_not_a_real_tool", "arguments": {}},
        }
        resp = client.post("/mcp", data=json.dumps(payload), content_type="application/json")
        assert resp.status_code == 401, resp.get_json()


class TestOriginAndResourceFailClosed:
    """D13: an unconfigured Origin/resource check must not silently accept
    everything — it falls back to comparing against this server's own
    origin instead of skipping the check."""

    def test_cross_origin_request_rejected_without_explicit_config(
        self, app, client, db_session, make_org
    ):
        org = make_org("bearer-origin")
        user = _make_user(db_session, org, "bearer-origin@example.com")
        element = _make_element(db_session, org.id, "origin-test")
        token = _mint_token_directly(db_session, org, user)

        app.config["MCP_ALLOWED_ORIGIN"] = ""

        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "ask_impact", "arguments": {"element_id": element.id}},
        }
        resp = client.post(
            "/mcp",
            data=json.dumps(payload),
            content_type="application/json",
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": "https://attacker.example",
            },
        )
        assert resp.status_code == 403, resp.get_data(as_text=True)

    def test_same_origin_request_still_works_without_explicit_config(
        self, app, client, db_session, make_org
    ):
        org = make_org("bearer-origin-ok")
        user = _make_user(db_session, org, "bearer-origin-ok@example.com")
        element = _make_element(db_session, org.id, "origin-ok-test")
        token = _mint_token_directly(db_session, org, user)

        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "ask_impact", "arguments": {"element_id": element.id}},
        }
        with app.test_request_context("/"):
            from flask import request as flask_request
            same_origin = flask_request.url_root.rstrip("/")
        resp = client.post(
            "/mcp",
            data=json.dumps(payload),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}", "Origin": same_origin},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)


class TestInactiveUserCleanRejection:
    """D18: an inactive user's token must not 500."""

    def test_inactive_user_token_returns_401(
        self, app, client, db_session, make_org, monkeypatch
    ):
        org = make_org("bearer-inactive")
        user = _make_user(db_session, org, "bearer-inactive@example.com")
        element = _make_element(db_session, org.id, "inactive-test")
        token = _mint_token_directly(db_session, org, user)

        monkeypatch.setattr(type(user), "is_active", property(lambda self: False))

        status, body = _mcp_call(client, token, "ask_impact", {"element_id": element.id})
        assert status == 401, body
