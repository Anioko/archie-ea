"""Phase-aware LLM Suggestion Generator (BPP-009).

Takes the assembled context from SolutionContextAssembler and generates
per-TOGAF-phase element suggestions.  For each phase the LLM receives
the assembled context and returns suggestions split into existing
elements (by ID) and proposed new elements (with names and types).
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app import db

logger = logging.getLogger(__name__)

# Phase → allowed ArchiMate element types
PHASE_ELEMENT_TYPES: Dict[str, List[str]] = {
    "A": ["Stakeholder", "Driver", "Goal", "Constraint", "Principle", "Assessment"],
    "B": [
        "BusinessProcess", "BusinessService", "BusinessActor",
        "BusinessRole", "BusinessObject", "BusinessFunction",
    ],
    "C": [
        "ApplicationComponent", "ApplicationService",
        "ApplicationInterface", "DataObject",
    ],
    "D": [
        "Node", "SystemSoftware", "Device",
        "CommunicationNetwork", "Artifact",
    ],
    "E": ["VendorProduct", "APQCProcess"],  # non-ArchiMate, handled separately
    "F": ["WorkPackage", "Plateau", "Deliverable", "Gap"],
    "G": [],  # Governance — no element suggestions, static templates
    "H": ["Metric"],  # derived from goals
}

# Phase → ArchiMate layer for filtering
PHASE_LAYERS: Dict[str, str] = {
    "A": "motivation",
    "B": "business",
    "C": "application",
    "D": "technology",
    "F": "implementation",
}

# LLM prompt template for per-phase suggestion
_SUGGESTION_PROMPT = """You are an enterprise architect using ArchiMate 3.2 and TOGAF ADM.

Given the following context about an existing enterprise architecture, suggest
ArchiMate elements for TOGAF ADM Phase {phase_letter} ({phase_name}) of a solution.

SOLUTION:
- Name: {solution_name}
- Description: {solution_description}
- Type: {solution_type}
- Business Domain: {business_domain}

EXISTING LINKED APPLICATIONS ({app_count}):
{linked_apps_text}

EXISTING LINKED ARCHIMATE ELEMENTS ({element_count}):
{linked_elements_text}

RELATIONSHIPS IN THE GRAPH ({rel_count}):
{relationships_text}

SIMILAR SOLUTIONS:
{similar_solutions_text}

INSTRUCTIONS:
1. Suggest elements for Phase {phase_letter} only.
2. Allowed element types for this phase: {allowed_types}
3. PREFER existing elements (reference by ID) over creating new ones.
4. For each suggestion, provide a confidence score (0.0-1.0) and a reason
   explaining WHY this element is relevant to the solution.
5. If suggesting an existing element, include the ArchiMate relationship type
   that connects it to the solution context (serving, realization, etc.)

