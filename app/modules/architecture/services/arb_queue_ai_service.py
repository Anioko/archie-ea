"""ARB queue clerk — AI assist for triage, agenda drafting and minutes drafting.

The reviewer side already has a per-review AI pre-brief
(arb_review_ai_service.py). This module covers the board-secretary side of
the workflow instead: prioritising a raw queue of pending submissions,
drafting a session agenda from the reviews attached to it, and drafting
minutes from the decisions already recorded in a session. All three are
advisory only — nothing here is written back to any review or session; the
callers (arb_queue_ai_routes.py) must not persist any part of a response as
if it were a real decision, schedule or minute.

Every context dict assembled here is built strictly from real column values
(or a cheap derived value like an age-in-days computed from created_at) —
never invented. Parsing never fabricates a fallback: unparseable or
structurally invalid LLM output raises ARBQueueAIError, and any item whose
review_number does not match a review actually in the context is dropped
rather than trusted, per CLAUDE.md's "never invent data" rule.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.modules.ai_chat.services.llm_service_impl import LLMService
from app.modules.architecture.services.arb_review_ai_service import VALID_DISPOSITIONS

logger = logging.getLogger(__name__)

MAX_QUEUE_ITEMS = 20

VALID_COMPLEXITIES = {"routine", "standard", "contentious"}


class ARBQueueAIError(Exception):
    """Raised when an LLM response cannot be parsed into a usable result.

    Never caught to fabricate a fallback value — a screen that fabricates a
    plausible value when the real one is missing is worse than one that
    shows nothing.
    """


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(ln for ln in lines if not ln.startswith("```"))
    return raw.strip()


def _load_json_object(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        raise ARBQueueAIError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ARBQueueAIError("LLM response was not a JSON object")
    return data


def _age_days(created_at: Optional[datetime]) -> Optional[int]:
    if created_at is None:
        return None
    return max((datetime.utcnow() - created_at).days, 0)


# ---------------------------------------------------------------------------
# 1. Queue triage
# ---------------------------------------------------------------------------


def _build_review_summary(review_item) -> Dict[str, Any]:
    """Real fields only: no computed metric that looks like a measurement."""
    return {
        "review_number": review_item.review_number,
        "title": review_item.title,
        "review_type": review_item.review_type,
        "priority": review_item.priority,
        "status": review_item.status,
        "compliance_score": review_item.compliance_score,
        "risk_score": review_item.risk_score,
        "quality_score": review_item.quality_score,
        "overall_score": review_item.overall_score,
        "age_days": _age_days(review_item.created_at),
    }


def _build_triage_context(review_items: List[Any]) -> Dict[str, Any]:
    return {"pending_reviews": [_build_review_summary(r) for r in review_items]}


def _build_triage_prompt(context: Dict[str, Any]) -> str:
    return (
        "You are assisting an Architecture Review Board (ARB) secretary in "
        "triaging the pending review queue. Below is the real, verified "
        "queue context — do not invent reviews or facts not present in "
        "it.\n\n"
        f"Queue context (JSON):\n{json.dumps(context, indent=2, default=str)}\n\n"
        "Produce a triage. Respond ONLY with a single JSON object with "
        "exactly these keys:\n"
        '- "summary": string, 1-3 sentences summarising the state of the queue\n'
        '- "items": array of objects, one per review IN THE CONTEXT ABOVE, each with:\n'
        '    "review_number": string, must exactly match a review_number from the context\n'
        '    "title": string, must match the title from the context\n'
        '    "complexity": one of "routine", "standard", "contentious"\n'
        '    "reason": string, why you assessed that complexity\n'
        '- "suggested_order": array of review_number strings, the order in which '
        "the board should take up these reviews (most urgent first)\n\n"
        "Every review_number you use MUST be one of the review_number values given "
        "in the context. Do not invent a review that is not listed.\n\n"
        "Respond with raw JSON only, no markdown fences, no extra prose."
    )


def _parse_triage(raw: str, valid_review_numbers: set) -> Dict[str, Any]:
    data = _load_json_object(raw)

    required_keys = {"summary", "items", "suggested_order"}
    missing = required_keys - data.keys()
    if missing:
        raise ARBQueueAIError(f"LLM response missing required keys: {sorted(missing)}")

    if not isinstance(data["summary"], str):
        raise ARBQueueAIError("LLM response 'summary' was not a string")
    if not isinstance(data["items"], list):
        raise ARBQueueAIError("LLM response 'items' was not a list")
    if not isinstance(data["suggested_order"], list):
        raise ARBQueueAIError("LLM response 'suggested_order' was not a list")

    parsed_items = []
    for entry in data["items"]:
        if not isinstance(entry, dict):
            raise ARBQueueAIError("LLM response item was not an object")
        item_required = {"review_number", "title", "complexity", "reason"}
        item_missing = item_required - entry.keys()
        if item_missing:
            raise ARBQueueAIError(f"LLM response item missing keys: {sorted(item_missing)}")
        if not isinstance(entry["review_number"], str) or not isinstance(entry["title"], str) or not isinstance(entry["reason"], str):
            raise ARBQueueAIError("LLM response item had a non-string field")

        # Drop rather than trust: an item naming a review not in our
        # context, or an invalid complexity value, is not usable.
        if entry["review_number"] not in valid_review_numbers:
            logger.warning("ARB triage: dropping invented review_number %r", entry["review_number"])
            continue
        if not isinstance(entry["complexity"], str):
            raise ARBQueueAIError(
                f"LLM response item 'complexity' was not a string: {entry['complexity']!r}"
            )
        if entry["complexity"] not in VALID_COMPLEXITIES:
            logger.warning("ARB triage: dropping item with invalid complexity %r", entry["complexity"])
            continue

        parsed_items.append(
            {
                "review_number": entry["review_number"],
                "title": entry["title"],
                "complexity": entry["complexity"],
                "reason": entry["reason"],
            }
        )

    if not parsed_items:
        raise ARBQueueAIError("LLM response contained no usable items after dropping invented reviews")

    suggested_order = [
        rn for rn in data["suggested_order"] if isinstance(rn, str) and rn in valid_review_numbers
    ]

    return {
        "summary": data["summary"],
        "items": parsed_items,
        "suggested_order": suggested_order,
    }


def generate_queue_triage(review_items: List[Any]) -> Dict[str, Any]:
    """Generate an AI triage of the pending ARB queue.

    Caller is responsible for the empty-queue short-circuit (no LLM call
    when there is nothing to triage) and for capping review_items at
    MAX_QUEUE_ITEMS before calling this.
    """
    valid_review_numbers = {r.review_number for r in review_items}
    context = _build_triage_context(review_items)
    prompt = _build_triage_prompt(context)
    raw = LLMService.generate_from_prompt(prompt, use_cache=False)
    return _parse_triage(raw, valid_review_numbers)


# ---------------------------------------------------------------------------
# 2. Session agenda draft
# ---------------------------------------------------------------------------


def _build_agenda_context(session) -> Dict[str, Any]:
    return {
        "session": {
            "board_number": session.board_number,
            "name": session.name,
            "scheduled_date": session.scheduled_date,
            "duration_minutes": session.duration_minutes,
            "status": session.status,
        },
        "review_items": [_build_review_summary(r) for r in (session.review_items or [])],
    }


def _build_agenda_prompt(context: Dict[str, Any]) -> str:
    return (
        "You are assisting an Architecture Review Board (ARB) secretary in "
        "drafting a session agenda. Below is the real, verified session and "
        "its linked review items — do not invent reviews or facts not "
        "present in it.\n\n"
        f"Session context (JSON):\n{json.dumps(context, indent=2, default=str)}\n\n"
        "Produce an agenda draft. Respond ONLY with a single JSON object "
        "with exactly these keys:\n"
        '- "summary": string, 1-3 sentences describing the agenda\n'
        '- "items": array of objects, one per review item IN THE CONTEXT ABOVE, each with:\n'
        '    "review_number": string, must exactly match a review_number from the context\n'
        '    "suggested_minutes": integer, minutes to allocate to this item\n'
        '    "focus": string, what the board should focus discussion on\n'
        '- "sequencing_rationale": string, why you ordered/allocated time this way\n\n'
        "Every review_number you use MUST be one of the review_number values given "
        "in the context. Do not invent a review that is not listed.\n\n"
        "Respond with raw JSON only, no markdown fences, no extra prose."
    )


def _parse_agenda(raw: str, valid_review_numbers: set) -> Dict[str, Any]:
    data = _load_json_object(raw)

    required_keys = {"summary", "items", "sequencing_rationale"}
    missing = required_keys - data.keys()
    if missing:
        raise ARBQueueAIError(f"LLM response missing required keys: {sorted(missing)}")

    if not isinstance(data["summary"], str) or not isinstance(data["sequencing_rationale"], str):
        raise ARBQueueAIError("LLM response summary/sequencing_rationale were not strings")
    if not isinstance(data["items"], list):
        raise ARBQueueAIError("LLM response 'items' was not a list")

    parsed_items = []
    for entry in data["items"]:
        if not isinstance(entry, dict):
            raise ARBQueueAIError("LLM response item was not an object")
        item_required = {"review_number", "suggested_minutes", "focus"}
        item_missing = item_required - entry.keys()
        if item_missing:
            raise ARBQueueAIError(f"LLM response item missing keys: {sorted(item_missing)}")
        if not isinstance(entry["review_number"], str) or not isinstance(entry["focus"], str):
            raise ARBQueueAIError("LLM response item had a non-string field")
        if not isinstance(entry["suggested_minutes"], int) or isinstance(entry["suggested_minutes"], bool):
            raise ARBQueueAIError("LLM response item 'suggested_minutes' was not an integer")

        if entry["review_number"] not in valid_review_numbers:
            logger.warning("ARB agenda: dropping invented review_number %r", entry["review_number"])
            continue

        parsed_items.append(
            {
                "review_number": entry["review_number"],
                "suggested_minutes": entry["suggested_minutes"],
                "focus": entry["focus"],
            }
        )

    if not parsed_items:
        raise ARBQueueAIError("LLM response contained no usable items after dropping invented reviews")

    return {
        "summary": data["summary"],
        "items": parsed_items,
        "sequencing_rationale": data["sequencing_rationale"],
    }


def generate_session_agenda(session) -> Dict[str, Any]:
    """Generate an AI agenda draft for an ARB session.

    Advisory only — the caller must not persist this as the session's real
    agenda without human review.
    """
    review_items = session.review_items or []
    valid_review_numbers = {r.review_number for r in review_items}
    context = _build_agenda_context(session)
    prompt = _build_agenda_prompt(context)
    raw = LLMService.generate_from_prompt(prompt, use_cache=False)
    return _parse_agenda(raw, valid_review_numbers)


# ---------------------------------------------------------------------------
# 3. Session minutes draft
# ---------------------------------------------------------------------------


def get_decided_review_items(session) -> List[Any]:
    """Return this session's review items that have a recorded decision.

    A recorded decision is a non-null `decision` column value drawn from
    the same vocabulary the reviewer decision flow writes
    (VALID_DISPOSITIONS in arb_review_ai_service.py).
    """
    return [r for r in (session.review_items or []) if r.decision in VALID_DISPOSITIONS]


def _build_minutes_context(session, decided_items: List[Any]) -> Dict[str, Any]:
    return {
        "session": {
            "board_number": session.board_number,
            "name": session.name,
            "scheduled_date": session.scheduled_date,
            "status": session.status,
        },
        "decided_reviews": [
            {
                "review_number": r.review_number,
                "title": r.title,
                "decision": r.decision,
                "decision_rationale": r.decision_rationale or None,
                "conditions": r.conditions or None,
            }
            for r in decided_items
        ],
    }


def _build_minutes_prompt(context: Dict[str, Any]) -> str:
    return (
        "You are assisting an Architecture Review Board (ARB) secretary in "
        "drafting session minutes from decisions already recorded. Below is "
        "the real, verified context — do not invent reviews, decisions or "
        "facts not present in it.\n\n"
        f"Session context (JSON):\n{json.dumps(context, indent=2, default=str)}\n\n"
        "Produce a minutes draft. Respond ONLY with a single JSON object "
        "with exactly these keys:\n"
        '- "summary": string, 1-3 sentences summarising what the board decided\n'
        '- "decisions": array of objects, one per decided review IN THE CONTEXT ABOVE, each with:\n'
        '    "review_number": string, must exactly match a review_number from the context\n'
        '    "disposition": one of "approved", "approved_with_conditions", "rejected", "deferred", '
        "matching that review's recorded decision in the context\n"
        '    "conditions": array of strings, the conditions attached to this decision '
        "(empty array if none)\n"
        '- "actions": array of strings, follow-up actions arising from the session\n\n'
        "Every review_number you use MUST be one of the review_number values given "
        "in the context. Do not invent a review that is not listed.\n\n"
        "Respond with raw JSON only, no markdown fences, no extra prose."
    )


def _parse_minutes(raw: str, valid_review_numbers: set) -> Dict[str, Any]:
    data = _load_json_object(raw)

    required_keys = {"summary", "decisions", "actions"}
    missing = required_keys - data.keys()
    if missing:
        raise ARBQueueAIError(f"LLM response missing required keys: {sorted(missing)}")

    if not isinstance(data["summary"], str):
        raise ARBQueueAIError("LLM response 'summary' was not a string")
    if not isinstance(data["decisions"], list):
        raise ARBQueueAIError("LLM response 'decisions' was not a list")
    if not isinstance(data["actions"], list):
        raise ARBQueueAIError("LLM response 'actions' was not a list")

    parsed_decisions = []
    for entry in data["decisions"]:
        if not isinstance(entry, dict):
            raise ARBQueueAIError("LLM response decision was not an object")
        item_required = {"review_number", "disposition", "conditions"}
        item_missing = item_required - entry.keys()
        if item_missing:
            raise ARBQueueAIError(f"LLM response decision missing keys: {sorted(item_missing)}")
        if not isinstance(entry["review_number"], str):
            raise ARBQueueAIError("LLM response decision had a non-string review_number")
        if not isinstance(entry["conditions"], list):
            raise ARBQueueAIError("LLM response decision 'conditions' was not a list")

        if entry["review_number"] not in valid_review_numbers:
            logger.warning("ARB minutes: dropping invented review_number %r", entry["review_number"])
            continue
        if not isinstance(entry["disposition"], str):
            raise ARBQueueAIError(
                f"LLM response decision 'disposition' was not a string: {entry['disposition']!r}"
            )
        if entry["disposition"] not in VALID_DISPOSITIONS:
            logger.warning("ARB minutes: dropping decision with invalid disposition %r", entry["disposition"])
            continue

        parsed_decisions.append(
            {
                "review_number": entry["review_number"],
                "disposition": entry["disposition"],
                "conditions": [str(c) for c in entry["conditions"]],
            }
        )

    if not parsed_decisions:
        raise ARBQueueAIError("LLM response contained no usable decisions after dropping invented reviews")

    return {
        "summary": data["summary"],
        "decisions": parsed_decisions,
        "actions": [str(a) for a in data["actions"]],
    }


def generate_session_minutes(session, decided_items: List[Any]) -> Dict[str, Any]:
    """Generate an AI minutes draft for an ARB session.

    Advisory only — the returned draft is rendered into a copyable textarea
    by the caller and is never auto-saved as the session's real minutes.
    Callers must ensure decided_items is non-empty (get_decided_review_items)
    before calling; this function does not itself special-case an empty
    list, matching the review-side service's "let the caller handle the
    empty-queue short-circuit" pattern.
    """
    valid_review_numbers = {r.review_number for r in decided_items}
    context = _build_minutes_context(session, decided_items)
    prompt = _build_minutes_prompt(context)
    raw = LLMService.generate_from_prompt(prompt, use_cache=False)
    return _parse_minutes(raw, valid_review_numbers)
