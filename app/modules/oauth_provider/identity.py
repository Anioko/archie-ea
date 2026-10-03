"""Bearer-token identity resolution for the MCP endpoint.

This is a flask-login ``request_loader`` — the seam flask-login calls when a
request carries no session cookie. It resolves ``current_user`` from an
``Authorization: Bearer`` header for exactly two kinds of request:

* a direct call to the public ``/mcp`` endpoint, and
* an internal bridge call (``app.utils.internal_api.call_internal_api`` in
  bearer mode) made on that same caller's behalf, identified by the
  ``MCP_BRIDGE_MARKER`` header this module defines and the bridge sets.

Every other request is left alone — the loader returns ``None`` and whatever
session-cookie handling already exists proceeds exactly as before. The loader
never calls ``login_user()`` and never touches the session: flask-login's
request-loader contract is already "resolve a user for *this* request only,"
which is exactly the no-session-written behaviour a bearer-authenticated API
caller needs.

Registered unconditionally at boot (see ``app/_bootstrap/blueprints.py``), but
inert — returns ``None`` immediately — while ``MCP_ENABLED`` is false, so the
mechanism exists in every build but only acts when the feature is turned on.
"""

from __future__ import annotations

from flask import current_app, g, request

from app.extensions import login_manager

# The header an internal bridge call sets to mark itself as carrying a
# caller's bearer token on the caller's behalf, so this loader authenticates
# the *inner* request the same way it authenticated the outer one.
# app.utils.internal_api.call_internal_api's bearer mode sets this header;
# nothing outside the bridge should ever send it, since the real guard is
# that the header alone grants nothing — the Authorization header still has
# to carry a valid bearer token.
MCP_BRIDGE_MARKER_HEADER = "X-Entelim-MCP-Bridge"
MCP_BRIDGE_MARKER_VALUE = "internal-bearer-bridge-v1"


def _is_mcp_scoped_request() -> bool:
    """True when this request is the public /mcp endpoint or a bridge call."""
    if request.path == "/mcp":
        return True
    return request.headers.get(MCP_BRIDGE_MARKER_HEADER) == MCP_BRIDGE_MARKER_VALUE


def load_user_from_bearer_token(req):
    """flask-login request_loader: resolve a user from an OAuth bearer token.

    Returns ``None`` for anything this loader should not touch — an unknown
    endpoint, no header, or any of the refusal conditions below — letting
    flask-login fall back to its usual anonymous-user handling.
    """
    if not current_app.config.get("MCP_ENABLED"):
        return None
    if not _is_mcp_scoped_request():
        return None

    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    raw_token = auth_header[len("Bearer "):].strip()
    if not raw_token:
        return None

    from app.modules.oauth_provider.models import OAuthToken

    token = OAuthToken.find_by_access_token(raw_token)
    if token is None:
        return None
    if not token.is_active:
        return None

    public_base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    expected_resource = f"{public_base}/mcp" if public_base else None
    if expected_resource is None or token.resource != expected_resource:
        return None

    from app.extensions import db
    from app.models.user import User

    user = db.session.get(User, token.user_id)
    if user is None:
        return None
    if not getattr(user, "is_active", True):
        return None
    if getattr(user, "organization_id", None) != token.organization_id:
        return None

    token.touch_last_used()

    g.auth_mode = "bearer"
    g.bearer_token = token
    return user


login_manager.request_loader(load_user_from_bearer_token)
