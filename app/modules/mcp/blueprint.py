"""POST /mcp — the assistant (MCP) connector endpoint.

Authenticates through the bearer identity loader only
(``app.modules.oauth_provider.identity``): a session cookie with no bearer
token is anonymous here, exactly as it would be for any other unauthenticated
caller. Every error returns a fixed message; the real exception is logged,
never returned.
"""
from __future__ import annotations

import time

from flask import Blueprint, current_app, g, jsonify, request
from flask_login import current_user

from app.modules.mcp.tools import TOOL_REGISTRY
from app.services.usage_metering_service import UsageMeteringService

mcp_bp = Blueprint("mcp", __name__)

GENERIC_ERROR_MESSAGE = "Internal error"


def _resource_metadata_url() -> str:
    return current_app.config["PUBLIC_BASE_URL"] + "/.well-known/oauth-protected-resource/mcp"


def _unauthorized():
    resp = jsonify({"error": "unauthorized"})
    resp.status_code = 401
    resp.headers["WWW-Authenticate"] = f'Bearer resource_metadata="{_resource_metadata_url()}"'
    return resp


def _bearer_token_from_request() -> str:
    auth_header = request.headers.get("Authorization", "")
    return auth_header[len("Bearer "):].strip() if auth_header.startswith("Bearer ") else ""


@mcp_bp.route("/mcp", methods=["GET"])
def mcp_get():
    return jsonify({"error": "method_not_allowed"}), 405


@mcp_bp.route("/mcp", methods=["POST"])
def mcp_endpoint():
    # A session cookie alone (no bearer) leaves the caller anonymous here:
    # current_user.is_authenticated alone isn't enough, since a browser
    # session cookie makes that True too — g.oauth_token is only ever set
    # by the bearer identity loader, never by the ordinary session loader.
    if not current_user.is_authenticated or getattr(g, "oauth_token", None) is None:
        return _unauthorized()

    origin = request.headers.get("Origin")
    if origin is not None:
        allowed_origins = current_app.config.get("MCP_ALLOWED_ORIGINS", ())
        if origin not in allowed_origins:
            return jsonify({"error": "forbidden_origin"}), 403

    protocol_version = request.headers.get("Mcp-Protocol-Version")
    supported_versions = current_app.config.get("MCP_SUPPORTED_PROTOCOL_VERSIONS", ())
    if not protocol_version or protocol_version not in supported_versions:
        return jsonify({"error": "unsupported_protocol_version"}), 400

    body = request.get_json(silent=True)
    if isinstance(body, list):
        return jsonify({"error": "batch_requests_not_supported"}), 400
    if not isinstance(body, dict) or "method" not in body:
        return jsonify({"error": "invalid_request"}), 400

    method = body.get("method")
    request_id = body.get("id")

    mcp_method_header = request.headers.get("Mcp-Method")
    if mcp_method_header is not None and mcp_method_header != method:
        return jsonify({"error": "mcp_method_mismatch"}), 400

    if method == "notifications/initialized":
        return ("", 202)

    try:
        if method == "initialize":
            return jsonify(_handle_initialize(request_id))
        if method == "tools/list":
            return jsonify(_handle_tools_list(request_id))
        if method == "tools/call":
            return _handle_tools_call(request_id, body.get("params") or {})
        return jsonify(_jsonrpc_error(request_id, -32601, "Method not found")), 400
    except Exception:
        current_app.logger.exception("Unhandled error in /mcp (method=%s)", method)
        return jsonify(_jsonrpc_error(request_id, -32603, GENERIC_ERROR_MESSAGE)), 500


def _jsonrpc_error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _handle_initialize(request_id):
    supported_versions = current_app.config.get("MCP_SUPPORTED_PROTOCOL_VERSIONS", ())
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": supported_versions[0] if supported_versions else None,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "archie-mcp", "version": "1.0.0"},
        },
    }


def _handle_tools_list(request_id):
    tools = [
        {
            "name": tool.name,
            "title": tool.title,
            "description": tool.description,
            "inputSchema": tool.input_schema,
        }
        for tool in TOOL_REGISTRY.values()
    ]
    return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}


def _handle_tools_call(request_id, params):
    tool_name = params.get("name")
    arguments = params.get("arguments") or {}

    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return jsonify(_jsonrpc_error(request_id, -32602, "Unknown tool")), 400

    # Scope check runs before any tool lookup/execution below.
    token = getattr(g, "oauth_token", None)
    granted_scopes = token.scopes() if token is not None else []
    if tool.required_scope not in granted_scopes:
        return jsonify({"error": "insufficient_scope"}), 403

    bearer = _bearer_token_from_request()
    start = time.monotonic()
    result = tool.call(arguments, bearer)
    latency_ms = (time.monotonic() - start) * 1000

    is_error = not result.ok
    body = result.json if result.json is not None else {"raw": result.raw_body.decode("utf-8", "replace")}

    UsageMeteringService.record(
        org_id=getattr(current_user, "organization_id", None),
        user_id=getattr(current_user, "id", None),
        event_type="mcp_tool_call",
        resource_type=tool.name,
        resource_id=tool.source_id(arguments, result),
        metadata={
            "outcome": "error" if is_error else "success",
            "status": result.status_code,
            "latency_ms": round(latency_ms, 2),
            "bytes": result.bytes_returned,
        },
    )

    content = [{"type": "text", "text": _to_json_text(body)}]
    return jsonify({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": content,
            "structuredContent": body,
            "isError": is_error,
        },
    })


def _to_json_text(body) -> str:
    import json
    return json.dumps(body)
