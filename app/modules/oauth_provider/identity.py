"""Bearer-token identity for /mcp and internal-bridge requests.

This is a Flask-Login ``request_loader``, not a session mechanism: it is
consulted only when there is no logged-in session user, it never calls
``login_user()``, and it never writes anything to the session. It only
activates for requests that are either headed to /mcp or carry the
in-process bridge marker (see ``app.utils.internal_api``) — a bearer header
sent to any other route leaves the request anonymous, exactly like today.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import current_app, g, request

from app.extensions import db, login_manager
from app.modules.oauth_provider.models import OAuthToken, hash_token

_LAST_USED_UPDATE_INTERVAL = timedelta(minutes=1)


def _is_bearer_eligible_request(req) -> bool:
    if req.path == "/mcp" or req.path.startswith("/mcp/"):
        return True
    # Set only by app.utils.internal_api.call_internal_api — a WSGI environ
    # key, never derived from an incoming HTTP header, so an external
    # request cannot forge it.
    return req.environ.get("archie.internal_bridge") is True


def load_user_from_bearer(req):
    """Flask-Login request_loader entry point."""
    if not current_app.config.get("MCP_ENABLED"):
        return None
    if not _is_bearer_eligible_request(req):
        return None

    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    plaintext = auth_header[len("Bearer "):].strip()
    if not plaintext:
        return None

    token = OAuthToken.query.filter_by(access_token_hash=hash_token(plaintext)).first()
    if token is None:
        return None
    if token.is_revoked:
        return None
    if token.is_access_token_expired:
        return None

    expected_resource = current_app.config.get("PUBLIC_BASE_URL", "") + "/mcp"
    if token.resource != expected_resource:
        return None

    from app.models.user import User

    user = db.session.get(User, token.user_id)
    if user is None:
        return None
    if user.organization_id != token.organization_id:
        return None

    now = datetime.utcnow()
    if token.last_used_at is None or (now - token.last_used_at) >= _LAST_USED_UPDATE_INTERVAL:
        token.last_used_at = now
        db.session.commit()

    g.current_org_id = user.organization_id
    g.oauth_token = token
    return user


def register_bearer_identity(app) -> None:
    login_manager.request_loader(load_user_from_bearer)
