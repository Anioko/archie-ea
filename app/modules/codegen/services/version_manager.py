"""VersionManager -- orchestrates versioned deployments with rollback.

Uses DeploymentOrchestrator (Phase 1) for actual Coolify operations.
"""
from __future__ import annotations

import logging
from datetime import datetime

from app.extensions import db
from app.modules.codegen.models import SolutionVersion

logger = logging.getLogger(__name__)


def _describe_change(change: dict) -> str:
    """Convert an atomic change dict to a human-readable sentence."""
    change_type = change.get("type", "unknown")
    entity = change.get("entity", "unknown")
    if change_type == "add_field":
        return f"Add field '{change.get('field_name', '?')}' to {entity}"
    elif change_type == "remove_field":
        return f"Deprecate field '{change.get('field_name', '?')}' on {entity} (30-day deprecation)"
    elif change_type == "rename_field":
        return f"Rename '{change.get('old_field_name', '?')}' to '{change.get('new_field_name', '?')}' on {entity}"
    elif change_type == "add_entity":
        return f"Create new entity '{entity}'"
    elif change_type == "modify_rule":
        return f"Modify rule '{change.get('rule_name', '?')}': {change.get('description', '')}"
    elif change_type == "add_integration":
        return f"Add integration: {change.get('description', entity)}"
    else:
        return f"{change_type} on {entity}"


class VersionManager:
    """Create, deploy, and rollback solution versions."""

    def create_version(
        self,
        solution_id: int,
        change_plan: dict,
        change_summary: str,
        migration_scripts: dict | None = None,
        created_by: str = "system",
    ) -> SolutionVersion:
        """Create a new version, auto-incrementing the version number."""
        last = (
            SolutionVersion.query
            .filter_by(solution_id=solution_id)
            .order_by(SolutionVersion.version_number.desc())
            .first()
        )
        next_num = (last.version_number + 1) if last else 1

        version = SolutionVersion(
            solution_id=solution_id,
            version_number=next_num,
            change_summary=change_summary,
            change_plan=change_plan,
            migration_scripts=migration_scripts,
            status="deploying",
            created_by=created_by,
        )
        db.session.add(version)
        db.session.commit()
        return version

    def get_history(self, solution_id: int) -> list[SolutionVersion]:
        """Return version history for a solution, most recent first."""
        return (
            SolutionVersion.query
            .filter_by(solution_id=solution_id)
            .order_by(SolutionVersion.version_number.desc())
            .all()
        )

    def rollback(self, solution_id: int, target_version: int) -> SolutionVersion:
        """Rollback to a previous version.

        Sets current live version to 'rolled_back', target to 'live'.
        """
        current = SolutionVersion.query.filter_by(
            solution_id=solution_id, status="live"
        ).first()
        target = SolutionVersion.query.filter_by(
            solution_id=solution_id, version_number=target_version
        ).first()
        if not target:
            raise ValueError(
                f"Version {target_version} not found for solution {solution_id}"
            )

        if current:
            current.status = "rolled_back"
        target.status = "live"
        target.deployed_at = datetime.utcnow()

        self._switch_deployment(solution_id, target)
        db.session.commit()
        return target

    def promote(self, version_id: int) -> SolutionVersion:
        """Promote a deploying version to live. Supersede current live version."""
        version = db.session.get(SolutionVersion, version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")

        current_live = SolutionVersion.query.filter_by(
            solution_id=version.solution_id, status="live"
        ).first()
        if current_live:
            current_live.status = "superseded"

        version.status = "live"
        version.deployed_at = datetime.utcnow()
        db.session.commit()
        return version

    def compare_versions(
        self, solution_id: int, v1: int, v2: int
    ) -> dict:
        """Compare two versions and return a BA-friendly diff.

        Returns structured diff with change summaries, rule changes,
        migration scripts, and test result deltas — NOT raw code diffs.
        """
        ver1 = SolutionVersion.query.filter_by(
            solution_id=solution_id, version_number=v1
        ).first()
        ver2 = SolutionVersion.query.filter_by(
            solution_id=solution_id, version_number=v2
        ).first()

        if not ver1:
            raise ValueError(f"Version {v1} not found for solution {solution_id}")
        if not ver2:
            raise ValueError(f"Version {v2} not found for solution {solution_id}")

        # Build change list from v2's change plan
        changes = []
        plan = ver2.change_plan or {}
        for change in plan.get("changes", []):
            changes.append({
                "type": change.get("type"),
                "description": _describe_change(change),
                "risk": change.get("risk", "medium"),
            })

        return {
            "v1": {
                "version_number": ver1.version_number,
                "change_summary": ver1.change_summary,
                "status": ver1.status,
                "created_at": ver1.created_at.isoformat() if ver1.created_at else None,
            },
            "v2": {
                "version_number": ver2.version_number,
                "change_summary": ver2.change_summary,
                "status": ver2.status,
                "created_at": ver2.created_at.isoformat() if ver2.created_at else None,
            },
            "changes": changes,
            "rule_changes": ver2.rule_changes,
            "migration_delta": {
                "forward": (ver2.migration_scripts or {}).get("forward"),
                "reverse": (ver2.migration_scripts or {}).get("reverse"),
            },
            "test_results_delta": {
                "v1": ver1.test_results,
                "v2": ver2.test_results,
            },
        }

    def record_test_results(self, version_id: int, results: dict) -> None:
        """Store test results on a version."""
        version = db.session.get(SolutionVersion, version_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")
        version.test_results = results
        db.session.commit()

    def _switch_deployment(
        self, solution_id: int, target_version: SolutionVersion
    ) -> None:
        """Switch Coolify deployment to target version. Override in tests."""
        try:
            from app.modules.codegen.services.deployment_orchestrator import (
                DeploymentOrchestrator,
            )
            from app.modules.codegen.services.instance_tracker import InstanceTracker

            orch = DeploymentOrchestrator()
            instance = InstanceTracker().get_instance(solution_id)
            if instance:
                orch.redeploy(instance.id, code_files={})
        except Exception as e:
            logger.error("Deployment switch failed: %s", e)
