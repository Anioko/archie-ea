"""Chief Architect AI briefing over the workbench's own measured posture.

Advisory only. This follows the contract established by
``app/modules/dashboard/v2/services/executive_briefing_service.py``:

* the model is handed **exactly** the posture the page already computed — never
  a re-query and never a figure assembled here, so it can only refer to numbers
  the reader can already see;
* the prompt states the measured / missing / unavailable distinction explicitly,
  because a model that cannot tell "0 recorded" from "could not measure" will
  confidently report a clean portfolio built out of an outage;
* a parse failure raises. There is deliberately no fallback briefing: a
  plausible sentence generated because the real one was unavailable is exactly
  the failure AGENTS.md forbids, and it is *more* dangerous in prose than in a
  number because prose carries no em dash to signal absence.

Nothing here is persisted, and nothing here feeds a measured figure back into
the page.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.modules.ai_chat.services.llm_service_impl import LLMService

logger = logging.getLogger(__name__)


class ChiefArchitectBriefingError(Exception):
    """Raised when the model's response cannot be parsed into a usable briefing.

    Never caught in order to substitute a fabricated briefing.
    """


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(
            line for line in raw.splitlines() if not line.startswith("```")
        ).strip()
    return raw


def _load_json_object(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as exc:
        raise ChiefArchitectBriefingError(
            f"Model response was not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ChiefArchitectBriefingError("Model response was not a JSON object")
    return data


def evidence_digest(synthesis: Dict[str, Any]) -> Dict[str, Any]:
    """The subset of the workbench posture the model is allowed to reason over.

    Deliberately narrow. Passing the whole synthesis would hand the model
    internal keys it cannot interpret (``worst``, ``action_url``) and invite it
    to describe plumbing as findings. What it gets is: the scope, the lens
    measures with their sources, and the attention queue — the same things the
    reader sees.
    """
    enterprise = synthesis.get("enterprise") or {}
    lenses: List[Dict[str, Any]] = []
    for lens in enterprise.get("lenses", []):
        lenses.append(
            {
                "domain": lens.get("label"),
                "state": lens.get("state"),
                "total": lens.get("total"),
                "total_of": lens.get("total_label"),
                "measured": [
                    {
                        "label": entry.get("label"),
                        "value": entry.get("value"),
                        "of": entry.get("of"),
                        "source_column": entry.get("source"),
                    }
                    for entry in lens.get("measures", [])
                ],
                "missing_information": [
                    {
                        "label": entry.get("label"),
                        "records_missing_the_field": entry.get("value"),
                        "of": entry.get("of"),
                        "source_column": entry.get("source"),
                    }
                    for entry in lens.get("missing", [])
                    if entry.get("value")
                ],
            }
        )

    return {
        "scope": synthesis.get("scope"),
        "solution_conformance": {
            "average_score_out_of_100": synthesis.get("avg_conformance"),
            "solutions_evaluated": synthesis.get("solutions_reviewed"),
            "solutions_unassessed": synthesis.get("solutions_unassessed"),
            "solutions_unavailable": synthesis.get("solutions_unavailable"),
        },
        "arb": synthesis.get("arb"),
        "enterprise_lenses": lenses,
        "attention_queue": [
            {
                "domain": item.get("source_label"),
                "title": item.get("title"),
                "severity": item.get("severity"),
                "why": item.get("reason"),
            }
            for item in synthesis.get("attention", [])
        ],
    }


def _build_prompt(digest: Dict[str, Any]) -> str:
    from app.modules.ai_chat.services.architect_persona_charters import (
        governed_evidence_rules,
    )

    return (
        "You are the Chief Architect of this organisation, briefing yourself before "
        "an architecture board meeting. Below is the enterprise architecture posture "
        "exactly as it was measured from the system of record.\n\n"
        # The same six HARD RULES every governed architect persona carries —
        # no fabrication, cite your source, propose don't dispose, governance
        # wins. Inherited rather than restated so this surface cannot drift away
        # from the platform's AI governance. `build_architect_prompt` is
        # deliberately NOT used: it appends a separately-queried live data block,
        # which would let the model cite numbers that are not on this page.
        f"{governed_evidence_rules()}\n"
        "The JSON below IS your Live Platform Data block; there is no other.\n\n"
        "ADDITIONAL RULES FOR THIS BRIEFING:\n"
        "1. Every number you cite must appear verbatim in the JSON below. Do not "
        "estimate, extrapolate, total, or average anything yourself.\n"
        "2. A null value means the figure COULD NOT BE MEASURED. It does not mean "
        "zero. Never describe a null as an absence of problems — describe it as an "
        "absence of evidence.\n"
        '3. A domain with state "unavailable" was not readable at all. Say so; do '
        "not reason about its contents.\n"
        '4. A domain with state "empty" genuinely has no records modelled. That is a '
        "gap in the architecture practice, not a clean bill of health.\n"
        "5. `missing_information` counts records that exist but do not carry the "
        "field. High values there mean the measured figures beside them rest on a "
        "small denominator — say that plainly.\n"
        "6. You are advisory. Recommend; do not assert that anything has been done.\n\n"
        f"Measured posture (JSON):\n{json.dumps(digest, indent=2, default=str)}\n\n"
        "Respond ONLY with a single JSON object with exactly these keys:\n"
        '- "headline": string, one sentence — the single thing a Chief Architect '
        "should know right now\n"
        '- "evidence_quality": string, 1-2 sentences on how far these figures can be '
        "trusted, given the missing information and any unavailable domains\n"
        '- "priorities": array of objects, each with exactly these keys:\n'
        '    - "focus": string, a specific action grounded in a figure above\n'
        '    - "because": string, citing the figure and its source column\n'
        '- "blind_spots": array of strings, things this posture CANNOT tell you, '
        "drawn from the nulls, empty domains and missing_information above\n\n"
        "Respond with raw JSON only, no markdown fences, no extra prose."
    )


def _parse(raw: str) -> Dict[str, Any]:
    data = _load_json_object(raw)

    required = {"headline", "evidence_quality", "priorities", "blind_spots"}
    missing = required - data.keys()
    if missing:
        raise ChiefArchitectBriefingError(
            f"Model response missing required keys: {sorted(missing)}"
        )
    for key in ("headline", "evidence_quality"):
        if not isinstance(data[key], str):
            raise ChiefArchitectBriefingError(
                f"Model response field {key!r} was not a string"
            )
    if not isinstance(data["priorities"], list):
        raise ChiefArchitectBriefingError(
            "Model response field 'priorities' was not a list"
        )
    if not isinstance(data["blind_spots"], list):
        raise ChiefArchitectBriefingError(
            "Model response field 'blind_spots' was not a list"
        )

    priorities = []
    for entry in data["priorities"]:
        if not isinstance(entry, dict) or "focus" not in entry or "because" not in entry:
            raise ChiefArchitectBriefingError(
                "Each priority must be an object with 'focus' and 'because'"
            )
        priorities.append(
            {"focus": str(entry["focus"]), "because": str(entry["because"])}
        )

    return {
        "headline": data["headline"],
        "evidence_quality": data["evidence_quality"],
        "priorities": priorities,
        "blind_spots": [str(x) for x in data["blind_spots"]],
    }


def generate_chief_architect_briefing(synthesis: Dict[str, Any]) -> Dict[str, Any]:
    """Advisory briefing over the workbench's own measured posture.

    Raises ``ChiefArchitectBriefingError`` rather than returning a fabricated
    briefing when the model's answer cannot be trusted.
    """
    prompt = _build_prompt(evidence_digest(synthesis))
    raw = LLMService.generate_from_prompt(prompt, use_cache=False)
    return _parse(raw)
