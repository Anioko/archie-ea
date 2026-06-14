"""Lucidchart OAuth and import helper routes."""

from __future__ import annotations

import json
import uuid

from flask import Blueprint, jsonify, request, session, url_for
from flask_login import current_user, login_required
from werkzeug.routing import BuildError

from app.services.lucid_archimate_transformer import LucidArchiMateTransformer
from app.services.lucidchart_connector_service import (
    LucidchartConnectorError,
    LucidchartConnectorService,
)
from app.utils.response_helpers import api_error, api_success


lucidchart_import_bp = Blueprint(
    "lucidchart_import",
    __name__,
    url_prefix="/archimate/lucidchart",
)

_service = LucidchartConnectorService()
_transformer = LucidArchiMateTransformer()


def _current_org_id() -> int:
    org_id = getattr(current_user, "organization_id", None)
    if org_id is None:
        raise LucidchartConnectorError("Current user is not scoped to an organization.")
    return int(org_id)


def _callback_url() -> str:
    """External OAuth callback URL.

    These handlers are registered as aliases on ``archimate_bp`` (via
    ``register_lucidchart_import_routes``); the standalone ``lucidchart_import``
    blueprint is not always registered. Build the URL for whichever endpoint
    actually exists so the OAuth start does not 500 with a BuildError once a
    connector config is present. The resolved URL is the redirect URI to
    register with the Lucid OAuth app.
    """
    for endpoint in (
        "archimate.api_lucidchart_auth_callback",
        "lucidchart_import.lucidchart_oauth_callback",
    ):
        try:
            return url_for(endpoint, _external=True)
        except BuildError:
            continue
    raise BuildError("lucidchart auth callback", {}, "GET")


def _needs_auth_response() -> tuple:
    return jsonify({"needs_auth": True, "documents": []}), 200


def _current_org_id_or_error():
    try:
        return _current_org_id(), None
    except LucidchartConnectorError as exc:
        return None, exc


def _import_payload_response(transformed: dict) -> tuple:
    elements = transformed.get("elements") or []
    relationships = transformed.get("relationships") or []
    return jsonify(
        {
            "elements": elements,
            "relationships": relationships,
            "stats": {
                "elements": len(elements),
                "relationships": len(relationships),
                "elements_created": len(elements),
                "elements_linked": 0,
                "relationships_created": len(relationships),
            },
            "warnings": transformed.get("warnings") or [],
            "layout_hints": transformed.get("layout_hints") or {},
            "model_name": transformed.get("model_name"),
        }
    ), 200


def _extract_lucid_zip(raw: bytes) -> dict:
    """A native ``.lucid`` file is a ZIP archive containing ``document.json``
    (Lucid Standard Import format). Extract and parse that document."""
    import io
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = archive.namelist()
            target = next(
                (n for n in names if n.lower().rstrip("/").endswith("document.json")),
                None,
            ) or next((n for n in names if n.lower().endswith(".json")), None)
            if target is None:
                raise LucidchartConnectorError(
                    "The .lucid archive does not contain a document.json."
                )
            data = archive.read(target)
    except zipfile.BadZipFile as exc:
        raise LucidchartConnectorError(
            "The .lucid file is not a readable ZIP archive."
        ) from exc

    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LucidchartConnectorError(
            "The .lucid archive's document.json is not valid JSON."
        ) from exc


def _load_uploaded_payload() -> dict:
    uploaded = request.files.get("file")
    if uploaded is not None:
        filename = (uploaded.filename or "").lower()
        if filename and not filename.endswith((".json", ".lucid")):
            raise LucidchartConnectorError(
                "Lucidchart upload must be a .json or .lucid file."
            )
        raw = uploaded.read()
        # Lucid caps a .lucid archive at 50MB; allow the same headroom.
        if len(raw) > 50 * 1024 * 1024:
            raise LucidchartConnectorError("Lucidchart upload exceeds the 50MB limit.")
        # Native .lucid files are ZIP archives (PK signature) regardless of the
        # extension; a plain Lucid JSON export is parsed directly.
        if raw[:2] == b"PK":
            return _extract_lucid_zip(raw)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LucidchartConnectorError(
                "Lucidchart upload is not valid JSON or a .lucid archive."
            ) from exc

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise LucidchartConnectorError(
            "Provide a Lucidchart JSON payload via multipart upload or JSON body."
        )
    return payload


@lucidchart_import_bp.route("/auth/start", methods=["GET"])
@login_required
def lucidchart_oauth_start():
    org_id, org_error = _current_org_id_or_error()
    if org_error is not None:
        return api_error(str(org_error), 400)
    config = _service.get_config(org_id)
    if config is None:
        return api_error("Lucidchart is not configured for this organization.", 404)

    state = str(uuid.uuid4())
    session["lucidchart_oauth_state"] = state
    authorization_url = _service.build_authorization_url(
        config=config,
        redirect_uri=_callback_url(),
        state=state,
    )
    return api_success({"authorization_url": authorization_url, "state": state})


