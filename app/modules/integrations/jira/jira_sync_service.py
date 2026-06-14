"""
Jira Sync Service — TPM-008

Fetches the current issue status from the Jira REST API and updates the
matching KanbanCard in the local database.
"""

import logging

import requests
from flask import current_app

from app import db
from app.models.adm_kanban import KanbanCard

logger = logging.getLogger(__name__)


def sync_card_from_jira(card: KanbanCard) -> dict:
    """
    Pull the latest status for *card* from the Jira REST API and persist it.

    Returns
    -------
    dict  with keys:
        - updated  (bool)
        - jira_status (str|None)
        - error    (str|None)
    """
    if not card.jira_issue_key:
        return {"updated": False, "jira_status": None, "error": "no jira_issue_key"}

    jira_url = current_app.config.get("JIRA_URL")
    jira_user = current_app.config.get("JIRA_USER")
    jira_token = current_app.config.get("JIRA_API_TOKEN")

    if not (jira_url and jira_user and jira_token):
        return {"updated": False, "jira_status": None, "error": "Jira not configured"}

    api_url = f"{jira_url.rstrip('/')}/rest/api/3/issue/{card.jira_issue_key}"
    try:
        resp = requests.get(
            api_url,
            auth=(jira_user, jira_token),
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("[TPM-008] Jira API request failed for %s: %s", card.jira_issue_key, exc)
        return {"updated": False, "jira_status": None, "error": str(exc)}

    data = resp.json()
    jira_status = (data.get("fields") or {}).get("status", {}).get("name")

    if jira_status:
        from app.modules.integrations.jira.jira_webhook_handler import _JIRA_STATUS_MAP
        card.status = _JIRA_STATUS_MAP.get(jira_status, jira_status.lower().replace(" ", "_"))

    card.jira_push_status = f"synced:{jira_status}" if jira_status else "synced"

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {"updated": True, "jira_status": jira_status, "error": None}
