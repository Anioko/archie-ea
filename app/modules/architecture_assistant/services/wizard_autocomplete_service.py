"""Wizard Auto-Complete Service (Layer B).

Fills ALL empty or sparse fields to north-star quality when triggered.
Shifts the user's role from "author" to "reviewer."

Two triggers:
1. "Auto-fix" button in Quality Gate overlay (fills only failing items)
2. "Auto-complete step" button in Copilot sidebar (fills everything below threshold)

Returns per-field completions with accept/reject/edit support.
"""

import json
import logging
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app import db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FieldCompletion:
    field_path: str
    original_value: Any
    completed_value: Any
    confidence: float  # 0.0-1.0
    source: str  # "derived_from_problem" | "industry_benchmark" | "inferred_from_constraints"
    rationale: str


@dataclass
class AutoCompleteResult:
    completions: List[FieldCompletion]
    fields_completed: int
    fields_skipped: int
    estimated_quality_delta: int
    cost_gbp: Decimal


# ---------------------------------------------------------------------------
# Step-specific field specs: what to auto-complete per step
# ---------------------------------------------------------------------------

STEP_FIELD_SPECS = {
    1: {
        "fields": [
            {"path": "problem_statement", "min_length": 100, "label": "Problem statement"},
            {"path": "budget_min", "required": True, "label": "Budget minimum"},
            {"path": "budget_max", "required": True, "label": "Budget maximum"},
            {"path": "timeline_months", "required": True, "label": "Timeline"},
            {"path": "success_metrics", "min_items": 1, "label": "Success metrics"},
        ],
    },
    2: {
        "array_field": "capabilities",
        "per_item_fields": [
            {"path": "description", "min_length": 30, "label": "Description"},
            {"path": "maturity_current", "required": True, "label": "Current maturity"},
            {"path": "maturity_target", "required": True, "label": "Target maturity"},
            {"path": "strategic_importance", "required": True, "label": "Strategic importance"},
            {"path": "acm_domain", "required": True, "label": "ACM domain"},
        ],
    },
    3: {
        "array_field": "elements",
        "per_item_fields": [
            {"path": "description", "min_length": 20, "label": "Description"},
            {"path": "properties.build_buy", "required": True, "label": "Build/Buy decision"},
            {"path": "properties.deployment_model", "required": True, "label": "Deployment model"},
            {"path": "properties.availability", "required": True, "label": "Availability tier"},
        ],
    },
    4: {
        "array_field": "gaps",
        "per_item_fields": [
            {"path": "severity", "required": True, "label": "Severity"},
            {"path": "recommendation", "min_length": 50, "label": "Recommendation"},
            {"path": "description", "min_length": 30, "label": "Description"},
        ],
    },
    5: {
        "array_field": "options",
        "per_item_fields": [
            {"path": "cost_estimate", "required": True, "label": "Cost estimate"},
            {"path": "timeline_months", "required": True, "label": "Timeline"},
            {"path": "pros_cons", "min_items": 3, "label": "Pros/Cons"},
        ],
    },
    6: {
        "fields": [
            {"path": "section_narratives.problem", "min_length": 50, "label": "Problem narrative"},
            {"path": "section_narratives.current_state", "min_length": 50, "label": "Current state"},
            {"path": "section_narratives.target_state", "min_length": 50, "label": "Target state"},
            {"path": "section_narratives.gap_analysis", "min_length": 50, "label": "Gap analysis"},
            {"path": "section_narratives.recommended_solution", "min_length": 50, "label": "Recommended solution"},
            {"path": "section_narratives.migration_approach", "min_length": 50, "label": "Migration approach"},
            {"path": "section_narratives.risk_register", "min_length": 50, "label": "Risk register"},
            {"path": "section_narratives.cost_model", "min_length": 50, "label": "Cost model"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class WizardAutoCompleteService:
    """Bulk field completion for wizard steps."""

    def complete_step(
        self,
        solution_id: int,
        step: int,
        current_data: dict,
        solution_context: dict,
        fields_to_complete: Optional[List[str]] = None,
    ) -> AutoCompleteResult:
        """Fill all empty/weak fields in a step.

        If fields_to_complete is None, fills everything below quality threshold.
        If provided, fills only those specific field paths.
        """
        # Identify what needs completing
        weak_fields = self._find_weak_fields(step, current_data, fields_to_complete)

        if not weak_fields:
            return AutoCompleteResult(
                completions=[], fields_completed=0, fields_skipped=0,
                estimated_quality_delta=0, cost_gbp=Decimal("0"),
            )

        # Call LLM to complete them
        completions, cost = self._llm_complete(step, current_data, solution_context, weak_fields)

        skipped = len(weak_fields) - len(completions)
        # Estimate quality delta: ~3 points per completed field, capped at 40
        delta = min(40, len(completions) * 3)

        return AutoCompleteResult(
            completions=completions,
            fields_completed=len(completions),
            fields_skipped=max(0, skipped),
            estimated_quality_delta=delta,
            cost_gbp=cost,
        )

    def complete_transition(
        self,
        solution_id: int,
        from_step: int,
        to_step: int,
        current_data: dict,
        solution_context: dict,
    ) -> AutoCompleteResult:
        """Fill fields needed by the NEXT step based on current step output."""
        return self.complete_step(solution_id, to_step, current_data, solution_context)

    def apply_completions(
        self,
        solution_id: int,
        accepted_fields: Dict[str, Any],
    ) -> dict:
        """Apply user-accepted completions to journey_state."""
        from app.models.solution_models import Solution

        solution = Solution.query.get(solution_id)
        if solution is None:
            return {"applied": 0}

        journey_state = solution.journey_state or {}
        applied = 0

        for field_path, value in accepted_fields.items():
            self._set_nested(journey_state, field_path, value)
            applied += 1

        # Track autocomplete stats
        stats = journey_state.get("_autocomplete_stats", {
            "fields_completed": 0, "fields_accepted": 0, "fields_rejected": 0,
        })
        stats["fields_accepted"] = stats.get("fields_accepted", 0) + applied
        journey_state["_autocomplete_stats"] = stats

        solution.journey_state = journey_state
        db.session.commit()

        return {"applied": applied}

    # ------------------------------------------------------------------
    # Field analysis
    # ------------------------------------------------------------------

    def _find_weak_fields(
        self, step: int, data: dict, restrict_to: Optional[List[str]] = None,
    ) -> List[dict]:
        """Identify fields that need completion."""
        spec = STEP_FIELD_SPECS.get(step)
        if not spec:
            return []

        weak = []

        if "fields" in spec:
            for field_spec in spec["fields"]:
                path = field_spec["path"]
                if restrict_to and path not in restrict_to:
                    continue
                value = self._get_nested(data, path)
                if self._is_weak(value, field_spec):
                    weak.append({
                        "path": path,
                        "label": field_spec.get("label", path),
                        "current_value": value,
                        "spec": field_spec,
                    })

        if "array_field" in spec:
            array = data.get(spec["array_field"], []) or []
            for idx, item in enumerate(array):
                if not isinstance(item, dict):
                    continue
                for field_spec in spec["per_item_fields"]:
                    full_path = f"{spec['array_field']}[{idx}].{field_spec['path']}"
                    if restrict_to and full_path not in restrict_to:
                        continue
                    value = self._get_nested(item, field_spec["path"])
                    if self._is_weak(value, field_spec):
                        item_name = item.get("name", f"item {idx}")
                        weak.append({
                            "path": full_path,
                            "label": f"{item_name}: {field_spec.get('label', field_spec['path'])}",
                            "current_value": value,
                            "spec": field_spec,
                        })

        return weak

    def _is_weak(self, value: Any, spec: dict) -> bool:
        """Check if a field value is below quality threshold."""
        if value is None or value == "" or value == []:
            return True
        if "min_length" in spec and isinstance(value, str) and len(value) < spec["min_length"]:
            return True
        if "min_items" in spec and isinstance(value, list) and len(value) < spec["min_items"]:
            return True
        return False

    # ------------------------------------------------------------------
    # LLM completion
    # ------------------------------------------------------------------

    def _llm_complete(
        self,
        step: int,
        data: dict,
        context: dict,
        weak_fields: List[dict],
    ) -> Tuple[List[FieldCompletion], Decimal]:
        """Call LLM to complete weak fields."""
        try:
            from app.modules.ai_chat.services.llm_service import LLMService

            if not LLMService.is_available():
                return [], Decimal("0")

            provider, model = LLMService._get_configured_provider()
            max_tokens = LLMService.get_max_tokens_limit(provider, model, requested_max=4096)

            prompt = self._build_prompt(step, data, context, weak_fields)
            raw, interaction = LLMService._call_llm(
                prompt=prompt, model=model, provider=provider, max_tokens=max_tokens,
            )

            cost = Decimal(str(getattr(interaction, "cost", 0) or 0))

            if not raw:
                return [], cost

            completions = self._parse_response(raw, weak_fields)
            return completions, cost

        except Exception:
            logger.exception("Auto-complete LLM call failed")
            return [], Decimal("0")

    def _build_prompt(
        self, step: int, data: dict, context: dict, weak_fields: List[dict],
    ) -> str:
        fields_desc = "\n".join(
            f"  - {wf['path']}: {wf['label']} (current: {json.dumps(wf['current_value'], default=str)[:100]})"
            for wf in weak_fields[:30]
        )

        data_str = json.dumps(data, default=str)[:3000]

        return f"""You are a senior enterprise architect completing an architecture specification. Fill every listed field to production quality.

RULES:
1. NEVER remove or contradict user-confirmed values
2. Only ADD missing detail, ENRICH sparse fields, COMPLETE partial specs
3. Every completion must be grounded in the solution context
4. Include source attribution: "derived_from_problem" | "industry_benchmark" | "inferred_from_constraints"
5. Be specific — "PostgreSQL 15 on AWS RDS Multi-AZ" not "a database"

SOLUTION CONTEXT:
- Problem: {context.get('problem_statement', '')[:600]}
- Domain: {context.get('business_domain', '')}
- Org size: {context.get('organization_size', '')}
- Budget: {context.get('budget_range', '')}
- Timeline: {context.get('timeline_months', '')} months
- Constraints: {', '.join(context.get('constraints', [])[:5])}

CURRENT STEP {step} DATA:
{data_str}

FIELDS TO COMPLETE:
{fields_desc}

Return ONLY a JSON array of objects:
[{{"field_path": "...", "completed_value": ..., "confidence": 0.0-1.0, "source": "...", "rationale": "..."}}]"""

    def _parse_response(self, raw: str, weak_fields: List[dict]) -> List[FieldCompletion]:
        """Parse LLM completion response."""
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()

            items = json.loads(text)
            if not isinstance(items, list):
                return []

            # Map weak fields by path for lookup
            weak_by_path = {wf["path"]: wf for wf in weak_fields}

            completions = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                path = item.get("field_path", "")
                if path not in weak_by_path:
                    continue
                completions.append(FieldCompletion(
                    field_path=path,
                    original_value=weak_by_path[path]["current_value"],
                    completed_value=item.get("completed_value"),
                    confidence=min(1.0, max(0.0, float(item.get("confidence", 0.7)))),
                    source=item.get("source", "inferred_from_constraints"),
                    rationale=item.get("rationale", ""),
                ))

            return completions

        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse auto-complete LLM response")
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_nested(self, data: dict, path: str) -> Any:
        """Get value at a dotted path like 'section_narratives.problem'."""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    def _set_nested(self, data: dict, path: str, value: Any) -> None:
        """Set value at a dotted/bracketed path like 'capabilities[2].description'."""
        import re
        # Handle array notation: capabilities[2].description
        parts = re.split(r'\.(?![^\[]*\])', path)
        current = data
        for i, part in enumerate(parts[:-1]):
            match = re.match(r'(\w+)\[(\d+)\]', part)
            if match:
                key, idx = match.group(1), int(match.group(2))
                if key not in current or not isinstance(current[key], list):
                    current[key] = []
                while len(current[key]) <= idx:
                    current[key].append({})
                current = current[key][idx]
            else:
                if part not in current or not isinstance(current.get(part), dict):
                    current[part] = {}
                current = current[part]

        last = parts[-1]
        match = re.match(r'(\w+)\[(\d+)\]', last)
        if match:
            key, idx = match.group(1), int(match.group(2))
            if key not in current or not isinstance(current[key], list):
                current[key] = []
            while len(current[key]) <= idx:
                current[key].append(None)
            current[key][idx] = value
        else:
            current[last] = value

    def to_dict(self, result: AutoCompleteResult) -> dict:
        return {
            "completions": [asdict(c) for c in result.completions],
            "fields_completed": result.fields_completed,
            "fields_skipped": result.fields_skipped,
            "estimated_quality_delta": result.estimated_quality_delta,
            "cost_gbp": str(result.cost_gbp),
        }
