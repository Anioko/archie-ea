"""OAuth 2.0 authorization server for the MCP connector.

Registration is a no-op unless ``MCP_ENABLED`` is true: a self-hosted
install that never turns MCP on gets no OAuth routes at all, and the bearer
identity loader (``app.modules.oauth_provider.identity``) stays unregistered
too, not merely disabled.

Every CSRF exemption below is a single, named, explicitly-reasoned
``csrf.exempt(view)`` call — never a blanket blueprint exemption — recorded
in ``VIEW_OPT_OUT`` so the reason is readable next to the code it exempts
rather than only in a commit message.
"""
from __future__ import annotations

# "module.function" (how flask_wtf.CSRFProtect._is_exempt() matches, not the
# blueprint-qualified endpoint name) -> why it is safe to accept an
# unauthenticated, cookie-less POST without a CSRF token.
VIEW_OPT_OUT = {
    "app.modules.oauth_provider.routes.token_routes.token": (
        "public client token exchange — the caller presents an authorization "
        "code or refresh token it already holds, never a browser session"
    ),
    "app.modules.oauth_provider.routes.token_routes.revoke": (
        "RFC 7009 revocation — same public-client trust model as /oauth/token, "
        "no session is read"
    ),
    "app.modules.oauth_provider.routes.register_routes.register_client": (
        "unauthenticated dynamic client registration; no session is read"
    ),
}


def register(app) -> None:
    if not app.config.get("MCP_ENABLED"):
        app.logger.info("[MCP] MCP_ENABLED is false; OAuth provider not registered")
        return

    from app.extensions import csrf
    from app.modules.oauth_provider.cli import register_cli
    from app.modules.oauth_provider.identity import register_bearer_identity
    from app.modules.oauth_provider.routes.authorize_routes import authorize_bp
    from app.modules.oauth_provider.routes.metadata_routes import metadata_bp
    from app.modules.oauth_provider.routes.register_routes import register_bp, register_client
    from app.modules.oauth_provider.routes.token_routes import revoke, token, token_bp

    app.register_blueprint(metadata_bp)
    app.register_blueprint(authorize_bp)
    app.register_blueprint(token_bp)
    app.register_blueprint(register_bp)

    # csrf.exempt() matches on the view function's __module__ + __name__, so
    # these must be the actual functions, not "blueprint.endpoint" strings —
    # see VIEW_OPT_OUT above for why each one is safe to exempt.
    csrf.exempt(token)
    csrf.exempt(revoke)
    csrf.exempt(register_client)

    register_bearer_identity(app)
    register_cli(app)

    app.logger.info("[MCP] OAuth provider registered (metadata, authorize, token, register)")
