import pytest


def test_mcp_disabled_registers_no_oauth_routes(monkeypatch):
    """MCP_ENABLED=false: no OAuth blueprint registers, and the loader is inert.

    config.py reads MCP_ENABLED/PUBLIC_BASE_URL from the environment once, at
    class-body (import) time, so monkeypatching os.environ after config.py
    has already been imported has no effect. Patch the Config class
    attributes directly instead — that's what app.config.from_object() reads
    at create_app() time.
    """
    from config import Config

    monkeypatch.setattr(Config, "MCP_ENABLED", False)
    monkeypatch.setattr(Config, "PUBLIC_BASE_URL", "")

    from app import create_app

    app = create_app("testing")

    oauth_paths = [
        r.rule for r in app.url_map.iter_rules()
        if r.rule.startswith("/oauth/") or r.rule.startswith("/.well-known/oauth") or r.rule == "/mcp"
    ]
    assert oauth_paths == []

    # The bearer loader is only ever consulted for /mcp or a bridge-marked
    # request. With no /mcp route at all, a bearer header can't reach it —
    # confirmed independently by an anonymous 404 rather than a 401/200.
    resp = app.test_client().post("/mcp", headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 404


def test_boot_fails_when_mcp_enabled_without_public_base_url(monkeypatch):
    from config import Config

    monkeypatch.setattr(Config, "MCP_ENABLED", True)
    monkeypatch.setattr(Config, "PUBLIC_BASE_URL", "")

    from app import create_app

    with pytest.raises(RuntimeError):
        create_app("testing")
