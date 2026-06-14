"""NaturalLanguageRuleParser -- converts BA English text into structured rule definitions.

Uses the LLM to interpret natural language, then validates the output against
rule_schema.py. If confidence < 0.8, returns a clarifying question instead of
a rule definition.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from app.modules.codegen.services.rule_schema import (
    VALID_ACTION_TYPES,
    VALID_CONDITION_TYPES,
    VALID_SIDE_EFFECT_TYPES,
    VALID_TRIGGER_EVENTS,
    validate_rule_definition,
)

logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.8


def _call_llm(prompt: str, max_tokens: int = 3072) -> Tuple[Optional[str], Optional[str]]:
    """Call LLM -- same pattern as codegen_intelligence_service.py."""
    try:
        from app.modules.ai_chat.services.llm_service import LLMService

        provider, model = LLMService._get_configured_provider()
        tok = LLMService.get_max_tokens_limit(provider, model, requested_max=max_tokens)
        raw_text, _ = LLMService._call_llm(
            prompt=prompt, model=model, provider=provider, max_tokens=tok
        )
        return (raw_text or "").strip(), None
    except Exception as e:
        logger.warning("NL rule parser LLM failed: %s", e)
        return None, str(e)


def _build_prompt(rule_text: str, data_model: Dict[str, Any]) -> str:
    """Build the LLM prompt from BA text and data model context."""
    entities_desc = []
    for cls in data_model.get("classes", []):
        fields = ", ".join(
            f"{f['name']} ({f.get('type', 'string')})" for f in cls.get("fields", [])
        )
        entities_desc.append(f"  - {cls['name']}: {fields}")
    entities_block = "\n".join(entities_desc) if entities_desc else "  (no entities defined)"

    return f"""You are a business rules interpreter. Convert the user's natural language rule into a structured JSON rule definition.

DATA MODEL:
{entities_block}

VALID TRIGGER EVENTS: {sorted(VALID_TRIGGER_EVENTS)}
VALID CONDITION TYPES: {sorted(VALID_CONDITION_TYPES)}
VALID ACTION TYPES: {sorted(VALID_ACTION_TYPES)}
VALID SIDE EFFECT TYPES: {sorted(VALID_SIDE_EFFECT_TYPES)}

OUTPUT FORMAT (JSON only, no markdown, no explanation):
{{
    "trigger": {{"event": "<valid_event>", "entity": "<entity_name>"}},
    "conditions": [{{"type": "<valid_type>", "field": "<field_name>", "operator": "<op>", "value": "<value>"}}],
    "actions": [{{"type": "<valid_type>", "details": {{...}}}}],
    "side_effects": [{{"type": "<valid_type>", "details": {{...}}}}],
    "confidence": <0.0-1.0>,
    "clarification": "<optional: question to ask if confidence < 0.8>"
}}

RULES:
- entity must be one of the entities in the data model above
- fields must exist on the referenced entity
- confidence reflects how certain you are about the interpretation (0.0-1.0)
- if you are unsure (confidence < 0.8), include a clarification question
- output ONLY the JSON object, nothing else

USER RULE: {rule_text}"""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from LLM response, handling markdown code blocks."""
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


class NaturalLanguageRuleParser:
    """Parses natural language business rules into structured rule definitions."""

    def parse(self, rule_text: str, data_model: Dict[str, Any]) -> Dict[str, Any]:
        """Parse natural language rule text into a structured rule definition.

        Returns:
            {success: True, rule_definition: {...}, confidence: float}
            OR {success: False, clarification: str, confidence: float} if low confidence
            OR {success: False, error: str} on failure
            OR {success: False, validation_errors: [...]} if schema validation fails
        """
        prompt = _build_prompt(rule_text, data_model)
        raw_text, llm_error = _call_llm(prompt, max_tokens=2048)

        if llm_error and not raw_text:
            return {"success": False, "error": f"LLM call failed: {llm_error}"}

        parsed = _extract_json(raw_text)
        if parsed is None:
            return {"success": False, "error": "LLM returned non-JSON response"}

        confidence = parsed.get("confidence", 0.0)
        clarification = parsed.get("clarification")

        rule_def = {k: v for k, v in parsed.items() if k not in ("clarification",)}

        if confidence < _CONFIDENCE_THRESHOLD:
            return {
                "success": False,
                "clarification": clarification or "Could you provide more detail about this rule?",
                "confidence": confidence,
                "rule_definition": rule_def,
            }

        errors = validate_rule_definition(rule_def)
        if errors:
            return {"success": False, "validation_errors": errors}

        return {"success": True, "rule_definition": rule_def, "confidence": confidence}
