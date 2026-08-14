"""AI drafting assist for the value-stream x capability mapping grid.

The BIZBOK grid on a value stream's detail page (app/templates/value_streams/
detail.html, app/modules/capabilities/routes/value_stream_routes.py) is
click-to-set: a user opens a cell and chooses a support level by hand. This
service suggests candidate (stage, capability) pairs from the stream's own
stages and this organization's real capability catalog — advisory only.
Nothing here is written to the database; the UI's "Apply" action reuses the
grid's existing POST /value-streams/api/mapping write path exactly, so the
AI-suggested pairs go through the same validation and persistence as a
manually-set cell.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Set

from app.models.unified_capability import UnifiedCapability, ValueStreamStage
from app.modules.ai_chat.services.llm_service_impl import LLMService

logger = logging.getLogger(__name__)

MAX_CAPABILITIES = 50


class ValueStreamAISuggestError(Exception):
    """Raised when the LLM response cannot be parsed into usable suggestions.

    Never caught to fabricate a fallback value — per CLAUDE.md, a screen that
    fabricates a plausible value when the real one is missing is worse than
    one that shows nothing.
    """


def _build_context(value_stream) -> Dict[str, Any]:
    """Assemble only the context this function actually queries: the
    stream's real stages, and this organization's real capability catalog
    (capped so the prompt stays small). Nothing is inferred or invented.
    """
    stages = (
        ValueStreamStage.query.filter(
            ValueStreamStage.value_stream_id == value_stream.id
        )
        .order_by(ValueStreamStage.stage_order)
        .all()
    )
    stage_names = [s.name for s in stages if s.name]

    try:
        capabilities = (
            UnifiedCapability.query.order_by(UnifiedCapability.name)
            .limit(MAX_CAPABILITIES)
            .all()
        )
        capability_names = [c.name for c in capabilities if c.name]
    except Exception:
        logger.exception(
            "Failed to load capability catalog for value stream %s AI context",
            value_stream.id,
        )
        capability_names = []

    return {
        "value_stream_name": value_stream.name,
        "value_stream_description": value_stream.description or None,
        "stages": stage_names,
        "capabilities": capability_names,
    }


def _build_prompt(context: Dict[str, Any]) -> str:
    return (
        "You are assisting a Business Architect mapping capabilities to "
        "value-stream stages (BIZBOK capability x stage grid). Below is the "
        "real, verified context: this stream's actual stages and this "
        "organization's actual capability catalog. Only ever name a stage "
        "or capability that appears verbatim in this context — never invent "
        "one.\n\n"
        f"Context (JSON):\n{json.dumps(context, indent=2, default=str)}\n\n"
        "Suggest which capabilities most strongly support which stages. "
        "Respond ONLY with a single JSON object with exactly these keys:\n"
        '- "suggestions": array of objects, each with "stage" (must exactly '
        'match one of the names in "stages"), "capability" (must exactly '
        'match one of the names in "capabilities"), and "rationale" (a short '
        "string explaining the mapping)\n"
        '- "summary": string, 1-3 sentences summarizing the suggested mapping\n\n'
        "Respond with raw JSON only, no markdown fences, no extra prose."
    )


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(ln for ln in lines if not ln.startswith("```"))
    return raw.strip()


def _parse_suggestions(
    raw: str, valid_stages: Set[str], valid_capabilities: Set[str]
) -> Dict[str, Any]:
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        raise ValueStreamAISuggestError(
            f"LLM response was not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueStreamAISuggestError("LLM response was not a JSON object")

    required_keys = {"suggestions", "summary"}
    missing = required_keys - data.keys()
    if missing:
        raise ValueStreamAISuggestError(
            f"LLM response missing required keys: {sorted(missing)}"
        )

    raw_suggestions = data["suggestions"]
    if not isinstance(raw_suggestions, list):
        raise ValueStreamAISuggestError("LLM response field 'suggestions' was not a list")
    if not isinstance(data["summary"], str):
        raise ValueStreamAISuggestError("LLM response field 'summary' was not a string")

    kept: List[Dict[str, str]] = []
    for item in raw_suggestions:
        if not isinstance(item, dict):
            continue
        stage = item.get("stage")
        capability = item.get("capability")
        rationale = item.get("rationale")
        # Drop any suggestion naming a stage or capability that is not
        # actually part of this stream / this org's catalog — the LLM must
        # not be allowed to invent a mapping target.
        if stage not in valid_stages or capability not in valid_capabilities:
            continue
        kept.append(
            {
                "stage": stage,
                "capability": capability,
                "rationale": str(rationale) if rationale is not None else "",
            }
        )

    if not kept:
        raise ValueStreamAISuggestError(
            "LLM suggested no stage/capability pairs present in the real context"
        )

    return {"suggestions": kept, "summary": data["summary"]}


def generate_stage_mapping_suggestions(value_stream) -> Dict[str, Any]:
    """Generate AI-suggested (stage, capability) mapping candidates.

    Advisory only — the caller must not persist any suggestion directly; the
    UI's "Apply" action goes through the grid's existing write endpoint.
    Raises ValueStreamAISuggestError (or lets an LLMService exception
    propagate) rather than fabricating a fallback suggestion list.
    """
    context = _build_context(value_stream)
    valid_stages = set(context["stages"])
    valid_capabilities = set(context["capabilities"])
    prompt = _build_prompt(context)
    raw = LLMService.generate_from_prompt(prompt, use_cache=False)
    return _parse_suggestions(raw, valid_stages, valid_capabilities)
