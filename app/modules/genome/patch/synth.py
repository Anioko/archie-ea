"""Real LLM patch synthesis for the genome-as-substrate copilot.

This is the production `patch_source` for `propose_genome_patch`: it turns a
free-text request into a *candidate genome patch dict* by prompting the existing
LLM service (`app.modules.ai_chat.services.llm_service.LLMService`). It does NOT
apply, queue, or trust anything — the returned dict is handed straight to the
deterministic validator (`validate_genome_patch`) downstream, and an invalid or
unparseable response is REJECTED, never coerced into a fabricated fallback
(CLAUDE.md: never invent data; fail closed).

Contract:
    llm_patch_source(request_text, context) -> patch dict

    context MUST carry:
        organization_id : int  — the acting org; embedded into target so the
                                  model can never propose a cross-org patch.
    context MAY carry:
        proposed_by     : str  — who/what is proposing (user id / model label),
                                  recorded into provenance.proposed_by.

The synthesizer builds a schema-shaped prompt, calls
`LLMService.generate_from_prompt` (the same generic completion entry point the
rest of the app uses; provider/model come from DB APISettings — DeepSeek in this
deployment), strips any Markdown code fences, and parses ONE JSON object out of
the response. If the response is prose, is not valid JSON, or contains no JSON
object, a `PatchSynthesisError` is raised — the proposer turns that into an
honest "could not produce a patch" result and nothing is queued.

The organization_id in `target` is FORCED to the acting org after parsing,
regardless of what the model emitted, so a hallucinated org id can never cause a
cross-org write.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from app.modules.genome.patch.schema import (
    ARCHIMATE_LAYERS,
    ARCHIMATE_TYPES,
    GENOME_DOMAINS,
    GENOME_PATCH_OPERATIONS,
)

logger = logging.getLogger(__name__)


class PatchSynthesisError(RuntimeError):
    """Raised when the LLM response cannot be turned into a patch dict.

    Carries the raw response (truncated) for diagnosis. The proposer catches
    this via its generic `except Exception` around the patch source and reports
    it honestly; nothing is queued.
    """


# --------------------------------------------------------------------------- #
# Prompt construction                                                          #
# --------------------------------------------------------------------------- #

_PROMPT_TEMPLATE = """You are the governed architecture copilot for an enterprise \
architecture platform (ArchiMate 3.2). Convert the user's request into EXACTLY ONE \
"genome patch" — a JSON object describing a single change to the enterprise model. \
You do NOT apply anything; a human approves the patch before it is applied.

Return ONLY the JSON object. No prose, no explanation, no Markdown fences.

The JSON object MUST have this shape:
{{
  "target": {{
    "organization_id": {organization_id},        // integer — MUST be exactly {organization_id}
    "domain": <one of {domains}>
  }},
  "operation": <one of {operations}>,             // "add" for a new element
  "element": {{
    "archimate_type": <one of {types}>,
    "layer": <one of {layers}>,
    "name": <short non-empty name>,
    "description": <optional one-sentence description>
  }},
  "provenance": {{
    "proposed_by": "{proposed_by}",
    "rationale": <non-empty human reason this element belongs in the model>,
    "archimate_anchor": <the type or name of the existing element this hangs off, non-empty>
  }}
}}

Rules:
- Pick the single most appropriate archimate_type and layer for the request.
- If the request describes modifying an existing element, use operation "modify" \
and include "element_id" (integer) inside "element".
- organization_id MUST be {organization_id}. domain, operation, archimate_type and \
layer MUST be chosen from the allowed values above — never invent a value.
- rationale and archimate_anchor must be real and non-empty. Do not fabricate a \
placeholder; if you cannot justify the element, that is fine — still return your \
best honest rationale.

