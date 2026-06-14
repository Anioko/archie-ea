"""
Implementation Wizard Service - Plan C + Plan B Hybrid
7 - step wizard for implementation planning
"""
import logging
from typing import Any, Dict, List, Optional

from app import db
from app.models import (
    ApplicationCapability,
    ArchiMateElement,
    ArchiMateRelationship,
    ArchitectureModel,
    BusinessCapability,
    GenerationPipeline,
    TechnologyStack,
    WorkflowPipeline,
    WorkflowTemplate,
)
from app.services.archimate.implementation_context_engine import ImplementationContextEngine
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ImplementationWizardService:
    """
    Interactive 7 - step wizard for implementation planning
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.context_engine = ImplementationContextEngine()

    def step1_architecture_summary(self, architecture_id: int) -> Dict[str, Any]:
        """
        Step 1: Review Generated Architecture
        Display architecture summary with layer distribution
        """
        model = ArchitectureModel.query.get(architecture_id)
        if not model:
            raise ValueError(f"Architecture model {architecture_id} not found")

        elements = ArchiMateElement.query.filter_by(architecture_id=architecture_id).all()

        # Count by layer
        layer_counts = {}
        for elem in elements:
            layer = elem.layer or "unknown"
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

        # Count by type
        type_counts = {}
        for elem in elements:
            elem_type = elem.element_type or "unknown"
            type_counts[elem_type] = type_counts.get(elem_type, 0) + 1

        return {
            "model": {
                "id": model.id,
                "name": model.name,
                "description": model.description,
                "created_at": model.created_at.isoformat() if model.created_at else None,
            },
            "summary": {
                "total_elements": len(elements),
                "layer_distribution": layer_counts,
                "type_distribution": type_counts,
            },
            "layers": {
                "motivation": layer_counts.get("motivation", 0),
                "strategy": layer_counts.get("strategy", 0),
                "business": layer_counts.get("business", 0),
                "application": layer_counts.get("application", 0),
                "technology": layer_counts.get("technology", 0),
                "physical": layer_counts.get("physical", 0),
                "implementation": layer_counts.get("implementation", 0),
                "migration": layer_counts.get("migration", 0),
            },
            "ready_for_implementation": (
                layer_counts.get("application", 0) > 0 or layer_counts.get("technology", 0) > 0
            ),
        }

    def step2_identify_scope(self, architecture_id: int) -> Dict[str, Any]:
        """
        Step 2: Identify Implementation Scope
        User selects which elements need implementation

        Returns selectable elements from application and technology layers
        """
        elements = ArchiMateElement.query.filter(
            ArchiMateElement.architecture_id == architecture_id,
            ArchiMateElement.layer.in_(["application", "technology"]),
        ).all()

        selectable_elements = []
        for elem in elements:
            selectable_elements.append(
                {
                    "id": elem.id,
                    "name": elem.name,
                    "type": elem.element_type,
                    "layer": elem.layer,
                    "description": elem.description,
                    "properties": elem.properties or {},
                    "implementation_type": self._determine_implementation_type(elem),
                }
            )

        return {
            "selectable_elements": selectable_elements,
            "total_count": len(selectable_elements),
            "application_count": len([e for e in elements if e.layer == "application"]),
            "technology_count": len([e for e in elements if e.layer == "technology"]),
        }

    def _determine_implementation_type(self, element: ArchiMateElement) -> str:
        """Determine what kind of implementation this element needs"""
        element_type = element.element_type or ""

        if "Component" in element_type:
            return "new_application"
        elif "Service" in element_type:
            return "new_service"
        elif "Interface" in element_type:
            return "new_integration"
        elif "Node" in element_type or "Device" in element_type:
            return "infrastructure"
        elif "Data" in element_type:
            return "data_migration"
        else:
            return "other"

    async def step3_analyze_context(
        self, architecture_id: int, selected_element_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Step 3: AI Analyzes Existing Systems & Capabilities
        Query existing context to inform implementation decisions
        """
        # Use existing ImplementationContextEngine
        selected_elements = ArchiMateElement.query.filter(
            ArchiMateElement.id.in_(selected_element_ids)
        ).all()

        selected_data = [
            {"id": elem.id, "name": elem.name, "type": elem.element_type, "layer": elem.layer}
            for elem in selected_elements
        ]

        # Analyze context
        context = await self.context_engine.analyze_context(selected_data)

        return {
            "selected_elements": selected_data,
            "technology_stacks": [
                {
                    "id": ts.id,
                    "name": ts.name,
                    "maturity_level": ts.maturity_level,
                    "cost_rating": ts.cost_rating,
                }
                for ts in context.get("technology_stacks", [])
            ],
            "capabilities": [
                {"id": cap.id, "name": cap.name, "maturity_level": cap.maturity_level}
                for cap in context.get("capabilities", [])
            ],
            "vendors": [
                {
                    "id": app.id,
                    "name": app.application_name,
                    "replacement_priority": app.replacement_priority,
                }
                for app in context.get("vendors", [])
            ],
            "workflow_templates": [
                {"id": wf.id, "name": wf.name, "complexity": wf.complexity}
                for wf in context.get("workflows", [])
            ],
            "pipelines": [
                {"id": pipe.id, "name": pipe.name, "target_platform": pipe.target_platform}
                for pipe in context.get("pipelines", [])
            ],
            "constraints": context.get("constraints", {}),
            "recommendations": context.get("recommendations", {}),
        }

    async def step4_generate_roadmap(
        self,
        architecture_id: int,
        selected_element_ids: List[int],
        constraints: Dict[str, Any],
        provider: str = "claude",
    ) -> Dict[str, Any]:
        """
        Step 4: Generate Implementation Roadmap
        AI generates Work Packages, Deliverables, Plateaus, Gaps
        """
        # Use ImplementationContextEngine to generate implementation layer
        implementation_data, interaction = await self.context_engine.generate_implementation_layer(
            architecture_id=architecture_id, constraints=constraints, provider=provider
        )

        return {
            "work_packages": implementation_data.get("work_packages", []),
            "deliverables": implementation_data.get("deliverables", []),
            "plateaus": implementation_data.get("plateaus", []),
            "gaps": implementation_data.get("gaps", []),
            "total_effort": sum(
                wp.get("properties", {}).get("effort_estimate_weeks", 0)
                for wp in implementation_data.get("work_packages", [])
            ),
            "total_tokens": interaction.total_tokens if interaction else 0,
            "cost": interaction.cost if interaction else 0.0,
        }

    def step5_organize_phases(
        self,
        work_packages: List[Dict[str, Any]],
        deliverables: List[Dict[str, Any]],
        plateaus: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Step 5: Select Delivery Phases
        Interactive phase assignment (this is UI-driven, backend provides structure)
        """
        # Group work packages by effort and dependencies
        phases = self._suggest_phases(work_packages, deliverables, plateaus)

        return {
            "suggested_phases": phases,
            "total_duration": sum(phase["duration_weeks"] for phase in phases),
            "work_packages": work_packages,
            "deliverables": deliverables,
            "plateaus": plateaus,
        }

    def _suggest_phases(
        self, work_packages: List[Dict], deliverables: List[Dict], plateaus: List[Dict]
    ) -> List[Dict]:
        """Suggest logical delivery phases"""
        phases = []

        # Simple heuristic: group by effort and create 3 - month phases
        sorted_wps = sorted(
            work_packages, key=lambda wp: wp.get("properties", {}).get("effort_estimate_weeks", 0)
        )

        current_phase = {
            "name": "Phase 1: Foundation",
            "duration_weeks": 12,
            "work_packages": [],
            "deliverables": [],
            "plateau": None,
        }

        accumulated_weeks = 0
        phase_num = 1

        for wp in sorted_wps:
            effort = wp.get("properties", {}).get("effort_estimate_weeks", 0)

            if accumulated_weeks + effort > 12 and current_phase["work_packages"]:
                # Start new phase
                phases.append(current_phase)
                phase_num += 1
                current_phase = {
                    "name": f"Phase {phase_num}",
                    "duration_weeks": 12,
                    "work_packages": [],
                    "deliverables": [],
                    "plateau": None,
                }
                accumulated_weeks = 0

            current_phase["work_packages"].append(wp)
            accumulated_weeks += effort

        if current_phase["work_packages"]:
            phases.append(current_phase)

        return phases

    async def step6_match_workflows(
        self, work_packages: List[Dict[str, Any]], provider: str = "claude"
    ) -> Dict[str, Any]:
        """
        Step 6: Match to Workflow Templates
        AI matches work packages to existing workflow templates
        """
        workflow_templates = WorkflowTemplate.query.filter_by(is_active=True).all()

        matches = []
        for wp in work_packages:
            match = await self._match_single_work_package(wp, workflow_templates, provider)
            matches.append(match)

        return {
            "matches": matches,
            "total_matched": len([m for m in matches if m["matched_template"]]),
            "total_unmatched": len([m for m in matches if not m["matched_template"]]),
        }

    async def _match_single_work_package(
        self,
        work_package: Dict[str, Any],
        workflow_templates: List[WorkflowTemplate],
        provider: str,
    ) -> Dict[str, Any]:
        """Match a single work package to best workflow template"""
        import json

        templates_info = [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "complexity": wf.complexity,
                "estimated_duration": wf.estimated_duration,
            }
            for wf in workflow_templates
        ]

        prompt = f"""You are an implementation planning expert. Match this work package to the best workflow template.

WORK PACKAGE:
Name: {work_package.get('name')}
Description: {work_package.get('description', 'N/A')}
Effort: {work_package.get('properties', {}).get('effort_estimate_weeks', 'N/A')} weeks
Technology Stack: {work_package.get('properties', {}).get('technology_stack', 'N/A')}
Deliverables: {work_package.get('properties', {}).get('deliverables', [])}

AVAILABLE WORKFLOW TEMPLATES:
{json.dumps(templates_info, indent=2)}

TASK:
1. Select the best matching workflow template (or null if no good match)
2. Provide confidence score (0.0 - 1.0)
3. List any customizations needed
4. Suggest pipeline stages

Return JSON:
{{
    "matched_template_id": 123 or null,
    "confidence": 0.85,
    "rationale": "This template matches because...",
    "customizations_needed": ["List", "of", "changes"],
    "pipeline_stages": ["stage1", "stage2"]
}}
"""

        try:
            response, interaction = await self.llm_service.generate_completion(
                prompt=prompt, provider=provider, temperature=0.3, max_tokens=1000
            )

            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                match_result = json.loads(json_match.group())
            else:
                match_result = {"matched_template_id": None, "confidence": 0.0}

            # Hydrate matched template
            matched_template = None
            if match_result.get("matched_template_id"):
                matched_template = WorkflowTemplate.query.get(match_result["matched_template_id"])

            return {
                "work_package": work_package,
                "matched_template": {"id": matched_template.id, "name": matched_template.name}
                if matched_template
                else None,
                "confidence": match_result.get("confidence", 0.0),
                "rationale": match_result.get("rationale", ""),
                "customizations_needed": match_result.get("customizations_needed", []),
                "pipeline_stages": match_result.get("pipeline_stages", []),
            }

        except Exception as e:
            logger.error(f"Error matching work package: {str(e)}")
            return {
                "work_package": work_package,
                "matched_template": None,
                "confidence": 0.0,
                "rationale": f"Error: {str(e)}",
                "customizations_needed": [],
                "pipeline_stages": [],
            }

    def step7_prepare_execution(
        self, architecture_id: int, matched_work_packages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Step 7: One-Click Code Generation
        Prepare for workflow execution
        """
        execution_plan = []

        for match in matched_work_packages:
            wp = match["work_package"]
            template = match["matched_template"]

            if not template:
                continue

            execution_plan.append(
                {
                    "work_package_id": wp.get("id"),
                    "work_package_name": wp.get("name"),
                    "template_id": template["id"],
                    "template_name": template["name"],
                    "confidence": match["confidence"],
                    "estimated_duration": wp.get("properties", {}).get("effort_estimate_weeks", 0),
                    "ready_to_execute": match["confidence"] >= 0.7,
                }
            )

        return {
            "execution_plan": execution_plan,
            "total_workflows": len(execution_plan),
            "ready_to_execute": len([p for p in execution_plan if p["ready_to_execute"]]),
            "needs_review": len([p for p in execution_plan if not p["ready_to_execute"]]),
        }

    def execute_work_package(
        self, architecture_id: int, work_package_id: int, template_id: int, user_id: int
    ) -> Dict[str, Any]:
        """
        Execute a single work package as a workflow
        Creates WorkflowPipeline instance and queues execution
        """
        from app.tasks.workflow_tasks import execute_workflow_pipeline

        work_package = ArchiMateElement.query.get(work_package_id)
        if not work_package:
            raise ValueError(f"Work package {work_package_id} not found")

        template = WorkflowTemplate.query.get(template_id)
        if not template:
            raise ValueError(f"Workflow template {template_id} not found")

        # Create WorkflowPipeline instance
        workflow = WorkflowPipeline(
            name=f"Implementation: {work_package.name}",
            template_id=template.id,
            architecture_id=architecture_id,
            created_by_id=user_id,
            config={
                "work_package_id": work_package_id,
                "work_package_name": work_package.name,
                "deliverables": work_package.properties.get("deliverables", []),
                "technology_stack": work_package.properties.get("technology_stack"),
            },
        )

        db.session.add(workflow)
        db.session.commit()

        # Queue async execution
        try:
            job = execute_workflow_pipeline.queue(workflow.id)
            job_id = job.id
        except Exception as e:
            logger.error(f"Failed to queue workflow execution: {str(e)}")
            job_id = None

        return {
            "workflow_id": workflow.id,
            "job_id": job_id,
            "status": "queued",
            "work_package_name": work_package.name,
            "template_name": template.name,
        }
