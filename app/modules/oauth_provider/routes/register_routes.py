"""POST /oauth/register — RFC 7591-style dynamic client registration.

Public clients only. Unauthenticated by design (a fresh assistant install
has no session yet) and rate-limited per remote address using the app's
existing in-house rate limiter (``app.services.rate_limiter``).
"""
from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from app.modules.oauth_provider.models import OAuthClient
from app.services.rate_limiter import rate_limit

register_bp = Blueprint("oauth_register", __name__)

_REGISTRATION_RATE_LIMIT = int(os.environ.get("OAUTH_CLIENT_REGISTRATION_RATE_LIMIT", "10"))


def _rate_limit_key():
    return f"ip:{request.remote_addr}:oauth_register"


@register_bp.route("/oauth/register", methods=["POST"])
@rate_limit(_REGISTRATION_RATE_LIMIT, "1h", key_func=_rate_limit_key)
def register_client():
    body = request.get_json(silent=True) or {}
    client_name = body.get("client_name")
    redirect_uris = body.get("redirect_uris")

    grant_types = body.get("grant_types", ["authorization_code", "refresh_token"])
    if set(grant_types) - {"authorization_code", "refresh_token"}:
        return jsonify({"error": "invalid_client_metadata",
                         "error_description": "Only authorization_code and refresh_token grant types are supported"}), 400

    response_types = body.get("response_types", ["code"])
    if response_types != ["code"]:
        return jsonify({"error": "invalid_client_metadata",
                         "error_description": "Only the 'code' response type is supported"}), 400

    auth_method = body.get("token_endpoint_auth_method", "none")
    if auth_method != "none":
        return jsonify({"error": "invalid_client_metadata",
                         "error_description": "Only public clients (token_endpoint_auth_method=none) are supported"}), 400

    try:
        client = OAuthClient.register(client_name=client_name, redirect_uris=redirect_uris)
    except ValueError as exc:
        return jsonify({"error": "invalid_client_metadata", "error_description": str(exc)}), 400

    return jsonify({
        "client_id": client.client_id,
        "client_name": client.client_name,
        "redirect_uris": client.redirect_uris,
        "token_endpoint_auth_method": client.token_endpoint_auth_method,
        "grant_types": client.grant_types,
        "response_types": client.response_types,
        "client_id_issued_at": int(client.created_at.timestamp()),
    }), 201
