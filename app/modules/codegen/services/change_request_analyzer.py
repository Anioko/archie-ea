"""ChangeRequestAnalyzer -- decomposes natural-language change requests into atomic changes.

Uses the LLM to interpret BA change descriptions and produce structured change
items with risk assessment and side-effect detection.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ChangeRequestAnalyzer:
    """Decomposes NL change requests into atomic changes with impact analysis."""

    def analyze(
        self,
        change_text: str,
        solution_id: int,
        model_entities: List[str],
        existing_rules: List[str],
    ) -> Dict[str, Any]:
        """Analyze a natural-language change request.

        Returns:
            {"changes": [...], "warnings": [...]}
            Each change has: type, risk, side_effects, and type-specific fields.
        """
        prompt = self._build_prompt(change_text, model_entities, existing_rules)
        raw, error = self._call_llm(prompt)

        if error or not raw:
            return {
                "changes": [],
                "warnings": [f"LLM analysis failed: {error or 'empty response'}"],
            }

        return self._parse_response(raw)

    def analyze_and_plan(
        self,
        change_text: str,
        solution_id: int,
        model_entities: List[str],
        existing_rules: List[str],
    ) -> Dict[str, Any]:
        """Analyze a change request AND generate a versioned change plan.

        Chains: analyze() -> MigrationGenerator.generate_batch() -> plan dict
        ready for VersionManager.create_version().
        """
        result = self.analyze(change_text, solution_id, model_entities, existing_rules)

        if not result["changes"]:
            return {
                "success": False,
                "error": "No changes extracted from request",
                "warnings": result.get("warnings", []),
            }

        from app.modules.codegen.services.migration_generator import MigrationGenerator
        migration_gen = MigrationGenerator()
        migration_result = migration_gen.generate_batch(result["changes"])

        # Compute overall risk (highest individual risk wins)
        risk_order = {"low": 0, "medium": 1, "high": 2}
        max_risk = max(
            (risk_order.get(c.get("risk", "medium"), 1) for c in result["changes"]),
            default=1,
        )
        overall_risk = {0: "low", 1: "medium", 2: "high"}[max_risk]

        # Build human-readable summary
        n = len(result["changes"])
        types = [c.get("type", "unknown") for c in result["changes"]]
        type_counts: Dict[str, int] = {}
        for t in types:
            type_counts[t] = type_counts.get(t, 0) + 1
        type_summary = ", ".join(f"{v} {k}" for k, v in type_counts.items())
        change_summary = f"{n} change{'s' if n != 1 else ''}: {type_summary}"

        return {
            "success": True,
            "changes": result["changes"],
            "warnings": result.get("warnings", []),
            "migration_scripts": {
                "forward": migration_result["forward"],
                "reverse": migration_result["reverse"],
            },
            "per_change_migrations": migration_result["per_change"],
            "overall_risk": overall_risk,
            "change_summary": change_summary,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        change_text: str,
        model_entities: List[str],
        existing_rules: List[str],
    ) -> str:
        entities_block = ", ".join(model_entities) if model_entities else "(none)"
        rules_block = ", ".join(existing_rules) if existing_rules else "(none)"

        return f"""You are a change-impact analyst for a business application.

EXISTING ENTITIES: {entities_block}
EXISTING RULES: {rules_block}

Decompose the following change request into atomic changes.

For EACH change, include:
- "type": one of add_field, modify_rule, remove_field, add_integration, update_tests, add_entity, rename_field
- "risk": low | medium | high
- "side_effects": list of non-obvious consequences (e.g., "$500K order skips approval")
- "affected_components": list of affected entities/rules
- Plus type-specific fields (entity, field_name, field_type, default, rule_name, description, etc.)

Also include a top-level "warnings" list for anything that could surprise the user.

OUTPUT FORMAT (JSON only, no markdown):
{{
    "changes": [
        {{"type": "...", "risk": "...", "side_effects": [...], "affected_components": [...], ...}}
    ],
    "warnings": ["..."]
}}

CHANGE REQUEST: {change_text}"""

    def _call_llm(self, prompt: str, max_tokens: int = 3072) -> Tuple[Optional[str], Optional[str]]:
        """Call LLM -- same pattern as nl_rule_parser.py."""
        try:
            from app.modules.ai_chat.services.llm_service import LLMService

            provider, model = LLMService._get_configured_provider()
            tok = LLMService.get_max_tokens_limit(provider, model, requested_max=max_tokens)
            raw_text, _ = LLMService._call_llm(
                prompt=prompt, model=model, provider=provider, max_tokens=tok
            )
            return (raw_text or "").strip(), None
        except Exception as e:
            logger.warning("Change request analyzer LLM failed: %s", e)
            return None, str(e)

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """Parse LLM JSON response, tolerating markdown fences."""
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "changes": [],
                "warnings": ["Failed to parse LLM response as JSON"],
            }

        changes = data.get("changes", [])
        warnings = data.get("warnings", [])

        # Ensure every change has required fields
        for change in changes:
            change.setdefault("risk", "medium")
            change.setdefault("side_effects", [])
            change.setdefault("affected_components", [])

        return {"changes": changes, "warnings": warnings}
