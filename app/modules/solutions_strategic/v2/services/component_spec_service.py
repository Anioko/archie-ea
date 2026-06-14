"""
Component Specification Service — CRUD + versioning for spec_data on SolutionArchiMateElement.

Manages three tabs:
- fields (data model): spec_data.fields, spec_data.fields_hash, spec_data.fields_version, etc.
- api_contract: spec_data.api_contract, spec_data.contract_hash, etc.
- business_rules: spec_data.business_rules (list of structured rule objects)

All writes increment version, store history, compute hash, record provenance.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone

from app import db
from app.models.solution_archimate_element import SolutionArchiMateElement

logger = logging.getLogger(__name__)


def _compute_hash(data):
    """SHA-256 of canonical JSON for drift detection."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ComponentSpecService:
    """Read/write component specifications stored in SolutionArchiMateElement.spec_data."""

    # ── Fields (Tab A: Data Model) ─────────────────────────────────────

    def get_component_spec(self, junction_id):
        """Return full spec_data for a junction row, or None."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j:
            return None
        return j.spec_data

    def get_fields(self, junction_id):
        """Return fields section of spec_data, or None."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            return None
        return {
            "fields": j.spec_data.get("fields", []),
            "version": j.spec_data.get("fields_version", 0),
            "status": j.spec_data.get("fields_status", "proposed"),
            "fields_hash": j.spec_data.get("fields_hash"),
            "provenance": j.spec_data.get("fields_provenance", {}),
        }

    def save_fields(self, junction_id, fields, user_id, generated_by="user", model_used=None):
        """Save or update fields. Increments version, computes hash, records provenance.

        Args:
            junction_id: SolutionArchiMateElement.id
            fields: list of field dicts (name, type, format, required, description, constraints, etc.)
            user_id: current user ID
            generated_by: "user" or "llm"
            model_used: LLM model name if generated_by == "llm"

        Returns:
            dict with version, status, fields_hash, provenance
        """
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j:
            raise ValueError(f"Junction {junction_id} not found")

        spec = dict(j.spec_data or {})
        old_version = spec.get("fields_version", 0)
        new_version = old_version + 1

        # Store history
        history = list(spec.get("fields_history", []))
        if spec.get("fields"):
            history.append({
                "version": old_version,
                "fields": spec["fields"],
                "hash": spec.get("fields_hash"),
                "provenance": spec.get("fields_provenance", {}),
                "archived_at": _utcnow_iso(),
            })
        spec["fields_history"] = history

        # Write new version
        spec["fields"] = fields
        spec["fields_version"] = new_version
        spec["fields_status"] = "proposed"
        spec["fields_hash"] = _compute_hash(fields)
        spec["fields_provenance"] = {
            "generated_by": generated_by,
            "saved_by": user_id,
            "saved_at": _utcnow_iso(),
            "model_used": model_used,
        }

        j.spec_data = spec
        db.session.commit()

        return {
            "version": new_version,
            "status": "proposed",
            "fields_hash": spec["fields_hash"],
            "provenance": spec["fields_provenance"],
        }

    def confirm_fields(self, junction_id, user_id):
        """Confirm proposed fields. Sets status to 'confirmed', bumps version.

        Returns:
            dict with version, status, fields_hash, provenance
        """
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data or not j.spec_data.get("fields"):
            raise ValueError("No fields to confirm")

        spec = dict(j.spec_data)

        # Archive current as pre-confirmation
        history = list(spec.get("fields_history", []))
        history.append({
            "version": spec.get("fields_version", 0),
            "fields": spec["fields"],
            "hash": spec.get("fields_hash"),
            "provenance": spec.get("fields_provenance", {}),
            "status": spec.get("fields_status", "proposed"),
            "archived_at": _utcnow_iso(),
        })
        spec["fields_history"] = history

        new_version = spec.get("fields_version", 0) + 1
        spec["fields_version"] = new_version
        spec["fields_status"] = "confirmed"
        spec["fields_hash"] = _compute_hash(spec["fields"])
        provenance = dict(spec.get("fields_provenance", {}))
        provenance["confirmed_by"] = user_id
        provenance["confirmed_at"] = _utcnow_iso()
        spec["fields_provenance"] = provenance

        j.spec_data = spec
        db.session.commit()

        return {
            "version": new_version,
            "status": "confirmed",
            "fields_hash": spec["fields_hash"],
            "provenance": spec["fields_provenance"],
        }

    # ── API Contract (Tab B) ───────────────────────────────────────────

    def get_api_contract(self, junction_id):
        """Return api_contract section of spec_data, or None."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            return None
        return {
            "api_contract": j.spec_data.get("api_contract", {}),
            "version": j.spec_data.get("contract_version", 0),
            "status": j.spec_data.get("contract_status", "proposed"),
            "contract_hash": j.spec_data.get("contract_hash"),
            "provenance": j.spec_data.get("contract_provenance", {}),
        }

    def save_api_contract(self, junction_id, contract, user_id, generated_by="user", model_used=None):
        """Save or update API contract. Same versioning pattern as fields."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j:
            raise ValueError(f"Junction {junction_id} not found")

        spec = dict(j.spec_data or {})
        old_version = spec.get("contract_version", 0)
        new_version = old_version + 1

        history = list(spec.get("contract_history", []))
        if spec.get("api_contract"):
            history.append({
                "version": old_version,
                "api_contract": spec["api_contract"],
                "hash": spec.get("contract_hash"),
                "provenance": spec.get("contract_provenance", {}),
                "archived_at": _utcnow_iso(),
            })
        spec["contract_history"] = history

        spec["api_contract"] = contract
        spec["contract_version"] = new_version
        spec["contract_status"] = "proposed"
        spec["contract_hash"] = _compute_hash(contract)
        spec["contract_provenance"] = {
            "generated_by": generated_by,
            "saved_by": user_id,
            "saved_at": _utcnow_iso(),
            "model_used": model_used,
        }

        j.spec_data = spec
        db.session.commit()

        return {
            "version": new_version,
            "status": "proposed",
            "contract_hash": spec["contract_hash"],
            "provenance": spec["contract_provenance"],
        }

    def confirm_api_contract(self, junction_id, user_id):
        """Confirm proposed API contract."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data or not j.spec_data.get("api_contract"):
            raise ValueError("No API contract to confirm")

        spec = dict(j.spec_data)
        history = list(spec.get("contract_history", []))
        history.append({
            "version": spec.get("contract_version", 0),
            "api_contract": spec["api_contract"],
            "hash": spec.get("contract_hash"),
            "provenance": spec.get("contract_provenance", {}),
            "status": spec.get("contract_status", "proposed"),
            "archived_at": _utcnow_iso(),
        })
        spec["contract_history"] = history

        new_version = spec.get("contract_version", 0) + 1
        spec["contract_version"] = new_version
        spec["contract_status"] = "confirmed"
        spec["contract_hash"] = _compute_hash(spec["api_contract"])
        provenance = dict(spec.get("contract_provenance", {}))
        provenance["confirmed_by"] = user_id
        provenance["confirmed_at"] = _utcnow_iso()
        spec["contract_provenance"] = provenance

        j.spec_data = spec
        db.session.commit()

        return {
            "version": new_version,
            "status": "confirmed",
            "contract_hash": spec["contract_hash"],
            "provenance": spec["contract_provenance"],
        }

    # ── Business Rules (Tab C) ─────────────────────────────────────────

    def get_business_rules(self, junction_id):
        """Return business_rules section of spec_data, or None."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            return None
        return {
            "rules": j.spec_data.get("business_rules", []),
            "version": j.spec_data.get("rules_version", 0),
            "provenance": j.spec_data.get("rules_provenance", {}),
        }

    def save_business_rules(self, junction_id, rules, user_id, generated_by="user", model_used=None):
        """Save or update business rules. Each rule has its own status."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j:
            raise ValueError(f"Junction {junction_id} not found")

        spec = dict(j.spec_data or {})
        old_version = spec.get("rules_version", 0)
        new_version = old_version + 1

        history = list(spec.get("rules_history", []))
        if spec.get("business_rules"):
            history.append({
                "version": old_version,
                "rules": spec["business_rules"],
                "provenance": spec.get("rules_provenance", {}),
                "archived_at": _utcnow_iso(),
            })
        spec["rules_history"] = history

        # Tag each rule with status + provenance
        tagged_rules = []
        for rule in rules:
            r = dict(rule)
            if "status" not in r:
                r["status"] = "proposed"
            if "version" not in r:
                r["version"] = new_version
            if "provenance" not in r:
                r["provenance"] = {
                    "generated_by": generated_by,
                    "saved_by": user_id,
                    "saved_at": _utcnow_iso(),
                    "model_used": model_used,
                }
            tagged_rules.append(r)

        spec["business_rules"] = tagged_rules
        spec["rules_version"] = new_version
        spec["rules_provenance"] = {
            "generated_by": generated_by,
            "saved_by": user_id,
            "saved_at": _utcnow_iso(),
            "model_used": model_used,
        }

        j.spec_data = spec
        db.session.commit()

        return {
            "version": new_version,
            "rules": tagged_rules,
            "provenance": spec["rules_provenance"],
        }

    def confirm_business_rule(self, junction_id, rule_id, user_id):
        """Confirm a single business rule by ID."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            raise ValueError("No spec data")

        spec = dict(j.spec_data)
        rules = list(spec.get("business_rules", []))
        found = False
        for rule in rules:
            if rule.get("id") == rule_id:
                rule["status"] = "confirmed"
                rule["version"] = rule.get("version", 0) + 1
                provenance = dict(rule.get("provenance", {}))
                provenance["confirmed_by"] = user_id
                provenance["confirmed_at"] = _utcnow_iso()
                rule["provenance"] = provenance
                found = True
                break

        if not found:
            raise ValueError(f"Rule {rule_id} not found")

        spec["business_rules"] = rules
        j.spec_data = spec
        db.session.commit()

        return {"rule_id": rule_id, "status": "confirmed"}

    # ── History ────────────────────────────────────────────────────────

    def get_history(self, junction_id, section="fields"):
        """Return version history for a given section (fields, contract, rules)."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            return []
        key = f"{section}_history"
        return j.spec_data.get(key, [])

    # ── Diff ──────────────────────────────────────────────────────────

    def diff_versions(self, junction_id, section, from_version, to_version):
        """Compare two versions of a section. Returns added/removed/changed fields."""
        history = self.get_history(junction_id, section)
        from_data = None
        to_data = None
        for entry in history:
            if entry.get("version") == from_version:
                from_data = entry.get(section, [])
            if entry.get("version") == to_version:
                to_data = entry.get(section, [])

        # If version is current (not yet archived), use live data
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if j and j.spec_data:
            if from_data is None:
                from_data = j.spec_data.get(section, [])
            if to_data is None:
                to_data = j.spec_data.get(section, [])

        if from_data is None or to_data is None:
            return {"error": "Version not found"}

        if section == "fields":
            return self._diff_fields(from_data, to_data)
        return {"from": from_data, "to": to_data}

    def _diff_fields(self, from_fields, to_fields):
        """Compute field-level diff between two versions."""
        from_map = {f["name"]: f for f in from_fields if "name" in f}
        to_map = {f["name"]: f for f in to_fields if "name" in f}

        added = [f for name, f in to_map.items() if name not in from_map]
        removed = [f for name, f in from_map.items() if name not in to_map]
        changed = []
        for name in set(from_map) & set(to_map):
            if from_map[name] != to_map[name]:
                changed.append({"field": name, "from": from_map[name], "to": to_map[name]})

        return {"added": added, "removed": removed, "changed": changed}
