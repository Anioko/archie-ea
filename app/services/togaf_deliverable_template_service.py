"""Shared section schema for TOGAF deliverable authoring."""

from copy import deepcopy
from typing import Any


TOGAF_DELIVERABLE_CONTENT_SCHEMA_VERSION = "1.0"


def _section(
    key: str,
    title: str,
    description: str,
    *,
    required: bool = True,
    field_keys: list[str] | None = None,
    source_types: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "description": description,
        "required": required,
        "field_keys": field_keys or [],
        "source_types": source_types or [],
    }


TOGAF_DELIVERABLE_TEMPLATES: dict[str, dict[str, Any]] = {
    "architecture_vision": {
        "id": "architecture_vision",
        "name": "Architecture Vision",
        "adm_phase": "A",
        "description": "High-level vision aligned to scope, stakeholders, drivers, and summary views.",
        "sections": [
            _section("vision_statement", "Vision Statement", "Summarize the target outcome.", field_keys=["summary", "business_value"], source_types=["workflow_definition", "application_component", "solution_summary"]),
            _section("scope", "Scope", "Define in-scope, out-of-scope, and assumptions.", field_keys=["in_scope", "out_of_scope", "assumptions"], source_types=["workflow_definition", "workflow_steps", "application_component"]),
            _section("stakeholders", "Stakeholders and Concerns", "Capture stakeholder groups and decision concerns.", field_keys=["stakeholder_map", "concerns"], source_types=["application_ownership", "stakeholder_summary", "application_governance"]),
            _section("drivers_goals_constraints", "Drivers, Goals, and Constraints", "Record business drivers, goals, and constraints.", field_keys=["drivers", "goals", "constraints"], source_types=["application_component", "application_governance", "roadmap_summary"]),
            _section("summary_views", "Summary Views", "Reference the summary views supporting the vision.", field_keys=["value_chain_view", "solution_concept_view"], source_types=["application_component", "solution_summary", "roadmap_summary"]),
        ],
    },
    "statement_of_architecture_work": {
        "id": "statement_of_architecture_work",
        "name": "Statement of Architecture Work",
        "adm_phase": "A",
        "description": "Scope, engagement model, roles, and acceptance approach.",
        "sections": [
            _section("engagement_overview", "Engagement Overview", "Project request and engagement context.", field_keys=["request_background", "project_context"]),
            _section("scope_and_change_control", "Scope and Change Control", "Scope boundaries and change control.", field_keys=["scope", "change_control"]),
            _section("roles_deliverables", "Roles, Responsibilities, and Deliverables", "RACI and outputs.", field_keys=["roles", "deliverables", "raci"]),
            _section("plan_and_acceptance", "Plan and Acceptance", "Milestones, KPIs, and acceptance approach.", field_keys=["milestones", "kpis", "acceptance_procedure"]),
        ],
    },
    "architecture_definition": {
        "id": "architecture_definition",
        "name": "Architecture Definition",
        "adm_phase": "B/C/D",
        "description": "Baseline, target, and transition architecture across core domains.",
        "sections": [
            _section("scope_and_objectives", "Scope and Objectives", "Scope and architecture principles.", field_keys=["scope", "objectives", "principles"]),
            _section("baseline_architecture", "Baseline Architecture", "Current-state summary.", field_keys=["baseline_summary", "baseline_domains"]),
            _section("target_architecture", "Target Architecture", "Target-state summary.", field_keys=["target_summary", "target_domains"]),
            _section("gap_and_transition", "Gap Analysis and Transition", "Major gaps and transition states.", field_keys=["gap_analysis", "transition_states", "impact_summary"]),
        ],
    },
    "capability_assessment": {
        "id": "capability_assessment",
        "name": "Capability Assessment",
        "adm_phase": "A/E",
        "description": "Business, IT, architecture, and readiness assessment.",
        "sections": [
            _section("business_capability", "Business Capability Assessment", "Current and target business capability.", field_keys=["baseline_performance", "target_aspiration", "business_impacts"]),
            _section("it_capability", "IT Capability Assessment", "Operational and delivery capability.", field_keys=["change_maturity", "operational_maturity", "capacity"]),
            _section("architecture_maturity", "Architecture Maturity Assessment", "Governance, skills, and standards maturity.", field_keys=["governance_processes", "skills", "reuse_potential"]),
            _section("transformation_readiness", "Transformation Readiness", "Readiness factors and risks.", field_keys=["readiness_factors", "target_readiness", "risks"]),
        ],
    },
    "communications_plan": {
        "id": "communications_plan",
        "name": "Communications Plan",
        "adm_phase": "A",
        "description": "Stakeholder communications requirements, mechanisms, and cadence.",
        "sections": [
            _section("stakeholder_matrix", "Stakeholder Matrix", "Stakeholder groups and owners.", field_keys=["stakeholders", "needs", "owners"]),
            _section("communication_requirements", "Communication Requirements", "Key messages and communication risks.", field_keys=["key_messages", "risks", "success_factors"]),
            _section("mechanisms", "Communication Mechanisms", "Channels and forums.", field_keys=["channels", "forums", "repositories"]),
            _section("timetable", "Communication Timetable", "Activities, milestones, and cadence.", field_keys=["activities", "milestones", "cadence", "resources"]),
        ],
    },
}


class TOGAFDeliverableTemplateService:
    """Return canonical TOGAF deliverable templates and initial section payloads."""

    def list_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "id": template_id,
                "name": template["name"],
                "adm_phase": template["adm_phase"],
                "description": template["description"],
                "section_count": len(template["sections"]),
            }
            for template_id, template in TOGAF_DELIVERABLE_TEMPLATES.items()
        ]

    def get_template(self, template_id: str) -> dict[str, Any]:
        template = TOGAF_DELIVERABLE_TEMPLATES.get(template_id)
        if template is None:
            raise ValueError(f"Unknown TOGAF deliverable template: {template_id!r}")
        return deepcopy(template)

    def build_initial_content(
        self,
        template_id: str,
        *,
        context_type: str | None = None,
        context_id: int | None = None,
    ) -> dict[str, Any]:
        template = self.get_template(template_id)
        return {
            "schema_version": TOGAF_DELIVERABLE_CONTENT_SCHEMA_VERSION,
            "template_id": template["id"],
            "template_name": template["name"],
            "adm_phase": template["adm_phase"],
            "context": {
                "context_type": context_type,
                "context_id": context_id,
            },
            "sections": [self._build_section_payload(section) for section in template["sections"]],
            "source_refs": [],
            "readiness_checks": [],
        }

    @staticmethod
    def _build_section_payload(section: dict[str, Any]) -> dict[str, Any]:
        return {
            "key": section["key"],
            "title": section["title"],
            "description": section["description"],
            "required": section["required"],
            "status": "not_started",
            "fields": {field_key: None for field_key in section.get("field_keys", [])},
            "generated_narrative": "",
            "manual_narrative": "",
            "source_ref_ids": [],
            "readiness": {
                "state": "missing_required_content" if section["required"] else "optional",
                "blocking_issues": [],
                "warnings": [],
            },
            "source_types": list(section.get("source_types", [])),
        }


togaf_deliverable_template_service = TOGAFDeliverableTemplateService()
