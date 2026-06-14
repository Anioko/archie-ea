"""Step 4 Variant Generator — decision point identification + diff-based architecture variants.

Receives the complete architecture from Step 3, identifies 2-3 key decision points
where genuinely different approaches exist, generates alternative variants as diffs
against the base architecture, and persists risk records.
"""

import json
import logging
import re

from app import db

logger = logging.getLogger(__name__)

VARIANT_PROMPT = """You are an enterprise architect evaluating architecture options for:

{problem_summary}

CURRENT ARCHITECTURE (from Step 3):
{architecture_summary}

ACCEPTED CAPABILITIES:
{capabilities_list}

VENDOR PRODUCTS AVAILABLE IN THE ORGANIZATION:
{vendor_context}

Identify 2-3 key architectural DECISION POINTS where genuinely different approaches exist.
Focus on decisions that change implementation significantly:
- Build custom vs buy vendor product vs extend existing
- Monolith vs microservices vs serverless
- On-premise vs cloud vs hybrid
- Real-time vs batch processing

For each decision point, generate 2-3 OPTIONS. Each option must specify:
- What elements it replaces/adds/removes from the base architecture
- Impact on timeline, cost, and risk (with specific estimates)
- 1-2 identified risks with likelihood/impact/mitigation

Return ONLY valid JSON:
{{
    "decision_points": [
        {{
            "id": "dp1",
            "name": "Decision point name",
            "description": "Why this is a key decision",
            "affected_elements": ["element names from base architecture"],
            "options": [
                {{
                    "id": "dp1_opt1",
                    "name": "Option name",
                    "description": "What this option does differently",
                    "approach": "build|buy|extend|hybrid",
                    "replaces": [{{"original_name": "...", "new_name": "...", "new_type": "...", "new_description": "..."}}],
                    "adds": [{{"type": "...", "name": "...", "description": "...", "layer": "..."}}],
                    "removes": ["element names to remove"],
                    "impact": {{
                        "timeline": "+6 months|-3 months|no change",
                        "cost_annual": "+£500K|-£200K|no change",
                        "complexity": "high|medium|low",
                        "team_skills": "What skills are needed"
                    }},
                    "risks": [
                        {{
                            "name": "Risk name",
                            "description": "What could go wrong",
                            "likelihood": "high|medium|low",
                            "impact": "high|medium|low",
                            "mitigation": "How to mitigate"
                        }}
                    ],
                    "vendor_product": null
                }}
            ]
        }}
    ]
}}"""


def _parse_llm_json(raw_text):
    """Parse JSON from LLM response, stripping markdown fences."""
    if not raw_text:
        return None
    text = raw_text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        return json.loads(text[json_start:json_end])
    return None


class VariantGeneratorService:
    """Generates architecture variants and persists risk records."""

    def generate_variants(self, architecture_elements, capabilities, problem_summary, solution_id):
        """Identify decision points and generate architecture variants.

        Args:
            architecture_elements: dict with elements_by_layer from Step 3
            capabilities: list of accepted capability dicts
            problem_summary: enriched problem description
            solution_id: for persisting risk records

        Returns:
            dict with decision_points list
        """
        arch_summary = self._summarize_architecture(architecture_elements)
        caps_text = "\n".join(
            f"- {c.get('name', '?')}: {c.get('description', '')}"
            for c in capabilities
        )

        prompt = VARIANT_PROMPT.format(
            problem_summary=problem_summary,
            architecture_summary=arch_summary,
            capabilities_list=caps_text,
            vendor_context=self._get_vendor_context(),
        )

        try:
            from app.modules.ai_chat.services.llm_service import LLMService
            provider, model = LLMService._get_configured_provider()
            # The variant JSON is large; without an explicit cap the default
            # max_tokens truncated the response mid-object ("Expecting ','
            # delimiter" at ~24k chars). Request a generous budget like the
            # genome perfector does.
            max_tokens = LLMService.get_max_tokens_limit(provider, model, requested_max=8192)
            raw_text, _ = LLMService._call_llm(
                prompt=prompt, model=model, provider=provider, max_tokens=max_tokens
            )

            parsed = _parse_llm_json(raw_text)
            if not parsed:
                return {"decision_points": [], "errors": ["Failed to parse LLM response"]}

            decision_points = parsed.get("decision_points", [])
            logger.info("Generated %d decision points for solution %d", len(decision_points), solution_id)
            return {"decision_points": decision_points, "errors": []}

        except Exception as e:
            logger.error("Variant generation failed: %s", e)
            return {"decision_points": [], "errors": [str(e)]}

    def select_variant(self, solution_id, decision_point_id, option_id, decision_points):
        """Apply a selected variant option and persist its risk records.

        Args:
            solution_id: solution to attach risks to
            decision_point_id: which decision point
            option_id: which option was selected
            decision_points: full decision_points data from generate_variants

        Returns:
            dict with risks_created count and selected option details
        """
        from app.models.models import RiskAssessment

        # Find the selected option
        selected_dp = None
        selected_option = None
        for dp in decision_points:
            if dp.get("id") == decision_point_id:
                selected_dp = dp
                for opt in dp.get("options", []):
                    if opt.get("id") == option_id:
                        selected_option = opt
                        break
                break

        if not selected_option:
            return {"error": f"Option {option_id} not found in decision point {decision_point_id}"}

        # Persist risk records
        risks_created = 0
        for risk_data in selected_option.get("risks", []):
            risk = RiskAssessment(
                name=risk_data.get("name", "Unnamed Risk"),
                description=risk_data.get("description", ""),
                probability=risk_data.get("likelihood", "medium"),
                impact=risk_data.get("impact", "medium"),
                mitigation_strategy=risk_data.get("mitigation", ""),
                status="identified",
            )
            db.session.add(risk)
            risks_created += 1

        if risks_created:
            db.session.commit()

        logger.info(
            "Selected option '%s' for decision '%s', created %d risks",
            selected_option.get("name"), selected_dp.get("name"), risks_created,
        )

        return {
            "selected": {
                "decision_point": selected_dp.get("name"),
                "option": selected_option.get("name"),
                "approach": selected_option.get("approach"),
                "impact": selected_option.get("impact", {}),
            },
            "risks_created": risks_created,
        }

    def _summarize_architecture(self, elements_by_layer):
        """Create a text summary of architecture elements for the LLM prompt."""
        lines = []
        for layer in ("business", "application", "technology"):
            elems = elements_by_layer.get(layer, [])
            if elems:
                lines.append(f"\n{layer.upper()} LAYER:")
                for el in elems:
                    lines.append(f"  - {el.get('type', '?')}: {el.get('name', '?')} — {el.get('description', '')}")
        return "\n".join(lines) if lines else "No architecture elements generated yet"

    def _get_vendor_context(self):
        """Reuse vendor product lookup from ArchitectureGenerationService."""
        try:
            from app.modules.architecture_assistant.architecture_generation import ArchitectureGenerationService
            return ArchitectureGenerationService()._get_vendor_context()
        except Exception:
            return "No vendor products in catalog"
