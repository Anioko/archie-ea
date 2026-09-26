"""GET/POST /oauth/authorize — the consent screen and code issuance.

The GET request validates the client/redirect_uri/resource/scope and stores
the validated request in the session (never trusts a re-posted hidden
field for anything security-relevant). The POST request reads that pending
request back, requires an explicit decision=allow|deny from a button, and
on allow issues a single-use authorization code.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models.user import Permission
from app.modules.oauth_provider.models import (
    OAuthAuthorizationCode,
    OAuthClient,
    generate_token,
    hash_token,
)

authorize_bp = Blueprint("oauth_authorize", __name__)

_SESSION_KEY = "oauth_pending_authorization"


def _append_query(uri: str, params: dict) -> str:
    """Add *params* to *uri*, merging correctly when it already has a query."""
    parts = urlsplit(uri)
    query = dict(parse_qsl(parts.query))
    query.update({k: v for k, v in params.items() if v is not None})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _error_response(error: str, description: str, status: int = 400):
    return jsonify({"error": error, "error_description": description}), status


def _expected_resource() -> str:
    return current_app.config["PUBLIC_BASE_URL"] + "/mcp"


@authorize_bp.route("/oauth/authorize", methods=["GET"])
@login_required
def authorize():
    response_type = request.args.get("response_type")
    client_id = request.args.get("client_id", "")
    redirect_uri = request.args.get("redirect_uri", "")
    scope = request.args.get("scope", "")
    state = request.args.get("state", "")
    resource = request.args.get("resource", "")

    client = OAuthClient.query.filter_by(client_id=client_id).first()
    if client is None:
        return _error_response("invalid_client", "Unknown client_id")

    if redirect_uri not in (client.redirect_uris or []):
        # Never redirect to an unregistered URI — that is an open redirect.
        return _error_response("invalid_request", "redirect_uri is not registered for this client")

    if response_type != "code":
        return redirect(_append_query(redirect_uri, {"error": "unsupported_response_type", "state": state}))

    if not resource or resource != _expected_resource():
        return redirect(_append_query(redirect_uri, {"error": "invalid_target", "state": state}))

    requested_scopes = [s for s in scope.split(" ") if s]
    allowed_scopes = set(current_app.config.get("OAUTH_SUPPORTED_SCOPES", ()))
    if not set(requested_scopes).issubset(allowed_scopes):
        return redirect(_append_query(redirect_uri, {"error": "invalid_scope", "state": state}))

    session[_SESSION_KEY] = {
        "client_id": client.client_id,
        "redirect_uri": redirect_uri,
        "scope": requested_scopes,
        "state": state,
        "resource": resource,
    }

    may_propose = "mcp:propose" in requested_scopes and current_user.can(Permission.GENERAL)

    return render_template(
        "oauth/consent.html",
        client_name=client.client_name,
        organization_name=(current_user.organization.name if current_user.organization else ""),
        scopes=requested_scopes,
        may_propose=may_propose,
    )


@authorize_bp.route("/oauth/authorize", methods=["POST"])
@login_required
def authorize_decision():
    pending = session.get(_SESSION_KEY)
    if not pending:
        abort(400, description="No pending authorization request for this session")

    decision = request.form.get("decision")
    redirect_uri = pending["redirect_uri"]
    state = pending["state"]

    if decision not in ("allow", "deny"):
        abort(400, description="decision must be 'allow' or 'deny'")

    if decision == "deny":
        session.pop(_SESSION_KEY, None)
        return redirect(_append_query(redirect_uri, {"error": "access_denied", "state": state}))

    client = OAuthClient.query.filter_by(client_id=pending["client_id"]).first()
    if client is None:
        session.pop(_SESSION_KEY, None)
        abort(400, description="Client no longer registered")

    granted_scopes = []
    if "mcp:read" in pending["scope"]:
        granted_scopes.append("mcp:read")
    if (
        "mcp:propose" in pending["scope"]
        and request.form.get("grant_propose") == "on"
        and current_user.can(Permission.GENERAL)
    ):
        granted_scopes.append("mcp:propose")

    plaintext_code = generate_token()
    code_row = OAuthAuthorizationCode(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        client_id=client.id,
        code_hash=hash_token(plaintext_code),
        redirect_uri=redirect_uri,
        scope=" ".join(granted_scopes),
        resource=pending["resource"],
        expires_at=datetime.utcnow() + current_app.config["OAUTH_AUTHORIZATION_CODE_TTL"],
    )
    db.session.add(code_row)
    db.session.commit()
    session.pop(_SESSION_KEY, None)

    return redirect(_append_query(redirect_uri, {"code": plaintext_code, "state": state}))
