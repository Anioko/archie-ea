"""Phase handoff planning for TOGAF deliverables."""

from typing import Any, Mapping

from app.services.togaf_deliverable_template_service import togaf_deliverable_template_service


ARCHITECTURE_VISION_HANDOFFS = [
    {
        "target_template_id": "statement_of_architecture_work",
        "phase": "A",
        "title": "Statement of Architecture Work",
        "source_sections": ["vision_statement", "scope", "stakeholders"],
    },
    {
        "target_template_id": "architecture_definition",
        "phase": "B/C/D",
        "title": "Architecture Definition",
        "source_sections": ["vision_statement", "drivers_goals_constraints", "summary_views"],
    },
    {
        "target_template_id": "capability_assessment",
        "phase": "A/E",
        "title": "Capability Assessment",
        "source_sections": ["stakeholders", "drivers_goals_constraints", "summary_views"],
    },
    {
        "target_template_id": "communications_plan",
        "phase": "A",
        "title": "Communications Plan",
        "source_sections": ["stakeholders", "scope"],
    },
]


class TOGAFDeliverableHandoffService:
    """Build downstream handoff guidance from current deliverable content."""

    def build_handoff_view(
        self,
        content: Mapping[str, Any],
        *,
        readiness_view: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        template_id = content.get("template_id")
        if template_id != "architecture_vision":
            return {"deliverables": [], "ready_targets": 0}

        sections = {section.get("key"): section for section in content.get("sections") or []}
        ready_section_keys = {
            section.get("key")
            for section in (readiness_view or {}).get("sections") or []
            if section.get("is_ready")
        }

        downstream = []
        for handoff in ARCHITECTURE_VISION_HANDOFFS:
            inherited_refs = []
            carried_sections = []
            for section_key in handoff["source_sections"]:
                section = sections.get(section_key) or {}
                if section:
                    carried_sections.append(section.get("title") or section_key.replace("_", " ").title())
                    inherited_refs.extend(section.get("source_ref_ids") or [])
            downstream.append(
                {
                    "target_template_id": handoff["target_template_id"],
                    "target_title": handoff["title"],
                    "phase": handoff["phase"],
                    "ready_for_handoff": set(handoff["source_sections"]).issubset(ready_section_keys),
                    "carried_sections": carried_sections,
                    "inherited_source_ref_count": len(set(inherited_refs)),
                    "section_count": togaf_deliverable_template_service.get_template(handoff["target_template_id"])["sections"].__len__(),
                }
            )

        return {
            "deliverables": downstream,
            "ready_targets": sum(1 for item in downstream if item["ready_for_handoff"]),
        }


togaf_deliverable_handoff_service = TOGAFDeliverableHandoffService()
