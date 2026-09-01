"""Propose a genome patch and route it through the EXISTING approval gate.

This is the copilot's only sanctioned way to change the enterprise model. The
language model NEVER emits artifacts or performs CRUD; it emits a *patch
object*, which this module:

  1. VALIDATES deterministically (fail-closed). An invalid proposal is rejected
     here and never queued — the validation errors are returned, not swallowed.
  2. QUEUES through the existing AI approval gate by calling
     ``AIChatApprovalService.create_pending_approval`` — the exact same queue
     mechanism `app.modules.ai_chat.approval_gate.queue_ai_write` and
     `AgentRunner._queue_approval` use. It is stored as an
     ``operation_type="tool_use"`` approval whose ``entity_type`` is
     ``"apply_genome_patch"`` and whose payload IS the validated patch. That
     makes it appear in ``GET /ai-chat/approvals/pending`` and be executable by
     ``POST /ai-chat/approvals/<id>/approve`` -> ``approve_and_execute`` ->
     ``ToolExecutor._tool_apply_genome_patch`` -> ``apply_genome_patch``.

Proposing therefore QUEUES the patch; it does NOT apply it. Applying is gated on
explicit human approval, reusing the existing gate end to end.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from app.modules.genome.patch.validator import validate_genome_patch

logger = logging.getLogger(__name__)

# The queued approval's dispatch key. Must match the ToolExecutor handler name
# suffix (`_tool_apply_genome_patch`) so approve_and_execute's tool_use branch
# routes to the applier. Deliberately NOT registered as an LLM-callable tool —
# it is reachable only through an approved patch, never directly by the model.
APPLY_ENTITY_TYPE = "apply_genome_patch"

# A patch source is any callable (request_text, context) -> patch dict. In
# production this is an LLM adapter constrained to emit ONLY a patch; in tests
# it is a stub. The point of the flow is that whatever it returns is validated
# and queued deterministically, so a hallucinated/malformed patch cannot reach
# the model.
PatchSource = Callable[[str, Dict[str, Any]], Dict[str, Any]]


def _summarize(patch: Dict[str, Any]) -> str:
    """Business-readable summary for the approval card (never a raw dict dump)."""
    el = patch.get("element", {})
    op = patch.get("operation", "add")
    prov = patch.get("provenance", {})
    verb = "Create" if op == "add" else "Modify"
    return (
        f"{verb} {el.get('archimate_type', 'element')} "
        f"'{el.get('name', '?')}' in the enterprise genome "
        f"({patch.get('target', {}).get('domain', '?')} domain). "
        f"Rationale: {prov.get('rationale', '—')}"
    )


def propose_genome_patch(
    request_text: str,
    user_id: int,
    patch_source: Optional[PatchSource] = None,
    context: Optional[Dict[str, Any]] = None,
    chat_session_id: Optional[str] = None,
    agent_turn_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Produce a validated patch from `request_text` and queue it for approval.

    Args:
        request_text: what the user asked (e.g. "propose a missing capability").
        user_id: the acting (proposing) user; also determines the target org.
        patch_source: callable returning the candidate patch dict. Injected so
            the LLM can be stubbed in tests. If omitted, the default LLM adapter
            is used (and cleanly reports if the model is unavailable).
        context: extra context passed to the patch source.

    Returns:
        On a valid, queued patch:
            {"success": True, "status": "pending_approval",
             "approval_id": int, "patch": {...}, "message": str}
        On an invalid proposal (rejected, NOT queued):
            {"success": False, "status": "rejected",
             "errors": [...], "patch": {...}}
        On any other failure: {"success": False, "error": str}.
    """
    context = dict(context or {})
    source = patch_source or _default_patch_source

    try:
        patch = source(request_text, context)
    except Exception as exc:
        logger.warning("genome patch source failed: %s", exc)
        return {"success": False, "error": f"Could not produce a patch: {exc}"}

    # 1) Deterministic, fail-closed validation BEFORE anything is queued.
    result = validate_genome_patch(patch)
    if not result.valid:
        logger.info("genome patch REJECTED (not queued): %s", result.errors)
        return {
            "success": False,
            "status": "rejected",
            "errors": result.errors,
            "patch": patch if isinstance(patch, dict) else None,
            "message": (
                "The proposed genome patch did not validate and was not queued. "
                "No change was made."
            ),
        }

    # 2) Queue through the EXISTING approval gate. This does not apply anything.
    from app.modules.ai_chat.services.ai_chat_approval_service import (
        AIChatApprovalService,
    )

    svc = AIChatApprovalService(user_id=user_id)
    queued = svc.create_pending_approval(
        operation_type="tool_use",
        entity_type=APPLY_ENTITY_TYPE,
        original_command=request_text,
        operation_payload=patch,
        summary=_summarize(patch),
        chat_session_id=chat_session_id,
        agent_turn_id=agent_turn_id,
    )

    if not queued.get("success"):
        return {"success": False, "error": queued.get("error", "Failed to queue patch")}

    return {
        "success": True,
        "status": "pending_approval",
        "approval_id": queued["approval_id"],
        "patch": patch,
        "summary": _summarize(patch),
        "message": queued.get("message", "Genome patch queued for approval."),
    }


def _default_patch_source(request_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Default (production) patch source: real LLM synthesis.

    Delegates to `app.modules.genome.patch.synth.llm_patch_source`, which prompts
    the existing LLM service to emit a candidate genome patch and parses its JSON
    fail-closed. The returned dict is NOT trusted — `propose_genome_patch`
    validates it deterministically before anything is queued. `context` must
    carry `organization_id` (the acting org); an unparseable/prose response
    raises rather than fabricating a patch (CLAUDE.md: never invent data).
    """
    from app.modules.genome.patch.synth import llm_patch_source

    return llm_patch_source(request_text, context)


__all__ = ["propose_genome_patch", "APPLY_ENTITY_TYPE", "PatchSource"]