Return JSON:
{{
  "existing_elements": [
    {{"element_id": 42, "name": "...", "type": "...", "layer": "...",
      "confidence": 0.9, "reason": "...", "relationship_type": "serving"}}
  ],
  "new_elements": [
    {{"name": "...", "type": "...", "layer": "...",
      "confidence": 0.6, "reason": "..."}}
  ]
}}
"""

PHASE_NAMES = {
    "A": "Architecture Vision",
    "B": "Business Architecture",
    "C": "Information Systems Architecture",
    "D": "Technology Architecture",
    "E": "Opportunities & Solutions",
    "F": "Migration Planning",
    "G": "Implementation Governance",
    "H": "Architecture Change Management",
}


class SolutionSuggestionGenerator:
    """Generate per-phase element suggestions using LLM + enterprise context."""

    def __init__(self, llm_service=None):
        """Initialize with an optional LLM service.

        Args:
            llm_service: An object with a ``generate_from_prompt(prompt)``
                method.  If None, the service will attempt to import
                the default LLMService at call time.
        """
        self._llm_service = llm_service

    @property
    def llm_service(self):
        if self._llm_service is None:
            try:
                from app.services.llm_service import LLMService
                self._llm_service = LLMService()
            except ImportError:
                logger.warning("LLMService not available")
        return self._llm_service

    def generate_suggestions(
        self,
        context: Dict[str, Any],
        target_phases: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, List]]:
        """Generate element suggestions for each target phase.

        Args:
            context: Output from SolutionContextAssembler.assemble().
            target_phases: List of phase letters (e.g. ["A", "B", "C"]).
                Defaults to all phases A-H.

        Returns:
            Dict keyed by phase letter, each containing
            ``existing_elements`` and ``new_elements`` arrays.
        """
        if target_phases is None:
            target_phases = list(PHASE_ELEMENT_TYPES.keys())

        solution = context.get("solution") or {}
        results: Dict[str, Dict[str, List]] = {}

        for phase in target_phases:
            allowed_types = PHASE_ELEMENT_TYPES.get(phase, [])
            if not allowed_types and phase not in ("E", "G", "H"):
                results[phase] = {"existing_elements": [], "new_elements": []}
                continue

            # Build the prompt
            prompt = self._build_prompt(phase, context, allowed_types)

            # Call LLM
            raw_response = self._call_llm(prompt)

            # Parse and validate
            phase_result = self._parse_response(raw_response, phase)

            # Filter by confidence
            phase_result["existing_elements"] = [
                e for e in phase_result["existing_elements"]
                if e.get("confidence", 0) >= 0.3
            ]
            phase_result["new_elements"] = [
                e for e in phase_result["new_elements"]
                if e.get("confidence", 0) >= 0.3
            ]

            # Validate existing element IDs exist in DB
            phase_result["existing_elements"] = self._validate_element_ids(
                phase_result["existing_elements"]
            )

            # Validate types match the phase
            if allowed_types:
                phase_result["existing_elements"] = [
                    e for e in phase_result["existing_elements"]
                    if e.get("type") in allowed_types
                ]
                phase_result["new_elements"] = [
                    e for e in phase_result["new_elements"]
                    if e.get("type") in allowed_types
                ]

            results[phase] = phase_result

        return results

    def _build_prompt(
        self, phase: str, context: Dict, allowed_types: List[str]
    ) -> str:
        solution = context.get("solution") or {}
        linked_apps = context.get("linked_apps", [])
        linked_elements = context.get("linked_elements", [])
        relationships = context.get("first_degree_relationships", [])
        similar = context.get("similar_solutions", [])

        return _SUGGESTION_PROMPT.format(
            phase_letter=phase,
            phase_name=PHASE_NAMES.get(phase, phase),
            solution_name=solution.get("name", ""),
            solution_description=solution.get("description", ""),
            solution_type=solution.get("solution_type", ""),
            business_domain=solution.get("business_domain", ""),
            app_count=len(linked_apps),
            linked_apps_text="\n".join(
                f"- {a.get('name', '?')} (id={a.get('id')}, status={a.get('lifecycle_status', '?')})"
                for a in linked_apps[:20]
            ) or "(none)",
            element_count=len(linked_elements),
            linked_elements_text="\n".join(
                f"- {e.get('name', '?')} (id={e.get('id')}, type={e.get('type')}, layer={e.get('layer')})"
                for e in linked_elements[:30]
            ) or "(none)",
            rel_count=len(relationships),
            relationships_text="\n".join(
                f"- {r.get('source_id')} --{r.get('type')}--> {r.get('target_id')}"
                for r in relationships[:30]
            ) or "(none)",
            similar_solutions_text="\n".join(
                f"- {s.get('name', '?')} (id={s.get('id')})"
                for s in similar[:5]
            ) or "(none)",
            allowed_types=", ".join(allowed_types),
        )

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM service and return raw response text."""
        svc = self.llm_service
        if svc is None:
            logger.warning("No LLM service — returning empty suggestions")
            return '{"existing_elements": [], "new_elements": []}'

        try:
            response = svc.generate_from_prompt(prompt)
            if isinstance(response, dict):
                return json.dumps(response)
            return str(response)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return '{"existing_elements": [], "new_elements": []}'

    def _parse_response(self, raw: str, phase: str) -> Dict[str, List]:
        """Parse LLM JSON response into structured suggestions."""
        try:
            # Extract JSON from markdown code blocks if present
            text = raw.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)
            return {
                "existing_elements": data.get("existing_elements", []),
                "new_elements": data.get("new_elements", []),
            }
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.warning("Failed to parse LLM response for phase %s: %s", phase, e)
            return {"existing_elements": [], "new_elements": []}

    def _validate_element_ids(self, elements: List[Dict]) -> List[Dict]:
        """Remove suggestions that reference non-existent element IDs."""
        if not elements:
            return elements

        from app.models.archimate_core import ArchiMateElement

        ids = [e.get("element_id") for e in elements if e.get("element_id")]
        if not ids:
            return elements

        try:
            existing_ids = set(
                r[0] for r in
                db.session.query(ArchiMateElement.id)
                .filter(ArchiMateElement.id.in_(ids))
                .all()
            )
        except Exception:
            # If DB query fails, return all (don't filter)
            return elements

        return [
            e for e in elements
            if e.get("element_id") in existing_ids
        ]
