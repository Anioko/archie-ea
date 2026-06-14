"""
Jira Integration Service — ENT-073

Bidirectional Jira sync for SolutionRequirement records.
- pull_issues(): fetch Jira issues by project key, create/update local requirements
- detect_drift(): compare local requirements with Jira state, flag changes
- get_sync_status(): return last sync time, issue count, drift count

Uses the requests library (already a project dependency) for synchronous HTTP
calls.  Config keys: JIRA_URL, JIRA_USER, JIRA_API_TOKEN.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app import db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status constants for jira_push_status on SolutionRequirement
# ---------------------------------------------------------------------------
PUSH_STATUS_NOT_PUSHED = "not_pushed"
PUSH_STATUS_PUSHED = "pushed"
PUSH_STATUS_SYNCED = "synced"
PUSH_STATUS_DRIFT = "drift_detected"
PUSH_STATUS_PULL_CREATED = "pull_created"
PUSH_STATUS_PULL_UPDATED = "pull_updated"

# Jira status → local requirement status mapping
_JIRA_STATUS_MAP: Dict[str, str] = {
    "To Do": "open",
    "Open": "open",
    "In Progress": "in_progress",
    "In Review": "in_review",
    "Done": "done",
    "Closed": "done",
    "Resolved": "done",
    "Backlog": "open",
}

# Jira priority → integer mapping (1 = highest)
_JIRA_PRIORITY_MAP: Dict[str, int] = {
    "Highest": 1,
    "High": 2,
    "Medium": 3,
    "Low": 4,
    "Lowest": 5,
}


@dataclass
class PullResult:
    """Result of a pull_issues() run."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "failed": self.failed,
            "total": self.created + self.updated + self.unchanged + self.failed,
            "errors": self.errors[:50],
        }


@dataclass
class DriftItem:
    """One requirement with drift between local and Jira."""

    requirement_id: int
    jira_key: str
    field_name: str
    local_value: Optional[str]
    jira_value: Optional[str]

    def as_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "jira_key": self.jira_key,
            "field": self.field_name,
            "local": self.local_value,
            "jira": self.jira_value,
        }


def _get_jira_config() -> Optional[Dict[str, str]]:
    """Read Jira connection params from Flask app config / env.

    Returns None if Jira is not configured.
    """
    jira_url = current_app.config.get("JIRA_URL")
    jira_user = current_app.config.get("JIRA_USER")
    jira_token = current_app.config.get("JIRA_API_TOKEN")

    if not (jira_url and jira_user and jira_token):
        return None

    return {
        "base_url": jira_url.rstrip("/"),
        "username": jira_user,
        "api_token": jira_token,
    }


