class TestRegister:
    def test_valid_registration(self, client):
        resp = client.post("/oauth/register", json={
            "client_name": "My Assistant",
            "redirect_uris": ["https://example.test/callback"],
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["client_id"].startswith("mcp_")
        assert body["token_endpoint_auth_method"] == "none"
        assert body["grant_types"] == ["authorization_code", "refresh_token"]

    def test_missing_client_name(self, client):
        resp = client.post("/oauth/register", json={"redirect_uris": ["https://example.test/cb"]})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "invalid_client_metadata"

    def test_missing_redirect_uris(self, client):
        resp = client.post("/oauth/register", json={"client_name": "No URIs"})
        assert resp.status_code == 400

    def test_wildcard_redirect_uri_rejected(self, client):
        resp = client.post("/oauth/register", json={
            "client_name": "Wildcard",
            "redirect_uris": ["https://*.example.test/callback"],
        })
        assert resp.status_code == 400

    def test_fragment_redirect_uri_rejected(self, client):
        resp = client.post("/oauth/register", json={
            "client_name": "Fragment",
            "redirect_uris": ["https://example.test/callback#frag"],
        })
        assert resp.status_code == 400

    def test_http_non_loopback_rejected(self, client):
        resp = client.post("/oauth/register", json={
            "client_name": "Plain HTTP",
            "redirect_uris": ["http://example.test/callback"],
        })
        assert resp.status_code == 400

    def test_http_loopback_accepted(self, client):
        resp = client.post("/oauth/register", json={
            "client_name": "Loopback client",
            "redirect_uris": ["http://127.0.0.1:51234/callback"],
        })
        assert resp.status_code == 201

    def test_confidential_client_auth_method_rejected(self, client):
        resp = client.post("/oauth/register", json={
            "client_name": "Confidential",
            "redirect_uris": ["https://example.test/callback"],
            "token_endpoint_auth_method": "client_secret_basic",
        })
        assert resp.status_code == 400

    def test_hostile_client_name_is_escaped_and_capped(self, client):
        hostile = "<script>alert(1)</script>" + ("x" * 10000)
        resp = client.post("/oauth/register", json={
            "client_name": hostile,
            "redirect_uris": ["https://example.test/callback"],
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert len(body["client_name"]) <= 100
        assert "<script>" in body["client_name"]  # stored as data, escaped only on render

    def test_client_name_capped_at_100_chars(self, client):
        resp = client.post("/oauth/register", json={
            "client_name": "x" * 500,
            "redirect_uris": ["https://example.test/callback"],
        })
        assert resp.status_code == 201
        assert len(resp.get_json()["client_name"]) == 100

    def test_registers_without_a_token(self, client):
        # Registration itself needs no Authorization header at all.
        resp = client.post("/oauth/register", json={
            "client_name": "No auth needed",
            "redirect_uris": ["https://example.test/callback"],
        })
        assert resp.status_code == 201

    def test_rate_limit_429_after_default_limit(self, app, client):
        from app.services.rate_limiter import _rate_limiter
        from app.modules.oauth_provider.routes.register_routes import _rate_limit_key

        app.config["RATE_LIMITING_ENABLED"] = True
        try:
            with app.test_request_context():
                _rate_limiter.reset(_rate_limit_key())

            payload = {"client_name": "Limited", "redirect_uris": ["https://example.test/cb"]}
            last = None
            for _ in range(11):
                last = client.post("/oauth/register", json=payload)
            assert last.status_code == 429
            assert "Retry-After" in last.headers
        finally:
            app.config["RATE_LIMITING_ENABLED"] = False
            with app.test_request_context():
                _rate_limiter.reset(_rate_limit_key())

    def test_registered_client_completes_full_flow(self, client, logged_in_client, db_session):
        reg = client.post("/oauth/register", json={
            "client_name": "Full flow client",
            "redirect_uris": ["http://127.0.0.1:9876/cb"],
        }).get_json()

        from urllib.parse import parse_qs, urlsplit

        resource = "https://mcp-test.example/mcp"
        logged_in_client.get("/oauth/authorize", query_string={
            "response_type": "code", "client_id": reg["client_id"],
            "redirect_uri": "http://127.0.0.1:9876/cb", "scope": "mcp:read",
            "state": "s", "resource": resource,
        })
        authorize_resp = logged_in_client.post("/oauth/authorize", data={"decision": "allow"})
        code = parse_qs(urlsplit(authorize_resp.headers["Location"]).query)["code"][0]

        token_resp = client.post("/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": "http://127.0.0.1:9876/cb", "client_id": reg["client_id"],
            "resource": resource,
        })
        assert token_resp.status_code == 200
        assert "access_token" in token_resp.get_json()
