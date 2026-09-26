class TestTransport:
    def test_get_is_405(self, client):
        assert client.get("/mcp").status_code == 405

    def test_no_bearer_no_session_is_401(self, client):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                            headers={"Mcp-Protocol-Version": "2025-06-18"})
        assert resp.status_code == 401
        assert "resource_metadata=" in resp.headers["WWW-Authenticate"]

    def test_session_cookie_without_bearer_is_401(self, logged_in_client):
        resp = logged_in_client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                      headers={"Mcp-Protocol-Version": "2025-06-18"})
        assert resp.status_code == 401

    def test_json_array_refused(self, client, mcp_headers):
        resp = client.post("/mcp", json=[{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}], headers=mcp_headers)
        assert resp.status_code == 400

    def test_missing_protocol_version_is_400(self, client, access_token):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                            headers={"Authorization": f"Bearer {access_token}"})
        assert resp.status_code == 400

    def test_unsupported_protocol_version_is_400(self, client, access_token):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                            headers={"Authorization": f"Bearer {access_token}", "Mcp-Protocol-Version": "1999-01-01"})
        assert resp.status_code == 400

    def test_mismatched_mcp_method_header_is_400(self, client, mcp_headers):
        headers = dict(mcp_headers, **{"Mcp-Method": "tools/call"})
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=headers)
        assert resp.status_code == 400

    def test_notifications_initialized_is_202_no_body(self, client, mcp_headers):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=mcp_headers)
        assert resp.status_code == 202
        assert resp.data == b""

    def test_origin_not_allowed_is_403(self, client, mcp_headers):
        headers = dict(mcp_headers, Origin="https://not-allowed.example")
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=headers)
        assert resp.status_code == 403

    def test_no_origin_header_is_allowed(self, client, mcp_headers):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=mcp_headers)
        assert resp.status_code == 200

    def test_tools_list_has_titles(self, client, mcp_headers):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=mcp_headers)
        tools = resp.get_json()["result"]["tools"]
        assert len(tools) >= 2
        for tool in tools:
            assert tool["title"]
            assert tool["inputSchema"]["type"] == "object"

    def test_unknown_method_is_400(self, client, mcp_headers):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "nope"}, headers=mcp_headers)
        assert resp.status_code == 400

    def test_insufficient_scope_is_403_before_tool_runs(self, client, db_session, access_token):
        from app.modules.oauth_provider.models import OAuthToken, hash_token

        row = OAuthToken.query.filter_by(access_token_hash=hash_token(access_token)).one()
        row.scope = ""
        db_session.commit()

        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "search_elements", "arguments": {}}},
            headers={"Authorization": f"Bearer {access_token}", "Mcp-Protocol-Version": "2025-06-18"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"] == "insufficient_scope"