User request:
{request_text}
"""


def _build_prompt(request_text: str, organization_id: int, proposed_by: str) -> str:
    return _PROMPT_TEMPLATE.format(
        organization_id=organization_id,
        proposed_by=proposed_by,
        request_text=(request_text or "").strip() or "(no request text provided)",
        domains=list(GENOME_DOMAINS),
        operations=list(GENOME_PATCH_OPERATIONS),
        types=list(ARCHIMATE_TYPES),
        layers=list(ARCHIMATE_LAYERS),
    )


# --------------------------------------------------------------------------- #
# Robust JSON extraction                                                       #
# --------------------------------------------------------------------------- #

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json_object(raw: str) -> Dict[str, Any]:
    """Parse a single JSON object out of an LLM response, fail-closed.

    Handles the common shapes: a bare object, an object wrapped in ```json```
    fences, or an object embedded in a little surrounding prose. Raises
    `PatchSynthesisError` if nothing parses to a dict — it NEVER returns a
    fabricated stand-in.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise PatchSynthesisError("LLM returned an empty response; no patch produced.")

    candidates = []

    # 1) Content inside a code fence, if any (```json ... ``` or ``` ... ```).
    for m in _FENCE_RE.finditer(raw):
        inner = m.group(1).strip()
        if inner:
            candidates.append(inner)

    # 2) The whole response, stripped.
    candidates.append(raw.strip())

    # 3) The first {...} span (greedy to the last brace) — catches an object
    #    surrounded by prose. Deterministic, no fabrication: it's still the
    #    model's own text, just delimited.
    brace = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace:
        candidates.append(brace.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
        # A JSON array/scalar is not a patch — keep trying other candidates.

    raise PatchSynthesisError(
        "LLM response was not a JSON patch object (unparseable or not an object). "
        "Fail-closed: no patch produced. Raw response (truncated): "
        f"{raw[:500]!r}"
    )


# --------------------------------------------------------------------------- #
# The patch source                                                            #
# --------------------------------------------------------------------------- #


def llm_patch_source(request_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesize a candidate genome patch from free text via the LLM service.

    This is the production `patch_source` handed to `propose_genome_patch`. The
    returned dict is NOT trusted — it is validated deterministically downstream.

    Args:
        request_text: the user's free-text request.
        context: must contain ``organization_id`` (int, the acting org); may
            contain ``proposed_by`` (str). Any ``llm_service`` in context (a
            callable ``(prompt) -> str``) overrides the default LLMService — used
            only to inject a stub in tests without a real/paid LLM call.

    Returns:
        A patch dict (unvalidated) with ``target.organization_id`` forced to the
        acting org.

    Raises:
        PatchSynthesisError: if org context is missing, the LLM call fails, or
            the response cannot be parsed into a JSON object. The proposer
            surfaces this as a clean failure and queues nothing.
    """
    context = context or {}
    organization_id = context.get("organization_id")
    if not isinstance(organization_id, int) or isinstance(organization_id, bool):
        raise PatchSynthesisError(
            "llm_patch_source requires an integer organization_id in context "
            "(the acting org). Refusing to synthesize a patch without it."
        )

    proposed_by = str(context.get("proposed_by") or "ai_copilot")
    prompt = _build_prompt(request_text, organization_id, proposed_by)

    # Injectable completion callable for tests; defaults to the real service.
    complete = context.get("llm_service")
    if complete is None:
        from app.modules.ai_chat.services.llm_service import LLMService

        # use_cache=False: a genome proposal must reflect the current request,
        # not a cached answer to a similar prompt.
        def complete(p: str) -> str:
            return LLMService.generate_from_prompt(p, use_cache=False)

    try:
        raw = complete(prompt)
    except PatchSynthesisError:
        raise
    except Exception as exc:  # provider/network/config failure — fail closed.
        raise PatchSynthesisError(f"LLM patch synthesis call failed: {exc}") from exc

    patch = _extract_json_object(raw)

    # Force the acting org into target regardless of what the model emitted, so
    # a hallucinated org id can never produce a cross-org patch. If the model
    # omitted target entirely, this also seeds it (validation still enforces the
    # rest of the shape).
    target = patch.get("target")
    if not isinstance(target, dict):
        target = {}
        patch["target"] = target
    target["organization_id"] = organization_id

    logger.info(
        "genome patch synthesized for org %s (operation=%s, type=%s)",
        organization_id,
        patch.get("operation"),
        (patch.get("element") or {}).get("archimate_type")
        if isinstance(patch.get("element"), dict)
        else None,
    )
    return patch


__all__ = ["llm_patch_source", "PatchSynthesisError"]
