"""OAuth 2.0 / OAuth 2.1 well-known metadata endpoints.

GET /.well-known/oauth-protected-resource       — RFC 9728
GET /.well-known/oauth-authorization-server     — RFC 8414
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.modules.oauth_provider.models import resolve_server_base_url

oauth_metadata_bp = Blueprint("oauth_metadata", __name__)


@oauth_metadata_bp.route("/.well-known/oauth-protected-resource")
def protected_resource_metadata():
    """RFC 9728: Protected Resource Metadata.

    Published at the root so any client can discover the authorization server
    before it ever reaches the MCP endpoint. There is deliberately no
    hosted-product fallback — a self-hosted or staging install with no
    ``MCP_OAUTH_BASE_URL`` override must never be told to fetch tokens from
    a different operator's server; ``resolve_server_base_url()`` derives the
    request's own scheme + host instead (RFC 8414 requires an absolute URI
    here, so an empty/relative fallback is not a valid alternative either).
    """
    base = resolve_server_base_url()
    return jsonify({
        "resource": f"{base}/mcp",
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
        "scopes_supported": ["mcp:read"],
    })


@oauth_metadata_bp.route("/.well-known/oauth-authorization-server")
def authorization_server_metadata():
    """RFC 8414: Authorization Server Metadata."""
    base = resolve_server_base_url()
    return jsonify({
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "scopes_supported": ["mcp:read"],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["none"],
        "code_challenge_methods_supported": ["S256"],
    })