"""
-> app.modules.architecture.services.modeling_service

ArchiMate Model Generator Service

Generates complete ArchiMate 3.2 models across all layers (Business, Application, Technology, Motivation, Strategy)
from capability analysis and solution options for the Architecture Assistant.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple

from app import db
from app.models.unified_capability import UnifiedCapability
from app.modules.architecture.services.archimate_validation_engine import (
    ArchiMateValidationEngine,
)
from app.services.archimate.archimate_service import ArchiMateService
from app.services.archimate.archimate_viewpoint_service import ArchiMateViewpointService

logger = logging.getLogger(__name__)


class ArchiMateModelGenerator:
    """
    Service for generating complete ArchiMate 3.2 models from architecture analysis.

    Generates elements and relationships across all 5 ArchiMate layers:
    - Business Layer: Business capabilities, processes, actors, services
    - Application Layer: Application components, services, interfaces
    - Technology Layer: Technology services, devices, system software
    - Motivation Layer: Goals, principles, requirements, constraints
    - Strategy Layer: Capabilities, resources, courses of action
    """

    def __init__(self):
        self.archimate_service = ArchiMateService()
        self.viewpoint_service = ArchiMateViewpointService()

    def generate_model_from_capability_analysis(
        self,
        capability_id: int,
        solution_options: List[Dict[str, Any]],
        gap_analysis: Dict[str, Any],
        include_viewpoints: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate complete ArchiMate model from capability analysis results.

        Args:
            capability_id: ID of the analyzed capability
            solution_options: List of solution options with vendor/product details
            gap_analysis: Gap analysis results
            include_viewpoints: Whether to include generated viewpoints

        Returns:
            Complete ArchiMate model with elements, relationships, and viewpoints
        """
        logger.info(f"Generating ArchiMate model for capability {capability_id}")

        try:
            # Validate inputs
            if gap_analysis is None:
                gap_analysis = {
                    "risks": [],
                    "dependencies": [],
                    "gap_analysis": {"current_coverage": 50, "target_coverage": 100},
                }

            # Get capability details
            capability = db.session.get(UnifiedCapability, capability_id)
            if not capability:
                return {"error": f"Capability {capability_id} not found"}

            # Initialize model structure
            model = self._initialize_model(capability)

            # Generate elements for each layer
            model["elements"] = []
            model["relationships"] = []

            # Business Layer
            business_elements, business_relationships = self._generate_business_layer(
                capability, gap_analysis
            )
            model["elements"].extend(business_elements)
            model["relationships"].extend(business_relationships)

            # Application Layer
            app_elements, app_relationships = self._generate_application_layer(
                capability, solution_options
            )
            model["elements"].extend(app_elements)
            model["relationships"].extend(app_relationships)

            # Technology Layer
            tech_elements, tech_relationships = self._generate_technology_layer(solution_options)
            model["elements"].extend(tech_elements)
            model["relationships"].extend(tech_relationships)

            # Motivation Layer
            motivation_elements, motivation_relationships = self._generate_motivation_layer(
                capability, gap_analysis
            )
            model["elements"].extend(motivation_elements)
            model["relationships"].extend(motivation_relationships)

            # Strategy Layer
            strategy_elements, strategy_relationships = self._generate_strategy_layer(
                capability, solution_options
            )
            model["elements"].extend(strategy_elements)
            model["relationships"].extend(strategy_relationships)

            # Generate viewpoints
            model["viewpoints"] = self._generate_viewpoints(model)

            # Add metadata
            model["metadata"] = {
                "generated_at": datetime.utcnow().isoformat(),
                "generator_version": "1.0.0",
                "archimate_version": "3.2",
                "source": "architecture_assistant",
                "capability_id": capability_id,
                "element_count": len(model["elements"]),
                "relationship_count": len(model["relationships"]),
                "viewpoint_count": len(model["viewpoints"]),
            }

            # Validate generated elements against the ArchiMate 3.2 metamodel.
            # ArchiMateValidationEngine is the canonical source of valid types —
            # its all_element_types set is built from the full specification.
            validation_errors: List[str] = []
            _validator = ArchiMateValidationEngine()
            valid_types = _validator.all_element_types
            for element in model.get("elements", []):
                elem_type = element.get("type")
                if elem_type not in valid_types:
                    validation_errors.append(
                        f"Invalid element type '{elem_type}' for element "
                        f"'{element.get('name', 'unknown')}' — not a valid "
                        f"ArchiMate 3.2 element type."
                    )
            model["validation_errors"] = validation_errors

            logger.info(
                f"Generated ArchiMate model with {len(model['elements'])} elements and "
                f"{len(model['relationships'])} relationships; "
                f"{len(validation_errors)} validation error(s)"
            )
            return model

        except Exception as e:
            logger.error(f"Error generating ArchiMate model: {e}")
            return {"error": str(e)}

    def _initialize_model(self, capability: UnifiedCapability) -> Dict[str, Any]:
        """Initialize the basic model structure."""
        return {
            "id": str(uuid.uuid4()),
            "name": f"Architecture Model - {capability.name}",
            "description": f"ArchiMate 3.2 model generated for capability: {capability.name}",
            "version": "1.0",
            "elements": [],
            "relationships": [],
            "viewpoints": [],
            "properties": {
                "capability_id": capability.id,
                "capability_name": capability.name,
                "domain": capability.domain.name if capability.domain else "Unknown",
            },
        }

    def _generate_business_layer(
        self, capability: UnifiedCapability, gap_analysis: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate Business Layer elements and relationships."""
        elements = []
        relationships = []

        # Business Capability
        capability_element = {
            "id": f"business_capability_{capability.id}",
            "name": capability.name,
            "type": "BusinessCapability",
            "layer": "business",
            "description": capability.description or f"Business capability: {capability.name}",
            "properties": {
                "level": capability.level,
                "strategic_importance": capability.strategic_importance,
                "business_criticality": capability.business_criticality,
            },
        }
        elements.append(capability_element)

        # Business Services (derived from capability)
        service_element = {
            "id": f"business_service_{capability.id}",
            "name": f"{capability.name} Service",
            "type": "BusinessService",
            "layer": "business",
            "description": f"Business service supporting {capability.name}",
            "properties": {},
        }
        elements.append(service_element)

        # Realization relationship
        relationships.append(
            {
                "id": f"rel_realization_{service_element['id']}_{capability_element['id']}",
                "type": "Realization",
                "source": service_element["id"],
                "target": capability_element["id"],
                "properties": {},
            }
        )

        # Business Processes (if gap analysis provides them)
        gap_details = gap_analysis.get("gap_analysis", {})
        if "recommended_solutions" in gap_details:
            for i, solution in enumerate(gap_details["recommended_solutions"][:3]):  # Limit to 3
                process_element = {
                    "id": f"business_process_{capability.id}_{i}",
                    "name": f"Implement {solution.get('name', f'Solution {i + 1}')}",
                    "type": "BusinessProcess",
                    "layer": "business",
                    "description": f"Business process to implement solution for {capability.name}",
                    "properties": {},
                }
                elements.append(process_element)

                # Assignment relationship to service
                relationships.append(
                    {
                        "id": f"rel_assignment_{process_element['id']}_{service_element['id']}",
                        "type": "Assignment",
                        "source": process_element["id"],
                        "target": service_element["id"],
                        "properties": {},
                    }
                )

        return elements, relationships

    def _generate_application_layer(
        self, capability: UnifiedCapability, solution_options: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate Application Layer elements and relationships."""
        elements = []
        relationships = []

        for i, option in enumerate(solution_options[:3]):  # Limit to top 3 options
            # Application Component
            component_element = {
                "id": f"app_component_{capability.id}_{i}",
                "name": option.get("name", f"Application Component {i + 1}"),
                "type": "ApplicationComponent",
                "layer": "application",
                "description": option.get(
                    "description", f"Application component for {capability.name}"
                ),
                "properties": {
                    "vendor_name": option.get("vendor_name", "Unknown"),
                    "cost_estimate": option.get("cost_estimate"),
                    "capability_coverage": option.get("capability_coverage", 0),
                },
            }
            elements.append(component_element)

            # Application Service
            service_element = {
                "id": f"app_service_{capability.id}_{i}",
                "name": f"{component_element['name']} Service",
                "type": "ApplicationService",
                "layer": "application",
                "description": f"Application service provided by {component_element['name']}",
                "properties": {},
            }
            elements.append(service_element)

            # Realization relationship
            relationships.append(
                {
                    "id": f"rel_realization_{service_element['id']}_{component_element['id']}",
                    "type": "Realization",
                    "source": service_element["id"],
                    "target": component_element["id"],
                    "properties": {},
                }
            )

            # Connect to Business Layer
            business_service_id = f"business_service_{capability.id}"
            relationships.append(
                {
                    "id": f"rel_serving_{service_element['id']}_{business_service_id}",
                    "type": "Serving",
                    "source": service_element["id"],
                    "target": business_service_id,
                    "properties": {},
                }
            )

        return elements, relationships

    def _generate_technology_layer(
        self, solution_options: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate Technology Layer elements and relationships."""
        elements = []
        relationships = []

        # Group by technology type
        tech_types = {}
        for option in solution_options:
            tech_type = option.get("technology_type", "Software")
            if tech_type not in tech_types:
                tech_types[tech_type] = []
            tech_types[tech_type].append(option)

        for tech_type, options in tech_types.items():
            # Technology Service
            service_element = {
                "id": f"tech_service_{tech_type.lower().replace(' ', '_')}",
                "name": f"{tech_type} Technology Service",
                "type": "TechnologyService",
                "layer": "technology",
                "description": f"Technology service for {tech_type} solutions",
                "properties": {"technology_type": tech_type},
            }
            elements.append(service_element)

            # System Software (for each deployment model)
            deployment_models = set()
            for option in options:
                deployment = option.get("deployment_model", "Cloud")
                if deployment not in deployment_models:
                    deployment_models.add(deployment)

                    software_element = {
                        "id": f"system_software_{tech_type.lower().replace(' ', '_')}_{deployment.lower().replace(' ', '_')}",
                        "name": f"{tech_type} System Software ({deployment})",
                        "type": "SystemSoftware",
                        "layer": "technology",
                        "description": f"System software for {tech_type} solutions deployed on {deployment}",
                        "properties": {
                            "deployment_model": deployment,
                            "technology_type": tech_type,
                        },
                    }
                    elements.append(software_element)

                    # Composition relationship between service and software
                    relationships.append(
                        {
                            "id": f"rel_composition_{service_element['id']}_{software_element['id']}",
                            "type": "Composition",
                            "source": service_element["id"],
                            "target": software_element["id"],
                            "properties": {},
                        }
                    )

            # Note: Cross-layer relationships are created in the main generation method
            # when all layers are available

        return elements, relationships

    def _generate_motivation_layer(
        self, capability: UnifiedCapability, gap_analysis: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate Motivation Layer elements and relationships."""
        elements = []
        relationships = []

        # Driver (from gap analysis challenges)
        drivers = gap_analysis.get("risks", []) + gap_analysis.get("dependencies", [])

        # Goal (defined first for relationships)
        goal_element = {
            "id": f"goal_{capability.id}",
            "name": f"Improve {capability.name} Capability",
            "type": "Goal",
            "layer": "motivation",
            "description": f"Strategic goal to enhance {capability.name} capability",
            "properties": {"priority": "high", "timeframe": "12 months"},
        }
        elements.append(goal_element)

        for i, driver_text in enumerate(drivers[:3]):  # Limit to 3 drivers
            driver_element = {
                "id": f"driver_{capability.id}_{i}",
                "name": f"Driver: {driver_text[:50]}",
                "type": "Driver",
                "layer": "motivation",
                "description": f"Strategic driver influencing {capability.name}: {driver_text}",
                "properties": {
                    "driver_type": "risk"
                    if driver_text in gap_analysis.get("risks", [])
                    else "dependency"
                },
            }
            elements.append(driver_element)

            # Influence relationship to goal
            relationships.append(
                {
                    "id": f"rel_influence_{driver_element['id']}_{goal_element['id']}",
                    "type": "Influence",
                    "source": driver_element["id"],
                    "target": goal_element["id"],
                    "properties": {},
                }
            )

        # Remove duplicate goal definition
        # Goal
        # goal_element = {
        #     "id": f"goal_{capability.id}",
        #     "name": f"Improve {capability.name} Capability",
        #     "type": "Goal",
        #     "layer": "motivation",
        #     "description": f"Strategic goal to enhance {capability.name} capability",
        #     "properties": {
        #         "priority": "high",
        #         "timeframe": "12 months"
        #     }
        # }
        # elements.append(goal_element)

        # Requirements (derived from gap analysis)
        gap_details = gap_analysis.get("gap_analysis", {})
        current_coverage = gap_details.get("current_coverage", 0)
        target_coverage = gap_details.get("target_coverage", 100)

        if current_coverage < target_coverage:
            requirement_element = {
                "id": f"requirement_{capability.id}",
                "name": f"Achieve {target_coverage}% coverage for {capability.name}",
                "type": "Requirement",
                "layer": "motivation",
                "description": f"Requirement to close capability gap from {current_coverage}% to {target_coverage}%",
                "properties": {
                    "current_coverage": current_coverage,
                    "target_coverage": target_coverage,
                    "gap": target_coverage - current_coverage,
                },
            }
            elements.append(requirement_element)

            # Influence relationship
            relationships.append(
                {
                    "id": f"rel_influence_{requirement_element['id']}_{goal_element['id']}",
                    "type": "Influence",
                    "source": requirement_element["id"],
                    "target": goal_element["id"],
                    "properties": {"influence_strength": "+"},
                }
            )

        return elements, relationships

    def _generate_strategy_layer(
        self, capability: UnifiedCapability, solution_options: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Generate Strategy Layer elements and relationships."""
        elements = []
        relationships = []

        # Strategic Capability (reuse business capability)
        strategy_capability = {
            "id": f"strategy_capability_{capability.id}",
            "name": f"{capability.name} ({capability.strategic_importance.title()} Priority)",
            "type": "Capability",
            "layer": "strategy",
            "description": f"Strategic capability: {capability.name} - {capability.strategic_importance} strategic importance",
            "properties": {
                "level": capability.level,
                "domain": capability.domain.name if capability.domain else "Unknown",
                "strategic_importance": capability.strategic_importance,
            },
        }
        elements.append(strategy_capability)

        # Course of Action (implementation strategy)
        for i, option in enumerate(solution_options[:2]):  # Limit to 2
            action_element = {
                "id": f"course_of_action_{capability.id}_{i}",
                "name": f"Implement {option.get('name', f'Solution {i + 1}')} Strategy",
                "type": "CourseOfAction",
                "layer": "strategy",
                "description": f"Strategic course of action to implement {option.get('name', f'Solution {i + 1}')}",
                "properties": {
                    "implementation_approach": option.get("deployment_model", "Cloud"),
                    "estimated_timeline": f"{option.get('implementation_time', 6)} months",
                    "vendor": option.get("vendor_name", "Unknown"),
                },
            }
            elements.append(action_element)

            # Realization relationship to strategic capability
            relationships.append(
                {
                    "id": f"rel_realization_{action_element['id']}_{strategy_capability['id']}",
                    "type": "Realization",
                    "source": action_element["id"],
                    "target": strategy_capability["id"],
                    "properties": {},
                }
            )

        # Resources (from solution options)
        for i, option in enumerate(solution_options[:2]):  # Limit to 2
            resource_element = {
                "id": f"resource_{capability.id}_{i}",
                "name": f"Resource: {option.get('name', f'Option {i + 1}')}",
                "type": "Resource",
                "layer": "strategy",
                "description": f"Strategic resource for implementing {option.get('name', f'Option {i + 1}')}",
                "properties": {
                    "cost": option.get("cost_estimate"),
                    "capability_coverage": option.get("capability_coverage", 0),
                },
            }
            elements.append(resource_element)

            # Assignment relationship to course of action
            action_id = f"course_of_action_{capability.id}_{i}"
            relationships.append(
                {
                    "id": f"rel_assignment_{resource_element['id']}_{action_id}",
                    "type": "Assignment",
                    "source": resource_element["id"],
                    "target": action_id,
                    "properties": {},
                }
            )

        return elements, relationships

    def _generate_viewpoints(self, model: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate relevant viewpoints for the model."""
        viewpoints = []

        # Application Cooperation Viewpoint
        app_elements = [e for e in model["elements"] if e["layer"] == "application"]
        if app_elements:
            viewpoints.append(
                {
                    "id": f"viewpoint_app_cooperation_{model['id'][:8]}",
                    "name": "Application Cooperation Viewpoint",
                    "type": "application_cooperation",
                    "description": "Shows relationships between application components",
                    "elements": [e["id"] for e in app_elements],
                    "relationships": [
                        r["id"]
                        for r in model["relationships"]
                        if r["source"] in [e["id"] for e in app_elements]
                        or r["target"] in [e["id"] for e in app_elements]
                    ],
                }
            )

        # Business Function Viewpoint
        business_elements = [e for e in model["elements"] if e["layer"] == "business"]
        if business_elements:
            viewpoints.append(
                {
                    "id": f"viewpoint_business_function_{model['id'][:8]}",
                    "name": "Business Function Viewpoint",
                    "type": "business_function",
                    "description": "Shows main business functions and relationships",
                    "elements": [e["id"] for e in business_elements],
                    "relationships": [
                        r["id"]
                        for r in model["relationships"]
                        if r["source"] in [e["id"] for e in business_elements]
                        or r["target"] in [e["id"] for e in business_elements]
                    ],
                }
            )

        # Technology Usage Viewpoint
        tech_elements = [e for e in model["elements"] if e["layer"] == "technology"]
        if tech_elements:
            viewpoints.append(
                {
                    "id": f"viewpoint_technology_usage_{model['id'][:8]}",
                    "name": "Technology Usage Viewpoint",
                    "type": "technology_usage",
                    "description": "Shows how technology is used by applications",
                    "elements": [e["id"] for e in tech_elements],
                    "relationships": [
                        r["id"]
                        for r in model["relationships"]
                        if r["source"] in [e["id"] for e in tech_elements]
                        or r["target"] in [e["id"] for e in tech_elements]
                    ],
                }
            )

        return viewpoints

    def export_to_archimate_exchange(self, model: Dict[str, Any]) -> str:
        """
        Export model to ArchiMate 3.2 Exchange Format XML.

        Args:
            model: ArchiMate model dictionary

        Returns:
            XML string in ArchiMate Exchange Format
        """
        # This is a simplified implementation - in production, you'd use a proper XML library
        xml_parts = [
            '<?xml version="1.0" encoding="UTF - 8"?>',
            '<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '        xsi:schemaLocation="http://www.opengroup.org/xsd/archimate/3.0/ http://www.opengroup.org/xsd/archimate/3.0/archimate3_Model.xsd"',
            f'        identifier="{model["id"]}" version="{model["version"]}">',
            f'  <name xml:lang="en">{model["name"]}</name>',
            f'  <documentation xml:lang="en">{model["description"]}</documentation>',
        ]

        # Add elements
        for element in model["elements"]:
            xml_parts.append(
                f'  <elements identifier="{element["id"]}" xsi:type="{element["type"]}ElementType">'
            )
            xml_parts.append(f'    <name xml:lang="en">{element["name"]}</name>')
            if element.get("description"):
                xml_parts.append(
                    f'    <documentation xml:lang="en">{element["description"]}</documentation>'
                )
            xml_parts.append("  </elements>")

        # Add relationships
        for relationship in model["relationships"]:
            xml_parts.append(
                f'  <relationships identifier="{relationship["id"]}" xsi:type="{relationship["type"]}RelationshipType"'
            )
            xml_parts.append(
                f'                   source="{relationship["source"]}" target="{relationship["target"]}">'
            )
            xml_parts.append("  </relationships>")

        xml_parts.append("</model>")

        return "\n".join(xml_parts)
