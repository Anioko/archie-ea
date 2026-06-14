"""
GenomeExtractionService — extracts genome field values from a plain-English
conversation using structured LLM extraction.
"""
from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from typing import Any, Optional, Tuple

from app.modules.codegen.services.genome_question_engine import GenomeQuestionEngine

logger = logging.getLogger(__name__)


def _call_llm(prompt: str, max_tokens: int = 4096) -> Tuple[Optional[str], Optional[str]]:
    try:
        from app.modules.ai_chat.services.llm_service import LLMService
        provider, model = LLMService._get_configured_provider()
        tok = LLMService.get_max_tokens_limit(provider, model, requested_max=max_tokens)
        raw_text, _ = LLMService._call_llm(prompt=prompt, model=model, provider=provider, max_tokens=tok)
        return (raw_text or "").strip(), None
    except Exception as exc:
        logger.warning("GenomeExtractionService LLM failed: %s", exc)
        return None, str(exc)


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _deep_merge(base: dict, update: dict) -> dict:
    result = deepcopy(base)
    for key, value in update.items():
        if key == "confidence":
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif value is not None:
            result[key] = value
    return result


def _build_extraction_prompt(conversation: list[dict], current_genome: dict) -> str:
    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in conversation
        if msg.get("content", "").strip()
    )
    existing_json = json.dumps(current_genome, indent=2) if current_genome else "{}"
    return f"""You are an expert software architect extracting structured information from a user conversation.

TASK: Extract genome fields from the conversation below and return ONLY a JSON object.

EXISTING GENOME (preserve these, only add/update):
{existing_json}

CONVERSATION:
{conversation_text}

EXTRACTION RULES:
1. Extract ONLY what the user has explicitly stated. Do NOT invent or assume.
2. Use snake_case for all keys.
3. For infrastructure.auth.provider use one of: jwt, oauth2, oidc, saml, magic_link, api_key
4. For infrastructure.database.engine use one of: postgresql, mysql, sqlite, mongodb, dynamodb
5. For security.multi_tenancy, set enabled: true if user mentioned multiple organisations/companies/tenants
6. For modules, create one key per domain area (e.g. "referral", "billing"). List entity names under "entities" as keys.
7. Include a "confidence" key mapping field paths to confidence scores (0.0-1.0)
8. Only include notifications, file_storage, payments if user explicitly mentioned them
9. Return ONLY the JSON. No markdown. No explanation.

OUTPUT FORMAT:
{{
  "problem": {{"statement": "..."}},
  "modules": {{"module_name": {{"entities": {{"EntityName": {{}}}}}}}},
  "infrastructure": {{"auth": {{"provider": "..."}}, "database": {{"engine": "..."}}}},
  "security": {{"multi_tenancy": {{"enabled": true/false}}}},
  "confidence": {{"problem.statement": 0.95}}
}}"""


class GenomeExtractionService:
    """Extracts genome fields from plain-English conversation."""

    def __init__(self) -> None:
        self._question_engine = GenomeQuestionEngine()

    def extract(
        self,
        conversation: list[dict[str, Any]],
        current_genome: dict[str, Any],
    ) -> dict[str, Any]:
        if not conversation:
            return {"success": False, "error": "No conversation provided"}

        prompt = _build_extraction_prompt(conversation, current_genome)
        raw_text, llm_error = _call_llm(prompt, max_tokens=4096)

        if not raw_text:
            return {"success": False, "error": f"LLM call failed: {llm_error}"}

        extracted = _extract_json(raw_text)
        if extracted is None:
            return {"success": False, "error": f"LLM returned non-JSON: {raw_text[:200]}"}

        merged = _deep_merge(current_genome, extracted)
        completeness = self._question_engine.completeness_pct(merged)
        next_q = self._question_engine.next_question(merged)
        ready = self._question_engine.ready_to_generate(merged)

        return {
            "success": True,
            "genome_partial": merged,
            "completeness_pct": completeness,
            "next_question": next_q,
            "ready_to_generate": ready,
        }
