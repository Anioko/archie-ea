"""POST /oauth/token (authorization_code + refresh_token grants) and
POST /oauth/revoke (RFC 7009).

Both routes are unauthenticated (a public client presents a code or a
refresh token, never a session) and are CSRF-exempt — see
``app.modules.oauth_provider.register`` for the ``csrf.exempt`` calls and
their ``VIEW_OPT_OUT`` reasons.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.modules.oauth_provider.models import (
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthToken,
    generate_token,
    hash_token,
)

token_bp = Blueprint("oauth_token", __name__)


def _error(error: str, description: str, status: int = 400):
    return jsonify({"error": error, "error_description": description}), status


def _expected_resource() -> str:
    return current_app.config["PUBLIC_BASE_URL"] + "/mcp"


def _issue_token_response(*, organization_id, user_id, client: OAuthClient, scope: str,
                           resource: str, grant_type: str):
    now = datetime.utcnow()
    plaintext_access = generate_token()
    plaintext_refresh = generate_token()

    token_row = OAuthToken(
        organization_id=organization_id,
        user_id=user_id,
        client_id=client.id,
        access_token_hash=hash_token(plaintext_access),
        refresh_token_hash=hash_token(plaintext_refresh),
        scope=scope,
        resource=resource,
        grant_type=grant_type,
        issued_at=now,
        access_token_expires_at=now + current_app.config["OAUTH_ACCESS_TOKEN_TTL"],
        refresh_token_expires_at=now + current_app.config["OAUTH_REFRESH_TOKEN_TTL"],
    )
    db.session.add(token_row)
    client.last_token_exchange_at = now
    db.session.commit()

    return jsonify({
        "access_token": plaintext_access,
        "token_type": "Bearer",
        "expires_in": int(current_app.config["OAUTH_ACCESS_TOKEN_TTL"].total_seconds()),
        "refresh_token": plaintext_refresh,
        "scope": scope,
    })


def _authorization_code_grant(resource: str):
    code = request.form.get("code")
    redirect_uri = request.form.get("redirect_uri")
    client_id = request.form.get("client_id")
    if not code or not redirect_uri or not client_id:
        return _error("invalid_request", "code, redirect_uri and client_id are required")

    client = OAuthClient.query.filter_by(client_id=client_id).first()
    if client is None:
        return _error("invalid_client", "Unknown client_id")

    code_row = OAuthAuthorizationCode.query.filter_by(code_hash=hash_token(code)).first()
    if code_row is None or code_row.client_id != client.id:
        return _error("invalid_grant", "Unknown authorization code")
    if code_row.is_used or code_row.is_expired:
        return _error("invalid_grant", "Authorization code is expired or already used")
    if code_row.redirect_uri != redirect_uri:
        return _error("invalid_grant", "redirect_uri does not match the authorization request")
    if code_row.resource != resource:
        return _error("invalid_target", "resource does not match the authorization request")

    code_row.used_at = datetime.utcnow()
    db.session.flush()

    return _issue_token_response(
        organization_id=code_row.organization_id,
        user_id=code_row.user_id,
        client=client,
        scope=code_row.scope,
        resource=resource,
        grant_type="authorization_code",
    )


def _refresh_token_grant(resource: str):
    refresh_token_value = request.form.get("refresh_token")
    client_id = request.form.get("client_id")
    if not refresh_token_value or not client_id:
        return _error("invalid_request", "refresh_token and client_id are required")

    client = OAuthClient.query.filter_by(client_id=client_id).first()
    if client is None:
        return _error("invalid_client", "Unknown client_id")

    old_token = OAuthToken.query.filter_by(refresh_token_hash=hash_token(refresh_token_value)).first()
    if old_token is None or old_token.client_id != client.id:
        return _error("invalid_grant", "Unknown refresh token")
    if old_token.is_revoked or old_token.is_refresh_token_expired:
        return _error("invalid_grant", "Refresh token is expired or revoked")
    if old_token.resource != resource:
        return _error("invalid_target", "resource does not match the original grant")

    old_token.revoke()

    return _issue_token_response(
        organization_id=old_token.organization_id,
        user_id=old_token.user_id,
        client=client,
        scope=old_token.scope,
        resource=resource,
        grant_type="refresh_token",
    )


@token_bp.route("/oauth/token", methods=["POST"])
def token():
    grant_type = request.form.get("grant_type")
    resource = request.form.get("resource")
    if not resource or resource != _expected_resource():
        return _error("invalid_target", "resource is required and must match this server's MCP resource")

    if grant_type == "authorization_code":
        return _authorization_code_grant(resource)
    if grant_type == "refresh_token":
        return _refresh_token_grant(resource)
    return _error("unsupported_grant_type", f"Unsupported grant_type: {grant_type!r}")


@token_bp.route("/oauth/revoke", methods=["POST"])
def revoke():
    """RFC 7009 — always 200, whether or not the token was found."""
    token_value = request.form.get("token")
    if not token_value:
        return _error("invalid_request", "token is required")

    token_hash = hash_token(token_value)
    row = OAuthToken.query.filter(
        db.or_(
            OAuthToken.access_token_hash == token_hash,
            OAuthToken.refresh_token_hash == token_hash,
        )
    ).first()
    if row is not None:
        row.revoke()
        db.session.commit()

    return ("", 200)
