"""CTO-facing AI advisories: an executive briefing on the Architecture
Health Scorecard, and investment-priority suggestions on the Investment
Priorities dashboard.

Both entrypoints here are advisory only: the caller must not persist any
part of the response, and both are handed exactly the metrics/context their
host page already computed (never re-queried or invented) so the model can
only reference numbers that are already real and on screen. See CLAUDE.md's
"Never invent data" rule and the ARB pre-brief service
(app/modules/architecture/services/arb_review_ai_service.py), which this
follows.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.modules.ai_chat.services.llm_service_impl import LLMService

logger = logging.getLogger(__name__)

VALID_PRIORITIES = {"now", "next", "later"}


class ExecutiveBriefingAIError(Exception):
    """Raised when the LLM response cannot be parsed into a usable result.

    Never caught to fabricate a fallback value — per CLAUDE.md, a screen
    that fabricates a plausible value when the real one is missing is worse
    than one showing nothing.
    """


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
        raise ExecutiveBriefingAIError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExecutiveBriefingAIError("LLM response was not a JSON object")
    return data


# ---------------------------------------------------------------------------
# Executive briefing (Architecture Health Scorecard)
# ---------------------------------------------------------------------------


def _build_briefing_prompt(metrics: Dict[str, Any]) -> str:
    return (
        "You are briefing a CTO on the current state of the enterprise architecture "
        "portfolio. Below is the real, computed metrics context for the Architecture "
        "Health Scorecard — do not invent, estimate, or reference any number that is "
        "not present in this JSON.\n\n"
        f"Scorecard metrics (JSON):\n{json.dumps(metrics, indent=2, default=str)}\n\n"
        "Produce an executive briefing. Respond ONLY with a single JSON object with "
        "exactly these keys:\n"
        '- "headline": string, one sentence capturing the single most important thing '
        "a CTO should know right now\n"
        '- "what_changed": array of strings, notable points drawn strictly from the '
        "given metrics (empty array if nothing stands out)\n"
        '- "risks": array of strings, the most important risks visible in the metrics\n'
        '- "recommended_focus": array of strings, where leadership attention should go '
        "next, grounded only in the given metrics\n"
        '- "rationale": string explaining the reasoning behind the headline and focus areas\n\n'
        "Respond with raw JSON only, no markdown fences, no extra prose."
    )


def _parse_briefing(raw: str) -> Dict[str, Any]:
    data = _load_json_object(raw)

    required_keys = {"headline", "what_changed", "risks", "recommended_focus", "rationale"}
    missing = required_keys - data.keys()
    if missing:
        raise ExecutiveBriefingAIError(f"LLM response missing required keys: {sorted(missing)}")

    for list_key in ("what_changed", "risks", "recommended_focus"):
        if not isinstance(data[list_key], list):
            raise ExecutiveBriefingAIError(f"LLM response field {list_key!r} was not a list")

    if not isinstance(data["headline"], str) or not isinstance(data["rationale"], str):
        raise ExecutiveBriefingAIError("LLM response headline/rationale were not strings")

    return {
        "headline": data["headline"],
        "what_changed": [str(x) for x in data["what_changed"]],
        "risks": [str(x) for x in data["risks"]],
        "recommended_focus": [str(x) for x in data["recommended_focus"]],
        "rationale": data["rationale"],
    }


def generate_executive_briefing(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an AI executive briefing from the scorecard's own metrics.

    Advisory only — the caller must not persist this. Raises
    ExecutiveBriefingAIError (or lets an LLMService exception propagate)
    rather than fabricating a fallback briefing.
    """
    prompt = _build_briefing_prompt(metrics)
    raw = LLMService.generate_from_prompt(prompt, use_cache=False)
    return _parse_briefing(raw)


# ---------------------------------------------------------------------------
# Investment priority suggestions (Investment Priorities dashboard)
# ---------------------------------------------------------------------------


def _build_suggestions_prompt(context: Dict[str, Any]) -> str:
    return (
        "You are advising a CTO on capability investment sequencing. Below is the "
        "real, computed investment-priorities context for this organization's "
        "portfolio — do not invent, estimate, or reference any figure not present "
        "in this JSON.\n\n"
        f"Investment priorities context (JSON):\n{json.dumps(context, indent=2, default=str)}\n\n"
        "Produce investment priority suggestions. Respond ONLY with a single JSON "
        "object with exactly these keys:\n"
        '- "suggestions": array of objects, each with exactly these keys:\n'
        '    - "item": string, a specific, concrete investment action grounded in the '
        "given context\n"
        '    - "priority": one of "now", "next", "later"\n'
        '    - "rationale": string explaining why this item belongs at this priority\n'
        '- "summary": string, 1-3 sentences summarizing the overall sequencing\n\n'
        "Respond with raw JSON only, no markdown fences, no extra prose."
    )


def _parse_suggestions(raw: str) -> Dict[str, Any]:
    data = _load_json_object(raw)

    required_keys = {"suggestions", "summary"}
    missing = required_keys - data.keys()
    if missing:
        raise ExecutiveBriefingAIError(f"LLM response missing required keys: {sorted(missing)}")

    if not isinstance(data["suggestions"], list):
        raise ExecutiveBriefingAIError("LLM response field 'suggestions' was not a list")
    if not isinstance(data["summary"], str):
        raise ExecutiveBriefingAIError("LLM response 'summary' was not a string")

    parsed: List[Dict[str, str]] = []
    for entry in data["suggestions"]:
        if not isinstance(entry, dict):
            continue
        item = entry.get("item")
        priority = entry.get("priority")
        rationale = entry.get("rationale")
        if not isinstance(item, str) or not item.strip():
            continue
        if priority not in VALID_PRIORITIES:
            continue
        parsed.append({
            "item": item,
            "priority": priority,
            "rationale": str(rationale) if rationale is not None else "",
        })

    if not parsed:
        raise ExecutiveBriefingAIError(
            "LLM response contained no usable suggestions after validation "
            "(empty items and/or invalid priority values were dropped)"
        )

    return {"suggestions": parsed, "summary": data["summary"]}


def generate_investment_suggestions(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate AI investment-priority suggestions from the page's own
    investment-priorities context.

    Advisory only — the caller must not persist this. Suggestions with an
    empty item string are dropped, as are ones outside {now, next, later};
    if every suggestion is dropped this raises ExecutiveBriefingAIError
    rather than returning an empty/fabricated result.
    """
    prompt = _build_suggestions_prompt(context)
    raw = LLMService.generate_from_prompt(prompt, use_cache=False)
    return _parse_suggestions(raw)
