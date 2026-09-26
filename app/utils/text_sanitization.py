"""Shared text sanitization utilities.

Functions here are used by multiple modules (AI chat, MCP tools) to prevent
untrusted content from injecting fence-like delimiters into structured output.
"""

from __future__ import annotations

import re

_FENCE_LOOKALIKE = re.compile(r"={3,}")


def neutralize_fence_lookalikes(text: str) -> str:
    """Break any byte-identical match to our own '=== BEGIN/END ... ===' fence
    syntax that might appear inside untrusted content.

    Runs of 3+ '=' are spaced apart ("===" -> "= = =") so untrusted content can
    describe or quote fence syntax (still legible) but can never produce the
    exact delimiter the real fence uses, the same way user input gets HTML-
    escaped rather than trusted not to contain "<script>".
    """
    return _FENCE_LOOKALIKE.sub(lambda m: " ".join("=" * len(m.group(0))), text)


#: Field names that are never free text (enums, ids, numbers, flags) — the
#: default skip-list for fence_response_strings(). A caller with its own
#: non-text keys can extend it rather than hand-writing a second walk.
DEFAULT_NON_TEXT_KEYS = {
    "id", "element_id", "risk_id", "work_package_id", "initiative_id",
    "application_component_id", "organization_unit_id", "depth",
    "explicit_count", "derived_count", "stale_count", "latency_ms",
    "likelihood", "impact", "risk_score", "progress_percentage",
    "completion_percentage", "cost_variance_pct", "budget_variance_pct",
    "target_value", "actual_value", "kind", "confidence", "stale",
    "derived_id", "engine_version", "chain", "chain_elements",
    "is_overdue", "capacity_not_available", "unresolved",
    "organization_id", "ratio", "sample_count", "type", "layer",
    "canvas_type", "canvas_id",
}


def fence_response_strings(payload, non_text_keys: set[str] | None = None) -> None:
    """Recursively apply neutralize_fence_lookalikes to every free-text
    string field in a dict/list response, in place.

    Fences every string value it finds rather than a hand-picked field list
    per caller — a hand-picked list silently stops covering a field the
    moment the wrapped endpoint adds one, and MCP tools have shipped with
    exactly that gap before (one tool fencing ``name``/``description`` while
    a sibling response field carrying user-authored text passed through
    unfenced). ``non_text_keys`` opts specific keys out (enums, ids,
    booleans) rather than opting fields in.
    """
    skip = DEFAULT_NON_TEXT_KEYS if non_text_keys is None else non_text_keys

    if isinstance(payload, dict):
        for key, value in list(payload.items()):
            if isinstance(value, str) and key not in skip:
                payload[key] = neutralize_fence_lookalikes(value)
            elif isinstance(value, (dict, list)):
                fence_response_strings(value, skip)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, (dict, list)):
                fence_response_strings(item, skip)