def _jira_get(cfg: Dict[str, str], path: str, params: Optional[dict] = None) -> dict:
    """Execute a GET request against the Jira REST API.

    Args:
        cfg: dict with base_url, username, api_token.
        path: API path (e.g. /rest/api/2/search).
        params: Optional query parameters.

    Returns:
        Parsed JSON response body.

    Raises:
        requests.RequestException on network/HTTP errors.
    """
    url = f"{cfg['base_url']}{path}"
    resp = requests.get(
        url,
        auth=(cfg["username"], cfg["api_token"]),
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _compute_field_hash(fields: dict) -> str:
    """Compute a deterministic SHA-256 hash of a dict for drift detection."""
    canonical = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def pull_issues(solution_id: int, jira_project_key: str) -> PullResult:
    """Fetch Jira issues and create/update local SolutionRequirement records.

    Args:
        solution_id: The Solution to attach requirements to.
        jira_project_key: Jira project key to query (e.g. 'EA').

    Returns:
        PullResult with created/updated/unchanged/failed counts.
    """
    from app.models.solution_architect_models import SolutionRequirement
    from app.models.solution_models import Solution

    result = PullResult()

    cfg = _get_jira_config()
    if cfg is None:
        result.errors.append("Jira not configured (JIRA_URL, JIRA_USER, JIRA_API_TOKEN required)")
        return result

    solution = db.session.get(Solution, solution_id)
    if not solution:
        result.errors.append(f"Solution {solution_id} not found")
        return result

    # Fetch issues from Jira with pagination
    all_issues: List[dict] = []
    start_at = 0
    max_results = 100
    jql = f"project = {jira_project_key}"

    try:
        while True:
            data = _jira_get(cfg, "/rest/api/2/search", {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": "summary,description,status,priority,issuetype,updated",
            })
            issues = data.get("issues", [])
            if not issues:
                break
            all_issues.extend(issues)
            start_at += len(issues)
            total = data.get("total", 0)
            if start_at >= total or len(all_issues) >= 5000:
                break
    except requests.RequestException as exc:
        logger.warning("[ENT-073] Jira API request failed: %s", exc)
        result.errors.append(f"Jira API error: {exc}")
        return result

    # Process each issue
    for issue in all_issues:
        try:
            _process_pulled_issue(issue, solution_id, result)
        except Exception as exc:
            jira_key = issue.get("key", "unknown")
            result.failed += 1
            result.errors.append(f"{jira_key}: {exc}")
            logger.warning("[ENT-073] Failed to process issue %s: %s", jira_key, exc)

    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        result.errors.append(f"DB commit failed: {exc}")
        logger.error("[ENT-073] Commit failed: %s", exc)

    return result


def _process_pulled_issue(issue: dict, solution_id: int, result: PullResult) -> None:
    """Create or update a single SolutionRequirement from a Jira issue.

    Args:
        issue: Jira issue dict from the search API.
        solution_id: ID of the parent Solution.
        result: PullResult to update counters on.
    """
    from app.models.solution_architect_models import SolutionRequirement

    jira_key = issue.get("key")
    fields = issue.get("fields", {})

    summary = fields.get("summary") or ""
    description = fields.get("description") or ""
    # Jira v2 description may be plain text; v3 may be ADF — normalise
    if isinstance(description, dict):
        # ADF format — extract text content best-effort
        description = _extract_adf_text(description)

    status_name = (fields.get("status") or {}).get("name", "")
    priority_name = (fields.get("priority") or {}).get("name", "")
    jira_updated = fields.get("updated", "")

    local_status = _JIRA_STATUS_MAP.get(status_name, status_name.lower().replace(" ", "_") if status_name else "open")
    local_priority = _JIRA_PRIORITY_MAP.get(priority_name, 3)

    # Build a hash of the Jira fields for drift detection
    jira_hash = _compute_field_hash({
        "summary": summary,
        "description": description,
        "status": status_name,
        "priority": priority_name,
        "updated": jira_updated,
    })

    # Look up existing requirement by jira_issue_key
    existing = SolutionRequirement.query.filter_by(
        jira_issue_key=jira_key,
        solution_id=solution_id,
    ).first()

    if existing:
        # Check if anything changed using the push_status field to store hash
        old_hash = (existing.jira_push_status or "").replace("hash:", "")
        if old_hash == jira_hash:
            result.unchanged += 1
            return

        existing.name = summary[:200]
        existing.description = description or existing.description
        existing.status = local_status
        existing.priority = local_priority
        existing.jira_push_status = f"hash:{jira_hash}"
        result.updated += 1
    else:
        req = SolutionRequirement(
            solution_id=solution_id,
            name=summary[:200],
            description=description or "Pulled from Jira",
            status=local_status,
            priority=local_priority,
            jira_issue_key=jira_key,
            jira_push_status=f"hash:{jira_hash}",
            source=f"Jira:{jira_key}",
            is_mandatory=False,
            ai_generated=False,
        )
        db.session.add(req)
        result.created += 1


def _extract_adf_text(adf: dict) -> str:
    """Extract plain text from Atlassian Document Format (best effort)."""
    texts: List[str] = []

    def _walk(node: dict) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text":
                texts.append(node.get("text", ""))
            for child in node.get("content", []):
                _walk(child)

    _walk(adf)
    return "\n".join(texts)


def detect_drift(solution_id: int) -> List[DriftItem]:
    """Compare local requirements with their Jira counterparts, flag changes.

    Only checks requirements that have a jira_issue_key set.

    Args:
        solution_id: The Solution whose requirements to check.

    Returns:
        List of DriftItem objects describing each field-level difference.
    """
    from app.models.solution_architect_models import SolutionRequirement

    cfg = _get_jira_config()
    if cfg is None:
        return []

    requirements = SolutionRequirement.query.filter(
        SolutionRequirement.solution_id == solution_id,
        SolutionRequirement.jira_issue_key.isnot(None),
    ).all()

    drift_items: List[DriftItem] = []

    for req in requirements:
        try:
            data = _jira_get(
                cfg,
                f"/rest/api/2/issue/{req.jira_issue_key}",
                params={"fields": "summary,description,status,priority"},
            )
        except requests.RequestException as exc:
            logger.warning("[ENT-073] Drift check failed for %s: %s", req.jira_issue_key, exc)
            continue

        fields = data.get("fields", {})
        jira_summary = (fields.get("summary") or "")[:200]
        jira_status = (fields.get("status") or {}).get("name", "")
        jira_priority = (fields.get("priority") or {}).get("name", "")

        local_status_display = req.status or ""
        jira_mapped_status = _JIRA_STATUS_MAP.get(jira_status, jira_status.lower().replace(" ", "_") if jira_status else "")

        if req.name != jira_summary:
            drift_items.append(DriftItem(
                requirement_id=req.id,
                jira_key=req.jira_issue_key,
                field_name="name",
                local_value=req.name,
                jira_value=jira_summary,
            ))

        if local_status_display != jira_mapped_status:
            drift_items.append(DriftItem(
                requirement_id=req.id,
                jira_key=req.jira_issue_key,
                field_name="status",
                local_value=local_status_display,
                jira_value=jira_mapped_status,
            ))

        jira_mapped_priority = _JIRA_PRIORITY_MAP.get(jira_priority, 3)
        if req.priority != jira_mapped_priority:
            drift_items.append(DriftItem(
                requirement_id=req.id,
                jira_key=req.jira_issue_key,
                field_name="priority",
                local_value=str(req.priority),
                jira_value=str(jira_mapped_priority),
            ))

    return drift_items


def get_sync_status(solution_id: int) -> dict:
    """Return sync summary for a solution's Jira-linked requirements.

    Args:
        solution_id: The Solution to report on.

    Returns:
        Dict with total_linked, synced, not_pushed, drift counts.
    """
    from app.models.solution_architect_models import SolutionRequirement

    linked = SolutionRequirement.query.filter(
        SolutionRequirement.solution_id == solution_id,
        SolutionRequirement.jira_issue_key.isnot(None),
    ).all()

    total = len(linked)
    synced = sum(1 for r in linked if (r.jira_push_status or "").startswith("hash:"))
    pushed = sum(1 for r in linked if r.jira_push_status == PUSH_STATUS_PUSHED)
    not_pushed = sum(1 for r in linked if r.jira_push_status == PUSH_STATUS_NOT_PUSHED)

    # Count requirements without a jira key
    unlinked = SolutionRequirement.query.filter(
        SolutionRequirement.solution_id == solution_id,
        db.or_(
            SolutionRequirement.jira_issue_key.is_(None),
            SolutionRequirement.jira_issue_key == "",
        ),
    ).count()

    return {
        "solution_id": solution_id,
        "total_linked": total,
        "synced": synced,
        "pushed": pushed,
        "not_pushed": not_pushed,
        "unlinked": unlinked,
        "jira_configured": _get_jira_config() is not None,
    }
