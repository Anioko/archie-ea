class TestMetadata:
    def test_authorization_server_metadata(self, client):
        resp = client.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["issuer"] == "https://mcp-test.example"
        assert data["authorization_endpoint"] == "https://mcp-test.example/oauth/authorize"
        assert data["token_endpoint"] == "https://mcp-test.example/oauth/token"
        assert data["registration_endpoint"] == "https://mcp-test.example/oauth/register"
        assert "mcp:read" in data["scopes_supported"]
        assert "mcp:propose" in data["scopes_supported"]

    def test_protected_resource_metadata(self, client):
        resp = client.get("/.well-known/oauth-protected-resource/mcp")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["resource"] == "https://mcp-test.example/mcp"
        assert data["authorization_servers"] == ["https://mcp-test.example"]

    def test_no_entelim_literal_anywhere(self):
        """Nothing derived from a hardcoded example host literal."""
        import re
        import pathlib

        pattern = re.compile(r"entelim\.(com|org)")
        root = pathlib.Path(__file__).resolve().parents[4]
        for sub in ("app/modules/oauth_provider", "app/modules/mcp", "app/templates/oauth"):
            for path in (root / sub).rglob("*.py"):
                assert not pattern.search(path.read_text()), f"found literal in {path}"
            for path in (root / sub).rglob("*.html"):
                assert not pattern.search(path.read_text()), f"found literal in {path}"
