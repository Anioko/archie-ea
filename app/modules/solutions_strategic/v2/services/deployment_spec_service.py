"""
Deployment Specification Service — CRUD + versioning for spec_data.deployment.

Stores deployment config on SolutionArchiMateElement.spec_data.deployment for Node elements.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone

from app import db
from app.models.solution_archimate_element import SolutionArchiMateElement
from app.modules.solutions_strategic.v2.services.spec_validators import validate_deployment_spec

logger = logging.getLogger(__name__)


def _compute_hash(data):
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DeploymentSpecService:
    """Read/write deployment specs in SolutionArchiMateElement.spec_data.deployment."""

    def get_deployment(self, junction_id):
        """Return deployment section of spec_data, or None."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            return None
        deploy = j.spec_data.get("deployment")
        if not deploy:
            return None
        return {
            "deployment": deploy,
            "version": j.spec_data.get("deployment_version", 0),
            "status": j.spec_data.get("deployment_status", "proposed"),
            "deployment_hash": j.spec_data.get("deployment_hash"),
            "provenance": j.spec_data.get("deployment_provenance", {}),
        }

    def save_deployment(self, junction_id, deployment, user_id, generated_by="user", model_used=None):
        """Save or update deployment spec. Validates before saving.

        Returns dict with version/status/hash/provenance on success.
        Returns {"errors": [...]} if validation fails.
        """
        # Validate first
        errors = validate_deployment_spec(deployment)
        if errors:
            return {"errors": errors}

        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j:
            raise ValueError(f"Junction {junction_id} not found")

        spec = dict(j.spec_data or {})
        old_version = spec.get("deployment_version", 0)
        new_version = old_version + 1

        # Store history
        history = list(spec.get("deployment_history", []))
        if spec.get("deployment"):
            history.append({
                "version": old_version,
                "deployment": spec["deployment"],
                "hash": spec.get("deployment_hash"),
                "provenance": spec.get("deployment_provenance", {}),
                "archived_at": _utcnow_iso(),
            })
        spec["deployment_history"] = history

        spec["deployment"] = deployment
        spec["deployment_version"] = new_version
        spec["deployment_status"] = "proposed"
        spec["deployment_hash"] = _compute_hash(deployment)
        spec["deployment_provenance"] = {
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
            "deployment_hash": spec["deployment_hash"],
            "provenance": spec["deployment_provenance"],
        }

    def confirm_deployment(self, junction_id, user_id):
        """Confirm proposed deployment spec. Increments version, sets status to confirmed."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data or not j.spec_data.get("deployment"):
            raise ValueError("No deployment spec to confirm")

        spec = dict(j.spec_data)

        history = list(spec.get("deployment_history", []))
        history.append({
            "version": spec.get("deployment_version", 0),
            "deployment": spec["deployment"],
            "hash": spec.get("deployment_hash"),
            "provenance": spec.get("deployment_provenance", {}),
            "status": spec.get("deployment_status", "proposed"),
            "archived_at": _utcnow_iso(),
        })
        spec["deployment_history"] = history

        new_version = spec.get("deployment_version", 0) + 1
        spec["deployment_version"] = new_version
        spec["deployment_status"] = "confirmed"
        spec["deployment_hash"] = _compute_hash(spec["deployment"])
        provenance = dict(spec.get("deployment_provenance", {}))
        provenance["confirmed_by"] = user_id
        provenance["confirmed_at"] = _utcnow_iso()
        spec["deployment_provenance"] = provenance

        j.spec_data = spec
        db.session.commit()

        return {
            "version": new_version,
            "status": "confirmed",
            "deployment_hash": spec["deployment_hash"],
            "provenance": spec["deployment_provenance"],
        }

    def suggest_from_element(self, element):
        """Suggest a deployment spec from a Node/TechnologyService ArchiMate element.

        Deterministic inference from element name/description — no LLM calls.
        """
        suggestion = {
            "runtime": "python3.11",
            "framework": "fastapi",
            "database": "postgresql",
            "cache": "none",
            "messaging": "none",
            "container_runtime": "kubernetes",
            "scaling": {"min_replicas": 1, "max_replicas": 3, "metric": "cpu", "threshold": 80},
            "secrets_backend": "env-vars",
            "observability": {"logging": "stdout", "metrics": "prometheus", "traces": "jaeger"},
        }

        if element:
            desc = (getattr(element, "description", "") or "").lower()
            name = (getattr(element, "name", "") or "").lower()

            # Infer from element metadata
            if "java" in desc or "java" in name or "spring" in desc:
                suggestion["runtime"] = "java17"
                suggestion["framework"] = "spring-boot"
            elif "flask" in desc or "flask" in name:
                suggestion["runtime"] = "python3.12"
                suggestion["framework"] = "flask"
            elif "go" in name or "chi" in desc or "golang" in desc:
                suggestion["runtime"] = "go1.22"
                suggestion["framework"] = "chi"
            elif "node" in desc or "express" in desc or "typescript" in desc:
                suggestion["runtime"] = "node20"
                suggestion["framework"] = "express"
            elif "react" in desc or "react" in name:
                suggestion["runtime"] = "node20"
                suggestion["framework"] = "react"
            elif "salesforce" in desc or "apex" in desc or "apex" in name:
                suggestion["runtime"] = "apex"
                suggestion["framework"] = "salesforce"
            elif "sap" in desc or "cap" in name:
                suggestion["runtime"] = "node20"
                suggestion["framework"] = "sap-cap"
            elif ".net" in desc or "aspnet" in desc or "csharp" in desc:
                suggestion["runtime"] = "dotnet8"
                suggestion["framework"] = "aspnet"

            if "mongo" in desc:
                suggestion["database"] = "mongodb"
            if "mysql" in desc:
                suggestion["database"] = "mysql"
            if "kafka" in desc:
                suggestion["messaging"] = "kafka"
            if "rabbit" in desc:
                suggestion["messaging"] = "rabbitmq"

        return suggestion

    def get_deployment_history(self, junction_id):
        """Return the version history array for this junction's deployment spec."""
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            return []
        return list(j.spec_data.get("deployment_history", []))

    def get_deployment_diff(self, junction_id, from_version, to_version):
        """Return a diff between two versions of the deployment spec.

        Returns dict with added/removed/changed keys, or None if versions not found.
        """
        j = db.session.get(SolutionArchiMateElement, junction_id)
        if not j or not j.spec_data:
            return None

        history = j.spec_data.get("deployment_history", [])
        current_version = j.spec_data.get("deployment_version", 0)

        # Build version lookup from history + current
        version_map = {}
        for entry in history:
            version_map[entry.get("version")] = entry.get("deployment", {})
        if current_version and j.spec_data.get("deployment"):
            version_map[current_version] = j.spec_data["deployment"]

        from_spec = version_map.get(from_version)
        to_spec = version_map.get(to_version)

        if from_spec is None or to_spec is None:
            return None

        # Compute diff
        all_keys = set(list(from_spec.keys()) + list(to_spec.keys()))
        added = {k: to_spec[k] for k in all_keys if k not in from_spec}
        removed = {k: from_spec[k] for k in all_keys if k not in to_spec}
        changed = {}
        for k in all_keys:
            if k in from_spec and k in to_spec and from_spec[k] != to_spec[k]:
                changed[k] = {"from": from_spec[k], "to": to_spec[k]}

        return {
            "from_version": from_version,
            "to_version": to_version,
            "added": added,
            "removed": removed,
            "changed": changed,
        }
