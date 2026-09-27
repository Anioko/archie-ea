import json


def _mcp_call(client, headers, name, arguments):
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
        headers=headers,
    )


class TestGetElementParity:
    def test_get_element_matches_rest_body_exactly(self, client, mcp_headers, element, logged_in_client):
        rest_resp = logged_in_client.get(f"/archimate/api/elements/{element.id}/detail")
        rest_body = rest_resp.get_json()

        mcp_resp = _mcp_call(client, mcp_headers, "get_element", {"element_id": element.id})
        assert mcp_resp.status_code == 200
        result = mcp_resp.get_json()["result"]
        assert result["structuredContent"] == rest_body
        assert json.loads(result["content"][0]["text"]) == rest_body
        assert result["isError"] is False

    def test_get_element_404_gives_iserror_true_with_body_verbatim(self, client, mcp_headers, logged_in_client):
        rest_resp = logged_in_client.get("/archimate/api/elements/999999/detail")
        rest_body = rest_resp.get_json()
        assert rest_resp.status_code == 404

        mcp_resp = _mcp_call(client, mcp_headers, "get_element", {"element_id": 999999})
        assert mcp_resp.status_code == 200
        result = mcp_resp.get_json()["result"]
        assert result["isError"] is True
        assert result["structuredContent"] == rest_body

    def test_get_element_tool_title(self, client, mcp_headers):
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=mcp_headers)
        tools = {t["name"]: t for t in resp.get_json()["result"]["tools"]}
        assert tools["get_element"]["title"] == "Get an architecture element"
        assert tools["search_elements"]["title"] == "Search architecture elements"


class TestSearchElementsParity:
    def test_search_elements_matches_rest_body_exactly(self, client, mcp_headers, element, logged_in_client):
        rest_resp = logged_in_client.get("/archimate/api/elements/search", query_string={"q": "Test Component"})
        rest_body = rest_resp.get_json()

        mcp_resp = _mcp_call(client, mcp_headers, "search_elements", {"q": "Test Component"})
        result = mcp_resp.get_json()["result"]
        assert result["structuredContent"] == rest_body
        assert result["isError"] is False


class TestBridgeIndependence:
    def test_tampering_with_outer_g_does_not_change_inner_response(self, client, mcp_headers, element, app):
        """Tampering with the outer request's g/login cache before the view
        runs must not change the inner (bridged) response: the bearer
        identity loader re-derives g.current_org_id from the token on every
        request, and the bridge call carries only the bearer header — never
        the outer request's session or g state."""
        from flask import g

        def _poison_g():
            g.current_org_id = -999999
            g.login_cache_poisoned = "attacker-controlled"

        # app.before_request() itself refuses to register after the app has
        # already handled a request (which fixture setup above triggered) —
        # append to the list Flask iterates at request time directly instead.
        app.before_request_funcs.setdefault(None, []).append(_poison_g)
        try:
            resp = _mcp_call(client, mcp_headers, "get_element", {"element_id": element.id})
        finally:
            app.before_request_funcs[None].remove(_poison_g)

        assert resp.status_code == 200
        assert resp.get_json()["result"]["isError"] is False
