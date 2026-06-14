"""Integration Contract Registry API — RUNTIME-02.

CRUD endpoints for IntegrationContract: real API endpoints, auth config,
and SLA parameters that the code generator uses instead of placeholder URLs.

Blueprint: integration_contract_bp, prefix /api/enterprise
"""

import logging

import requests as http_requests
from flask import Blueprint, jsonify, request
from flask_login import login_required

from app import db
from app.models.integration_contract import (
    VALID_AUTH_METHODS,
    VALID_PROTOCOLS,
    VALID_SPEC_FORMATS,
    IntegrationContract,
)

logger = logging.getLogger(__name__)

integration_contract_bp = Blueprint(
    "integration_contract_api",
    __name__,
    url_prefix="/api/enterprise",
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _validate_contract_payload(data, is_update=False):
    """Return (cleaned_data, error_message). error_message is None on success."""
    if not is_update and not data.get("name"):
        return None, "name is required"

    cleaned = {}

    str_fields = [
        "name", "version", "base_url", "protocol", "auth_method",
        "spec_format", "spec_url", "sla_availability", "rate_limit",
        "owner_team", "documentation_url",
    ]
    for f in str_fields:
        if f in data:
            cleaned[f] = data[f]

    json_fields = ["auth_config", "spec_content", "environments"]
    for f in json_fields:
        if f in data:
            cleaned[f] = data[f]

    int_fields = ["application_id", "sla_latency_ms"]
    for f in int_fields:
        if f in data and data[f] is not None:
            try:
                cleaned[f] = int(data[f])
            except (ValueError, TypeError):
                return None, f"{f} must be an integer"

    # Validate enums
    if "protocol" in cleaned and cleaned["protocol"]:
        if cleaned["protocol"] not in VALID_PROTOCOLS:
            return None, f"protocol must be one of: {', '.join(sorted(VALID_PROTOCOLS))}"

    if "auth_method" in cleaned and cleaned["auth_method"]:
        if cleaned["auth_method"] not in VALID_AUTH_METHODS:
            return None, f"auth_method must be one of: {', '.join(sorted(VALID_AUTH_METHODS))}"

    if "spec_format" in cleaned and cleaned["spec_format"]:
        if cleaned["spec_format"] not in VALID_SPEC_FORMATS:
            return None, f"spec_format must be one of: {', '.join(sorted(VALID_SPEC_FORMATS))}"

    # Security: reject auth_config that contains actual secret values
    auth_cfg = cleaned.get("auth_config")
    if auth_cfg and isinstance(auth_cfg, dict):
        for key, val in auth_cfg.items():
            if isinstance(val, str) and key not in (
                "token_url", "authorize_url", "scope", "grant_type",
                "client_id_env", "client_secret_env", "api_key_env",
                "api_key_header", "username_env", "password_env",
                "cert_path_env", "key_path_env",
            ):
                # Allow env var references (ending in _env) and known URL fields
                if not key.endswith("_env") and "url" not in key.lower():
                    logger.warning(
                        "auth_config field %r may contain a secret — "
                        "use env var names (ending in _env) instead",
                        key,
                    )

    return cleaned, None


# ── CRUD ─────────────────────────────────────────────────────────────────


@integration_contract_bp.route("/contracts", methods=["POST"])
@login_required
def create_contract():
    """Create a new integration contract."""
    data = request.get_json(silent=True) or {}
    cleaned, err = _validate_contract_payload(data)
    if err:
        return jsonify({"error": err}), 400

    contract = IntegrationContract(**cleaned)
    db.session.add(contract)
    db.session.commit()

    logger.info("Created IntegrationContract id=%d name=%r", contract.id, contract.name)
    return jsonify(contract.to_dict()), 201


@integration_contract_bp.route("/contracts", methods=["GET"])
@login_required
def list_contracts():
    """List contracts with optional filters: ?q=, ?protocol=, ?application_id=, ?auth_method=."""
    query = IntegrationContract.query

    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(IntegrationContract.name.ilike(f"%{q}%"))

    protocol = request.args.get("protocol")
    if protocol:
        query = query.filter(IntegrationContract.protocol == protocol)

    auth_method = request.args.get("auth_method")
    if auth_method:
        query = query.filter(IntegrationContract.auth_method == auth_method)

    app_id = request.args.get("application_id")
    if app_id:
        try:
            query = query.filter(IntegrationContract.application_id == int(app_id))
        except (ValueError, TypeError):
            return jsonify({"error": "application_id must be an integer"}), 400

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)

    pagination = query.order_by(IntegrationContract.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False,
    )

    return jsonify({
        "items": [c.to_dict() for c in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    })


@integration_contract_bp.route("/contracts/<int:contract_id>", methods=["GET"])
@login_required
def get_contract(contract_id):
    """Get a single contract by ID."""
    contract = IntegrationContract.query.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404
    return jsonify(contract.to_dict())


@integration_contract_bp.route("/contracts/<int:contract_id>", methods=["PUT"])
@login_required
def update_contract(contract_id):
    """Update an existing contract."""
    contract = IntegrationContract.query.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404

    data = request.get_json(silent=True) or {}
    cleaned, err = _validate_contract_payload(data, is_update=True)
    if err:
        return jsonify({"error": err}), 400

    for key, value in cleaned.items():
        setattr(contract, key, value)

    db.session.commit()
    logger.info("Updated IntegrationContract id=%d", contract.id)
    return jsonify(contract.to_dict())


@integration_contract_bp.route("/contracts/<int:contract_id>", methods=["DELETE"])
@login_required
def delete_contract(contract_id):
    """Delete a contract."""
    contract = IntegrationContract.query.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404

    db.session.delete(contract)
    db.session.commit()
    logger.info("Deleted IntegrationContract id=%d", contract_id)
    return jsonify({"deleted": contract_id})


# ── Spec fetcher ─────────────────────────────────────────────────────────


@integration_contract_bp.route("/contracts/<int:contract_id>/fetch-spec", methods=["POST"])
@login_required
def fetch_spec(contract_id):
    """Fetch an OpenAPI/AsyncAPI spec from the contract's spec_url and store it."""
    contract = IntegrationContract.query.get(contract_id)
    if not contract:
        return jsonify({"error": "Contract not found"}), 404

    if not contract.spec_url:
        return jsonify({"error": "No spec_url configured on this contract"}), 400

    try:
        resp = http_requests.get(contract.spec_url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        spec_data = resp.json()
    except http_requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        return jsonify({
            "error": f"Spec URL returned {status}",
        }), 502
    except Exception as exc:
        return jsonify({"error": f"Failed to fetch spec: {exc}"}), 502

    contract.spec_content = spec_data
    # Auto-detect format from spec content
    if not contract.spec_format:
        if "openapi" in spec_data:
            contract.spec_format = "openapi"
        elif "asyncapi" in spec_data:
            contract.spec_format = "asyncapi"

    db.session.commit()
    logger.info(
        "Fetched spec for IntegrationContract id=%d from %s",
        contract.id, contract.spec_url,
    )
    return jsonify({
        "message": "Spec fetched and stored",
        "spec_format": contract.spec_format,
        "spec_keys": list(spec_data.keys()) if isinstance(spec_data, dict) else None,
    })


# ── Application-scoped listing ───────────────────────────────────────────


@integration_contract_bp.route(
    "/applications/<int:app_id>/contracts", methods=["GET"]
)
@login_required
def list_contracts_for_app(app_id):
    """List all contracts for a specific application."""
    contracts = (
        IntegrationContract.query
        .filter_by(application_id=app_id)
        .order_by(IntegrationContract.name)
        .all()
    )
    return jsonify({
        "application_id": app_id,
        "items": [c.to_dict() for c in contracts],
        "total": len(contracts),
    })
