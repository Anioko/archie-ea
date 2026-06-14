"""Step 5 Migration Planner — gap identification, dependency sequencing, work packages.

Identifies novel elements (gaps), sequences by ArchiMate layer dependency rules,
generates phased work packages via LLM, and persists as RoadmapTask rows.
"""

import json
import logging
import re

from app import db

logger = logging.getLogger(__name__)

# ArchiMate layer dependency order (infrastructure first, people last)
LAYER_SEQUENCE = {
    "technology": 1,  # Infrastructure first
    "application": 2,  # Apps need infra
    "business": 3,     # Process changes need app support
}

MIGRATION_PROMPT = """You are creating a migration/implementation plan for this solution:

{problem_summary}

ARCHITECTURE ELEMENTS TO IMPLEMENT:
{gap_elements}

EXISTING ELEMENTS (already in place — no work needed):
{existing_elements}

CONSTRAINTS:
{constraints}

DEPENDENCY RULES:
1. Technology layer (infrastructure) must be deployed before Application layer
2. Application layer must be deployed before Business layer process changes
3. Within each layer, data/storage elements before service elements
4. Integration elements after both source and target components exist

Generate 3-4 IMPLEMENTATION PHASES with work packages. Each phase should:
- Have a clear name and goal
- List specific work packages with estimated effort
- Link each work package to specific architecture elements
- Specify dependencies between work packages

Return ONLY valid JSON:
{{
    "phases": [
        {{
            "id": "phase1",
            "name": "Phase name",
            "goal": "What this phase achieves",
            "duration_weeks": 8,
            "work_packages": [
                {{
                    "id": "wp1",
                    "name": "Work package name",
                    "description": "What needs to be done",
                    "estimated_hours": 160,
                    "priority": "high|medium|low",
                    "element_names": ["Architecture element names this delivers"],
                    "depends_on": [],
                    "deliverables": ["What gets delivered"],
                    "skills_needed": ["Required team skills"]
                }}
            ]
        }}
    ],
    "total_estimated_hours": 640,
    "critical_path": ["wp1", "wp3", "wp5"]
}}"""


class MigrationPlannerService:
    """Generates phased migration plans and persists work packages as RoadmapTask rows."""

    def generate_plan(self, architecture_elements, problem_summary, solution_id, constraints=None):
        """Generate a phased migration plan from architecture gaps.

        Args:
            architecture_elements: dict with elements_by_layer from Step 3
            problem_summary: enriched problem description
            solution_id: for persisting RoadmapTask rows
            constraints: optional dict with timeline/budget/team info

        Returns:
            dict with phases, work_packages, total_hours
        """
        gaps, existing = self._identify_gaps(architecture_elements)

        if not gaps:
            return {"phases": [], "total_estimated_hours": 0, "message": "No gaps identified — all elements already exist"}

        gap_text = self._format_elements(gaps)
        existing_text = self._format_elements(existing) if existing else "None"
        constraints_text = self._format_constraints(constraints)

        prompt = MIGRATION_PROMPT.format(
            problem_summary=problem_summary,
            gap_elements=gap_text,
            existing_elements=existing_text,
            constraints=constraints_text,
        )

        try:
            from app.modules.ai_chat.services.llm_service import LLMService
            provider, model = LLMService._get_configured_provider()
            raw_text, _ = LLMService._call_llm(prompt=prompt, model=model, provider=provider)

            parsed = _parse_llm_json(raw_text)
            if not parsed:
                return {"phases": [], "errors": ["Failed to parse LLM response"]}

            phases = parsed.get("phases", [])

            # Persist work packages as RoadmapTask rows
            tasks_created = self._persist_roadmap_tasks(phases, solution_id)

            logger.info(
                "Migration plan: %d phases, %d work packages, %d RoadmapTasks created",
                len(phases), sum(len(p.get("work_packages", [])) for p in phases), tasks_created,
            )

            return {
                "phases": phases,
                "total_estimated_hours": parsed.get("total_estimated_hours", 0),
                "critical_path": parsed.get("critical_path", []),
                "tasks_created": tasks_created,
                "errors": [],
            }

        except Exception as e:
            logger.error("Migration planning failed: %s", e)
            return {"phases": [], "errors": [str(e)]}

    def _identify_gaps(self, elements_by_layer):
        """Split elements into gaps (novel, need building) and existing (already deployed).

        Returns (gaps, existing) — both are lists of element dicts with layer info.
        """
        gaps = []
        existing = []
        for layer in ("technology", "application", "business"):
            for el in elements_by_layer.get(layer, []):
                enriched = {**el, "layer": layer, "sequence": LAYER_SEQUENCE.get(layer, 99)}
                if el.get("source") in ("existing", "catalog"):
                    existing.append(enriched)
                else:
                    gaps.append(enriched)

        # Sort gaps by layer sequence (infra first)
        gaps.sort(key=lambda x: x.get("sequence", 99))
        return gaps, existing

    def _persist_roadmap_tasks(self, phases, solution_id):
        """Persist work packages as RoadmapTask rows linked to the solution."""
        from app.models.roadmap import RoadmapTask

        created = 0
        for phase in phases:
            phase_name = phase.get("name", "Unknown Phase")
            for wp in phase.get("work_packages", []):
                task = RoadmapTask(
                    title=wp.get("name", "Unnamed Work Package"),
                    description=wp.get("description", ""),
                    estimated_hours=wp.get("estimated_hours", 0),
                    priority=wp.get("priority", "medium"),
                    status="planned",
                    plateau_from=phase.get("id"),
                    dependencies=json.dumps(wp.get("depends_on", [])),
                    capability_level=wp.get("priority", "medium"),
                )
                db.session.add(task)
                created += 1

        if created:
            db.session.commit()

        return created

    def _format_elements(self, elements):
        """Format element list for LLM prompt."""
        lines = []
        current_layer = None
        for el in elements:
            layer = el.get("layer", "unknown")
            if layer != current_layer:
                current_layer = layer
                lines.append(f"\n{layer.upper()} LAYER:")
            lines.append(f"  - {el.get('type', '?')}: {el.get('name', '?')} — {el.get('description', '')}")
        return "\n".join(lines) if lines else "No elements"

    def _format_constraints(self, constraints):
        """Format constraints for LLM prompt."""
        if not constraints:
            return "No specific constraints provided"
        lines = []
        if constraints.get("timeline"):
            lines.append(f"- Timeline: {constraints['timeline']}")
        if constraints.get("budget"):
            lines.append(f"- Budget: {constraints['budget']}")
        if constraints.get("team_size"):
            lines.append(f"- Team: {constraints['team_size']}")
        return "\n".join(lines) if lines else "No specific constraints provided"


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
