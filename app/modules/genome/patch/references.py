"""Retrieval of known-good reference architectures for a genome proposal.

Grounding (grounding.py) checks a proposal against the org's OWN model — it
stops re-invention and untrue structure. This module is the other half the
owner asked for: grounding against the WORLD's proven architecture. It reuses
the reference-pattern library the platform already ships
(`ArchiMatePatternLibrary.PATTERNS` — 3-tier web, microservices, event-driven,
serverless, data-warehouse, …), each with trigger keywords and exemplar
elements at the right type and layer.

Used two ways:
  * to ENRICH the synthesis prompt, so the AI proposes elements that match
    proven practice instead of designing from a blank slate;
  * to tell the human approver which reference the proposal draws on (or that
    it matches none, which is itself worth knowing).

Deterministic — keyword scoring over the library, no LLM, no network. If the
library is unavailable it degrades to "no references", never an error.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_WORD.findall((text or "").lower()))


def _load_patterns() -> Dict[str, Any]:
    try:
        from app.modules.architecture.services.archimate_pattern_library import (
            ArchiMatePatternLibrary,
        )

        return dict(ArchiMatePatternLibrary.PATTERNS)
    except Exception:
        return {}


def retrieve_reference_patterns(query_text: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Return the reference patterns most relevant to `query_text`, best first.

    Scored by overlap between the query's words and each pattern's trigger
    phrases, name, and description. A pattern with zero overlap is not returned,
    so "no references" is an honest, common outcome — never a fabricated match.
    Each result is trimmed to what a prompt or an approver needs: id, name,
    description, and the exemplar (type, layer) pairs the pattern prescribes.
    """
    q = _tokens(query_text)
    if not q:
        return []
    scored = []
    for pid, pat in _load_patterns().items():
        score = 0
        for trigger in pat.get("triggers", []):
            tw = _tokens(trigger)
            if tw and tw <= q:            # whole trigger phrase present
                score += 3
            elif tw & q:                  # some overlap
                score += len(tw & q)
        score += len(_tokens(pat.get("name", "")) & q)
        score += len(_tokens(pat.get("description", "")) & q)
        if score > 0:
            exemplars = [
                {"type": e.get("type"), "layer": e.get("layer")}
                for e in pat.get("elements", [])
            ]
            # de-dup (type, layer) exemplars, preserve order
            seen, uniq = set(), []
            for ex in exemplars:
                key = (ex["type"], ex["layer"])
                if key not in seen:
                    seen.add(key)
                    uniq.append(ex)
            scored.append(
                (
                    score,
                    {
                        "id": pid,
                        "name": pat.get("name"),
                        "description": pat.get("description"),
                        "exemplar_elements": uniq,
                    },
                )
            )
    scored.sort(key=lambda s: s[0], reverse=True)
    return [item for _, item in scored[:limit]]


def references_prompt_block(query_text: str, limit: int = 3) -> str:
    """A compact prose block of retrieved references to fold into the synthesis
    prompt. Empty string when nothing matches (the prompt then just omits it)."""
    refs = retrieve_reference_patterns(query_text, limit=limit)
    if not refs:
        return ""
    lines = [
        "Relevant proven reference architectures (design consistently with these; "
        "do not copy blindly):"
    ]
    for r in refs:
        shapes = ", ".join(
            f"{e['type']}@{e['layer']}" for e in r["exemplar_elements"][:6]
        )
        lines.append(f"- {r['name']}: {r['description']} — typical elements: {shapes}")
    return "\n".join(lines)
