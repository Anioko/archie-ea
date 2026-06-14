"""
Integration Contract Service — CRUD + versioning for spec_data.integrations.

Stores integration contracts keyed by target element ID on the source element's
SolutionArchiMateElement.spec_data.integrations dict.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone

from app import db
from app.models.solution_archimate_element import SolutionArchiMateElement

logger = logging.getLogger(__name__)


def _compute_hash(data):
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class IntegrationContractService:
    """Read/write integration contracts in SolutionArchiMateElement.spec_data.integrations."""

    def get_contracts(self, junction_id):
        """Return all integration contracts for a junction, keyed by target element ID."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            return {}
        return j.spec_data.get("integrations", {})

    def get_contract(self, junction_id, target_element_id):
        """Return a single integration contract for a specific target."""
        contracts = self.get_contracts(junction_id)
        return contracts.get(str(target_element_id))

    def save_contract(self, junction_id, target_element_id, contract, user_id, generated_by="user", model_used=None):
        """Save or update an integration contract for a target element."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j:
            raise ValueError(f"Junction {junction_id} not found")

        spec = dict(j.spec_data or {})
        integrations = dict(spec.get("integrations", {}))
        target_key = str(target_element_id)

        existing = integrations.get(target_key, {})
        old_version = existing.get("version", 0)
        new_version = old_version + 1

        # Store history
        history_key = f"integration_history_{target_key}"
        history = list(spec.get(history_key, []))
        if existing:
            history.append({
                "version": old_version,
                "contract": existing,
                "archived_at": _utcnow_iso(),
            })
        spec[history_key] = history

        # Write new version
        contract_data = dict(contract)
        contract_data["version"] = new_version
        contract_data["status"] = "proposed"
        contract_data["contract_hash"] = _compute_hash(contract)
        contract_data["provenance"] = {
            "generated_by": generated_by,
            "saved_by": user_id,
            "saved_at": _utcnow_iso(),
            "model_used": model_used,
        }

        integrations[target_key] = contract_data
        spec["integrations"] = integrations
        j.spec_data = spec
        db.session.commit()

        return {
            "version": new_version,
            "status": "proposed",
            "contract_hash": contract_data["contract_hash"],
            "provenance": contract_data["provenance"],
        }

    def confirm_contract(self, junction_id, target_element_id, user_id):
        """Confirm a proposed integration contract."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            raise ValueError("No spec data")

        spec = dict(j.spec_data)
        integrations = dict(spec.get("integrations", {}))
        target_key = str(target_element_id)
        contract = integrations.get(target_key)
        if not contract:
            raise ValueError(f"No contract for target {target_element_id}")

        # Archive
        history_key = f"integration_history_{target_key}"
        history = list(spec.get(history_key, []))
        history.append({
            "version": contract.get("version", 0),
            "contract": dict(contract),
            "archived_at": _utcnow_iso(),
        })
        spec[history_key] = history

        # Confirm
        new_version = contract.get("version", 0) + 1
        contract_data = dict(contract)
        contract_data["version"] = new_version
        contract_data["status"] = "confirmed"
        contract_data["contract_hash"] = _compute_hash({
            k: v for k, v in contract_data.items()
            if k not in ("version", "status", "contract_hash", "provenance")
        })
        provenance = dict(contract_data.get("provenance", {}))
        provenance["confirmed_by"] = user_id
        provenance["confirmed_at"] = _utcnow_iso()
        contract_data["provenance"] = provenance

        integrations[target_key] = contract_data
        spec["integrations"] = integrations
        j.spec_data = spec
        db.session.commit()

        return {
            "version": new_version,
            "status": "confirmed",
            "contract_hash": contract_data["contract_hash"],
            "provenance": contract_data["provenance"],
        }

    def suggest_from_relationship(self, junction_id, relationship):
        """Suggest an integration contract from an existing ArchiMateRelationship.

        Reads global connection_spec as a starting point for solution-scoped contract.
        """
        suggestion = {
            "protocol": "REST",
            "auth_method": "bearer",
            "direction": "publish",
            "sla": {"availability": 99.5, "max_latency_ms": 500},
            "retry_policy": {"max_retries": 3, "backoff": "exponential"},
            "circuit_breaker": {"failure_threshold": 5, "timeout_ms": 30000},
            "error_handling": {"dead_letter_queue": False, "alert_on_failure": True},
        }

        if relationship and hasattr(relationship, "connection_spec") and relationship.connection_spec:
            cs = relationship.connection_spec
            if cs.get("protocol"):
                suggestion["protocol"] = cs["protocol"]
            if cs.get("auth_method"):
                suggestion["auth_method"] = cs["auth_method"]
            if cs.get("sla"):
                suggestion["sla"] = cs["sla"]

        return suggestion
