"""RFC 8414 authorization server metadata and RFC 9728 protected resource
metadata for the MCP connector.

Every URL here is built from ``PUBLIC_BASE_URL`` — never from
``request.host`` and never from a hardcoded literal — so a forwarded or
spoofed Host header can never change what a client is told the issuer is.
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify

metadata_bp = Blueprint("oauth_metadata", __name__)


def _base_url() -> str:
    return current_app.config["PUBLIC_BASE_URL"]


def _resource_url() -> str:
    return _base_url() + "/mcp"


@metadata_bp.route("/.well-known/oauth-authorization-server", methods=["GET"])
def authorization_server_metadata():
    base = _base_url()
    scopes = list(current_app.config.get("OAUTH_SUPPORTED_SCOPES", ()))
    return jsonify({
        "issuer": base,
        "authorization_endpoint": base + "/oauth/authorize",
        "token_endpoint": base + "/oauth/token",
        "revocation_endpoint": base + "/oauth/revoke",
        "registration_endpoint": base + "/oauth/register",
        "scopes_supported": scopes,
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none"],
    })


@metadata_bp.route("/.well-known/oauth-protected-resource/mcp", methods=["GET"])
def protected_resource_metadata():
    base = _base_url()
    scopes = list(current_app.config.get("OAUTH_SUPPORTED_SCOPES", ()))
    return jsonify({
        "resource": _resource_url(),
        "authorization_servers": [base],
        "scopes_supported": scopes,
        "bearer_methods_supported": ["header"],
    })
