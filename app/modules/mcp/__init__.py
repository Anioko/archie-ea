"""The /mcp endpoint. Registration is a no-op unless MCP_ENABLED is true."""
from __future__ import annotations

VIEW_OPT_OUT = {
    "app.modules.mcp.blueprint.mcp_endpoint": (
        "refuses every request not authenticated by a bearer token "
        "(app.modules.oauth_provider.identity) — no session is ever read here"
    ),
}


def register(app) -> None:
    if not app.config.get("MCP_ENABLED"):
        return

    from app.extensions import csrf
    from app.modules.mcp.blueprint import mcp_bp, mcp_endpoint

    app.register_blueprint(mcp_bp)
    csrf.exempt(mcp_endpoint)

    app.logger.info("[MCP] /mcp endpoint registered")
