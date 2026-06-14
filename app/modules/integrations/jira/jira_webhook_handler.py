"""
Jira Webhook Handler — TPM-008

Receives inbound Jira webhook payloads, verifies the HMAC-SHA256 signature,
and syncs the issue status back to the matching KanbanCard.
"""

import hashlib
import hmac
import logging

from flask import current_app

from app import db
from app.models.adm_kanban import KanbanCard

logger = logging.getLogger(__name__)

# Map Jira status names → KanbanCard.status values
_JIRA_STATUS_MAP = {
    "To Do": "todo",
    "In Progress": "in_progress",
    "In Review": "review",
    "Done": "done",
    "Backlog": "backlog",
}


def _verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Return True when the HMAC-SHA256 digest matches the request header."""
    if not secret:
        # No secret configured — skip verification (dev/test mode)
        return True
    expected = hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


def handle_jira_webhook(payload: dict, raw_body: bytes, secret_header: str) -> dict:
    """
    Process an inbound Jira webhook event.

    Returns
    -------
    dict  with keys:
        - verified (bool)  — False when signature check failed
        - updated  (bool)  — True when a KanbanCard was modified
        - card_ref (str|None) — jira_issue_key of the updated card
    """
    secret = current_app.config.get("JIRA_WEBHOOK_SECRET", "")

    if not _verify_signature(raw_body, secret_header, secret):
        logger.warning("[TPM-008] Jira webhook HMAC verification failed")
        return {"verified": False, "updated": False, "card_ref": None}

    # Extract issue key and status from Jira Cloud / Server payload shape
    issue = payload.get("issue") or {}
    issue_key = issue.get("key") or payload.get("issue_key")
    fields = issue.get("fields") or {}
    status_obj = fields.get("status") or {}
    jira_status = status_obj.get("name")

    if not issue_key:
        logger.debug("[TPM-008] Webhook payload has no issue key — ignoring")
        return {"verified": True, "updated": False, "card_ref": None}

    card = KanbanCard.query.filter_by(jira_issue_key=issue_key).first()
    if card is None:
        logger.debug("[TPM-008] No KanbanCard found for jira_issue_key=%s", issue_key)
        return {"verified": True, "updated": False, "card_ref": issue_key}

    if jira_status:
        new_status = _JIRA_STATUS_MAP.get(jira_status, jira_status.lower().replace(" ", "_"))
        card.status = new_status

    card.jira_push_status = "synced"

    try:
        db.session.commit()
        logger.info("[TPM-008] KanbanCard %s synced from Jira status '%s'", issue_key, jira_status)
    except Exception:
        db.session.rollback()
        logger.exception("[TPM-008] DB commit failed for card %s", issue_key)
        raise

    return {"verified": True, "updated": True, "card_ref": issue_key}