@lucidchart_import_bp.route("/auth/callback", methods=["GET"])
@login_required
def lucidchart_oauth_callback():
    org_id, org_error = _current_org_id_or_error()
    if org_error is not None:
        return api_error(str(org_error), 400)
    error = request.args.get("error")
    if error:
        description = request.args.get("error_description") or error
        return api_error(f"Lucidchart authorization failed: {description}", 400)

    code = request.args.get("code")
    state = request.args.get("state")
    expected_state = session.pop("lucidchart_oauth_state", None)
    if not code:
        return api_error("Lucidchart callback is missing authorization code.", 400)
    if not state or state != expected_state:
        return api_error("Lucidchart callback state did not match the active session.", 400)

    config = _service.get_or_create_config(org_id)
    token_payload = _service.exchange_code_for_tokens(
        config=config,
        code=code,
        redirect_uri=_callback_url(),
    )
    return api_success(
        {
            "connected": True,
            "scope": config.scope,
            "lucid_account_id": config.lucid_account_id,
            "token_expires_at": (
                config.token_expires_at.isoformat()
                if config.token_expires_at
                else None
            ),
            "token_payload_keys": sorted(token_payload.keys()),
        }
    )


@lucidchart_import_bp.route("/documents", methods=["GET"])
@login_required
def lucidchart_list_documents():
    org_id, org_error = _current_org_id_or_error()
    if org_error is not None:
        return _needs_auth_response()
    config = _service.get_config(org_id)
    if config is None or not config.enabled or not config.access_token:
        return jsonify({"needs_auth": True, "documents": []}), 200

    query = request.args.get("q", type=str)
    try:
        documents = _service.list_documents(config, query=query)
    except LucidchartConnectorError:
        return _needs_auth_response()
    return api_success({"needs_auth": False, "documents": documents})


@lucidchart_import_bp.route("/documents/<string:document_id>/contents", methods=["GET"])
@login_required
def lucidchart_document_contents(document_id: str):
    org_id, org_error = _current_org_id_or_error()
    if org_error is not None:
        return jsonify({"needs_auth": True}), 200
    config = _service.get_config(org_id)
    if config is None or not config.enabled or not config.access_token:
        return jsonify({"needs_auth": True}), 200

    contents = _service.get_document_contents(config, document_id=document_id)
    return api_success({"needs_auth": False, "document": contents})


def register_lucidchart_import_routes(bp: Blueprint) -> None:
    """Attach composer-facing Lucidchart import routes to an existing blueprint."""

    @bp.route("/api/lucidchart/auth/start", methods=["GET"])
    @login_required
    def api_lucidchart_auth_start():
        return lucidchart_oauth_start()

    @bp.route("/api/lucidchart/auth/callback", methods=["GET"])
    @login_required
    def api_lucidchart_auth_callback():
        return lucidchart_oauth_callback()

    @bp.route("/api/lucidchart/documents", methods=["GET"])
    @login_required
    def api_lucidchart_documents():
        org_id, org_error = _current_org_id_or_error()
        if org_error is not None:
            return _needs_auth_response()
        config = _service.get_config(org_id)
        if config is None or not config.enabled or not config.access_token:
            return _needs_auth_response()

        query = request.args.get("q", type=str)
        try:
            documents = _service.list_documents(config, query=query)
        except LucidchartConnectorError:
            return _needs_auth_response()
        return jsonify({"needs_auth": False, "documents": documents}), 200

    @bp.route("/api/lucidchart/import/<string:document_id>", methods=["POST"])
    @login_required
    def api_lucidchart_import_document(document_id: str):
        org_id, org_error = _current_org_id_or_error()
        if org_error is not None:
            return jsonify({"needs_auth": True}), 200
        config = _service.get_config(org_id)
        if config is None or not config.enabled or not config.access_token:
            return jsonify({"needs_auth": True}), 200

        try:
            document = _service.get_document_contents(config, document_id=document_id)
        except LucidchartConnectorError:
            return jsonify({"needs_auth": True}), 200
        transformed = _transformer.transform_document(document)
        return _import_payload_response(transformed)

    @bp.route("/api/lucidchart/import/upload", methods=["POST"])
    @login_required
    def api_lucidchart_import_upload():
        payload = _load_uploaded_payload()
        transformed = _transformer.transform_document(payload)
        return _import_payload_response(transformed)


register_lucidchart_import_routes(lucidchart_import_bp)
