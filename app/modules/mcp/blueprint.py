"""MCP Streamable HTTP blueprint.

A single POST endpoint at /mcp that accepts JSON-RPC messages and dispatches
to the registered tool handlers. Every tool call executes inside a real Flask
request carrying an authenticated ``current_user`` resolved from the OAuth
bearer token.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request, url_for
from flask_login import current_user

from app.modules.oauth_provider.models import OAuthToken
from app.modules.mcp.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)

mcp_bp = Blueprint("mcp", __name__, url_prefix="/mcp")

# JSON-RPC 2.0 error codes
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603

#: The only scope a token needs to call this server — kept in one place so
#: the check at the door matches what /oauth/authorize is willing to grant.
REQUIRED_SCOPE = "mcp:read"


def _resolve_bearer_token() -> OAuthToken | None:
    """Resolve the current request's Bearer token to an OAuthToken.

    Returns None if no valid, correctly-scoped token is present.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    access_token = auth_header[7:].strip()
    if not access_token:
        return None
    token = OAuthToken.find_by_access_token(access_token)
    if token is None:
        return None
    if not token.is_active:
        return None
    if REQUIRED_SCOPE not in (token.scope or "").split():
        return None
    # Update last_used_at — an intentional write for token usage tracking
    # so that idle tokens can be identified and revoked.
    token.last_used_at = datetime.now(timezone.utc)
    from app.extensions import db
    db.session.flush()
    return token


def _authenticate_request() -> bool:
    """Authenticate the current request via Bearer token.

    Resolves ``current_user`` for the rest of this request without touching
    the Flask session: no session cookie, no remember-me cookie, and no
    ``user_logged_in`` signal, because a read-only bearer credential is not a
    browser login. flask-login reads ``g._login_user`` directly once it is
    set (its own ``_get_user()`` only falls back to loading from the session
    when that attribute is absent), so this is honoured for the rest of this
    request and by any nested ``call_internal_api()`` call it makes, which
    runs inside the same app context and therefore shares this ``g``.

    Also sets g.current_org_id and the database tenant context, because the
    before_request handler runs before this view function and cannot
    see the yet-to-be-authenticated user. Returns True if authentication
    succeeded.
    """
    token = _resolve_bearer_token()
    if token is None:
        return False

    from app.models.user import User
    from app.extensions import db
    user = db.session.get(User, token.user_id)
    if user is None or not getattr(user, "is_active", True):
        return False

    g._login_user = user

    # Re-establish tenant context now that current_user is set.
    # The before_request handler ran before authentication and left
    # g.current_org_id = None; we must set it here so that metering
    # and tenant isolation work correctly for the remainder of the request.
    if hasattr(user, "organization_id"):
        g.current_org_id = user.organization_id
        g.current_org = getattr(user, "organization", None)
        from app.middleware.tenant_isolation import set_database_tenant_context
        set_database_tenant_context(db.session.connection(), g.current_org_id)

    return True


def _jsonrpc_error(id_, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _jsonrpc_result(id_, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _unauthenticated_response(req_id):
    """401 with the WWW-Authenticate header a standards MCP client needs to
    discover the authorization server (RFC 9728 / RFC 6750)."""
    resp = jsonify(_jsonrpc_error(req_id, JSONRPC_INTERNAL_ERROR, "Authentication required"))
    resp.status_code = 401
    metadata_url = url_for("oauth_metadata.protected_resource_metadata", _external=True)
    resp.headers["WWW-Authenticate"] = f'Bearer resource_metadata="{metadata_url}"'
    return resp


@mcp_bp.route("", methods=["POST"])
def mcp_endpoint():
    """Streamable HTTP MCP endpoint — accepts JSON-RPC messages."""
    # Validate Origin header for DNS rebinding protection. Only a browser
    # ever sends this header, so its absence (the normal case for a non-
    # browser assistant client) is not itself suspicious and is left alone.
    # When it IS present, MCP_ALLOWED_ORIGIN is an explicit override; unset
    # does not mean "accept any origin" — it falls back to this server's own
    # origin, which is what a same-origin browser request would send anyway.
    origin = request.headers.get("Origin", "")
    if origin:
        from app.modules.oauth_provider.models import resolve_server_base_url
        allowed_origin = current_app.config.get("MCP_ALLOWED_ORIGIN") or resolve_server_base_url()
        if origin != allowed_origin:
            return jsonify({"error": "forbidden"}), 403

    try:
        body = request.get_json(silent=True)
        if body is None:
            return jsonify(_jsonrpc_error(None, JSONRPC_PARSE_ERROR, "Parse error")), 400
    except Exception:
        return jsonify(_jsonrpc_error(None, JSONRPC_PARSE_ERROR, "Parse error")), 400

    req_id = body.get("id")
    method = body.get("method", "")

    # Handle MCP lifecycle methods
    if method == "initialize":
        return jsonify(_jsonrpc_result(req_id, {
            "protocolVersion": "2025-11-25",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "entelim", "version": "1.0.0"},
        }))

    if method == "notifications/initialized":
        return jsonify(_jsonrpc_result(req_id, {}))

    if method == "tools/list":
        if not _authenticate_request():
            return _unauthenticated_response(req_id)
        tools = []
        for name, handler in sorted(TOOL_REGISTRY.items()):
            tools.append({
                "name": name,
                "description": handler.description,
                "inputSchema": handler.input_schema,
                "annotations": handler.annotations,
            })
        return jsonify(_jsonrpc_result(req_id, {"tools": tools}))

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Authenticate before revealing anything about which tool names
        # exist — checking existence first let an unauthenticated caller
        # enumerate the (admittedly static) tool list for free.
        if not _authenticate_request():
            return _unauthenticated_response(req_id)

        if tool_name not in TOOL_REGISTRY:
            return jsonify(_jsonrpc_error(req_id, JSONRPC_METHOD_NOT_FOUND,
                                          f"Tool not found: {tool_name}")), 404

        handler = TOOL_REGISTRY[tool_name]

        # Meter the call
        try:
            from app.services.usage_metering_service import UsageMeteringService
            UsageMeteringService.record(
                org_id=g.current_org_id,
                user_id=current_user.id,
                event_type="mcp_tool_call",
                resource_type=tool_name,
            )
        except Exception:
            pass  # Metering never raises

        start = time.monotonic()
        try:
            result = handler.execute(arguments)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            logger.info(
                "mcp_tool_call tool=%s org=%s user=%s elapsed_ms=%d",
                tool_name, g.current_org_id, current_user.id, elapsed_ms,
            )

            return jsonify(_jsonrpc_result(req_id, {
                "content": [{"type": "text", "text": json.dumps(result)}],
            }))
        except Exception:
            # The real exception is logged server-side only — returning
            # str(exc) to the caller can leak internal state (an attribute
            # error naming a class, a query fragment, a file path).
            logger.exception("mcp_tool_call tool=%s failed", tool_name)
            return jsonify(_jsonrpc_error(req_id, JSONRPC_INTERNAL_ERROR,
                                          "Tool execution failed")), 500

    # Unknown method
    return jsonify(_jsonrpc_error(req_id, JSONRPC_METHOD_NOT_FOUND,
                                  f"Method not found: {method}")), 404


@mcp_bp.route("", methods=["GET"])
def mcp_get():
    """GET on the MCP endpoint — returns server metadata for SSE discovery."""
    return jsonify({
        "protocolVersion": "2025-11-25",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "entelim", "version": "1.0.0"},
    })