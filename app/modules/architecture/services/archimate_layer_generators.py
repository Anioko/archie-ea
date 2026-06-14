"""
-> app.modules.architecture.services.layer_service

ArchiMate Layer-Specific Generators
Multi-stage generation for comprehensive enterprise architecture
Supports three modes: quick (50 - 100), standard (100 - 200), comprehensive (200 - 300)
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.models.application_portfolio import ApplicationComponent
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# Generation mode configurations
GENERATION_MODES = {
    "quick": {
        "motivation": "10 - 15",
        "strategy": "5 - 8",
        "business": "15 - 20",
        "application": "10 - 15",
        "technology": "8 - 12",
        "physical": "3 - 5",
        "implementation": "5 - 8",
        "total_target": "50 - 100",
    },
    "standard": {
        "motivation": "15 - 25",
        "strategy": "10 - 15",
        "business": "25 - 40",
        "application": "20 - 30",
        "technology": "15 - 25",
        "physical": "5 - 10",
        "implementation": "10 - 15",
        "total_target": "100 - 200",
    },
    "comprehensive": {
        "motivation": "25 - 35",
        "strategy": "15 - 25",
        "business": "40 - 60",
        "application": "30 - 45",
        "technology": "25 - 35",
        "physical": "10 - 15",
        "implementation": "15 - 25",
        "total_target": "200 - 300",
    },
}


class ArchiMateLayerGenerators:
    """Layer-specific generators for comprehensive ArchiMate 3.2 architecture."""

    def __init__(self, llm_service=None, mode: str = "standard", layer_overrides=None):
        # LLMService is static, no need to store instance
        self.mode = mode if mode in GENERATION_MODES else "standard"
        self.config = dict(GENERATION_MODES[self.mode])  # copy so overrides don't mutate
        if layer_overrides:
            for layer, target in layer_overrides.items():
                if layer in self.config:
                    self.config[layer] = str(target)

    def is_layer_enabled(self, layer):
        """Check if a layer has a non-zero target (avoids wasted LLM calls)."""
        val = self.config.get(layer, "0")
        if isinstance(val, (int, float)):
            return val > 0
        # Range string like "15 - 25" or override "0"
        try:
            return int(val.strip().split("-")[0].strip()) > 0
        except (ValueError, AttributeError):
            return True

    def build_comprehensive_app_context(self, app: ApplicationComponent, context: str) -> str:
        """Build rich context for ArchiMate generation."""
        hosting_type = getattr(app, 'hosting_type', None) or 'Not specified'  # model-safety-ok: optional field (not on ApplicationComponent schema)
        number_of_users = getattr(app, 'number_of_users', None) or 'Not specified'  # model-safety-ok: optional field (not on ApplicationComponent schema)
        return f"""
APPLICATION NAME: {app.name}
DESCRIPTION: {app.description or 'No description available'}
BUSINESS FUNCTIONS: {app.application_functions_text or 'No functions specified'}
BUSINESS DOMAIN: {app.business_domain or 'Not specified'}
BUSINESS CRITICALITY: {app.business_criticality or 'Not specified'}
TECHNOLOGY STACK: {app.technology_stack or 'Not specified'}
HOSTING: {hosting_type}
VENDOR: {app.vendor_name or 'Not specified'}
LIFECYCLE STATUS: {app.lifecycle_status or 'Not specified'}
USERS: {number_of_users}
ADDITIONAL CONTEXT: {context}
""".strip()

    def generate_motivation_layer(
        self, app: ApplicationComponent, app_context: str
    ) -> List[Dict[str, Any]]:
        """Generate Motivation layer: Stakeholders, Drivers, Goals, Requirements."""
        try:
            target = self.config["motivation"]
            prompt = f"""
Generate ArchiMate 3.2 Motivation layer elements for this application.

{app_context}

Generate these elements (target: {target} total):
1. Stakeholders (e.g., Business Users, IT Operations, Management, External Partners, Customers)
2. Drivers (business/technical pressures motivating this application)
3. Goals (strategic objectives this application supports)
4. Requirements (key functional/non-functional requirements)

Return ONLY valid JSON:
{{
  "elements": [
    {{"name": "...", "type": "Stakeholder|Driver|Goal|Requirement", "layer": "motivation", "description": "..."}}
  ]
}}

CRITICAL: Generate {target} elements total. Be comprehensive and specific to the application context.
"""

            response = LLMService.generate_from_prompt(prompt)
            elements = self._parse_elements_response(response, "motivation")
            logger.info(f"Generated {len(elements)} motivation layer elements for {app.name}")
            return elements

        except Exception as e:
            logger.error(f"Motivation layer generation failed for {getattr(app, 'name', 'unknown')}: {e}")
            return []

    def generate_strategy_layer(
        self, app: ApplicationComponent, app_context: str, motivation_elements: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate Strategy layer: Capabilities, Value Streams, Courses of Action."""
        try:
            target = self.config["strategy"]
            # Extract goals from motivation layer for traceability
            goals = [e["name"] for e in motivation_elements if e.get("type") == "Goal"]
            goals_text = ", ".join(goals[:5]) if goals else "business goals"

            prompt = f"""
Generate ArchiMate 3.2 Strategy layer elements for this application.

{app_context}

This application supports these goals: {goals_text}

Generate these elements (target: {target} total):
1. Capabilities (business/technical capabilities this application provides)
2. Value Streams (end-to-end value delivery processes)
3. Courses of Action (strategic initiatives or approaches)

Return ONLY valid JSON:
{{
  "elements": [
    {{"name": "...", "type": "Capability|ValueStream|CourseOfAction", "layer": "strategy", "description": "..."}}
  ]
}}

CRITICAL: Generate {target} elements total. Link comprehensively to the application's strategic purpose.
"""

            response = LLMService.generate_from_prompt(prompt)
            elements = self._parse_elements_response(response, "strategy")
            logger.info(f"Generated {len(elements)} strategy layer elements")
            return elements

        except Exception as e:
            logger.error(f"Strategy layer generation failed: {e}")
            return []

    def generate_business_layer(
        self, app: ApplicationComponent, app_context: str, strategy_elements: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate Business layer: Actors, Processes, Services, Objects."""
        try:
            target = self.config["business"]
            # Extract capabilities for context
            capabilities = [e["name"] for e in strategy_elements if e.get("type") == "Capability"]
            cap_text = ", ".join(capabilities[:4]) if capabilities else "business capabilities"

            prompt = f"""
Generate ArchiMate 3.2 Business layer elements for this application.

{app_context}

This application supports: {cap_text}

Generate these elements (target: {target} total):
1. Business Actors/Roles (who uses this application, including internal and external users)
2. Business Processes (key processes this application supports, including sub-processes)
3. Business Services (services provided to users)
4. Business Objects (key business data entities)

Return ONLY valid JSON:
{{
  "elements": [
    {{"name": "...", "type": "BusinessActor|BusinessRole|BusinessProcess|BusinessService|BusinessObject", "layer": "business", "description": "..."}}
  ]
}}

CRITICAL: Generate {target} elements total. Be comprehensive and specific to all application functions.
"""

            response = LLMService.generate_from_prompt(prompt)
            elements = self._parse_elements_response(response, "business")
            logger.info(f"Generated {len(elements)} business layer elements")
            return elements

        except Exception as e:
            logger.error(f"Business layer generation failed: {e}")
            return []

    def generate_application_layer(
        self, app: ApplicationComponent, app_context: str, business_elements: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate Application layer: Components, Services, Interfaces, Data."""
        try:
            target = self.config["application"]
            # Extract business services for context
            services = [e["name"] for e in business_elements if e.get("type") == "BusinessService"]
            svc_text = ", ".join(services[:5]) if services else "business services"

            prompt = f"""
Generate ArchiMate 3.2 Application layer elements for this application.

{app_context}

This application automates: {svc_text}

Generate these elements (target: {target} total):
1. Application Components (software modules/systems, including microservices and sub-components)
2. Application Services (services exposed by components)
3. Application Interfaces (APIs, UIs, integration points, messaging interfaces)
4. Data Objects (key data entities managed by application)

Return ONLY valid JSON:
{{
  "elements": [
    {{"name": "...", "type": "ApplicationComponent|ApplicationService|ApplicationInterface|DataObject", "layer": "application", "description": "..."}}
  ]
}}

CRITICAL: Generate {target} elements total. Include the main application as ApplicationComponent and be comprehensive.
"""

            response = LLMService.generate_from_prompt(prompt)
            elements = self._parse_elements_response(response, "application")
            logger.info(f"Generated {len(elements)} application layer elements")
            return elements

        except Exception as e:
            logger.error(f"Application layer generation failed: {e}")
            return []

    def generate_technology_layer(
        self, app: ApplicationComponent, app_context: str, application_elements: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Generate Technology layer: Nodes, Devices, Software, Networks."""
        try:
            target = self.config["technology"]
            tech_stack = (
                app.technology_stack or "standard enterprise technology stack"
            )
            hosting = getattr(app, "hosting_type", None) or "on-premise or cloud"  # model-safety-ok: optional field (not on ApplicationComponent schema)

            prompt = f"""
Generate ArchiMate 3.2 Technology layer elements for this application.

{app_context}

Technology Stack: {tech_stack}
Hosting: {hosting}

Generate these elements (target: {target} total):
1. Nodes (servers, VMs, containers, load balancers, caching layers)
2. Devices (end-user devices, hardware, IoT devices)
3. System Software (OS, middleware, databases, monitoring tools, security software)
4. Networks (network infrastructure, communication paths, VPNs, CDNs)

Return ONLY valid JSON:
{{
  "elements": [
    {{"name": "...", "type": "Node|Device|SystemSoftware|CommunicationNetwork", "layer": "technology", "description": "..."}}
  ]
}}

CRITICAL: Generate {target} elements total. Be comprehensive and match to actual technology stack if specified.
"""

            response = LLMService.generate_from_prompt(prompt)
            elements = self._parse_elements_response(response, "technology")
            logger.info(f"Generated {len(elements)} technology layer elements")
            return elements

        except Exception as e:
            logger.error(f"Technology layer generation failed: {e}")
            return []

    def generate_physical_layer(
        self, app: ApplicationComponent, app_context: str
    ) -> List[Dict[str, Any]]:
        """Generate Physical layer: Equipment, Facilities (if applicable)."""
        try:
            target = self.config["physical"]
            # Physical layer is optional - only generate if relevant (on-premise, manufacturing, etc.)
            hosting = (getattr(app, "hosting_type", None) or "").lower()  # model-safety-ok: optional field (not on ApplicationComponent schema)

            # Skip physical layer for pure cloud/SaaS applications
            if "cloud" in hosting or "saas" in hosting or "azure" in hosting or "aws" in hosting:
                return []

            prompt = f"""
Generate ArchiMate 3.2 Physical layer elements for this application (if applicable).

{app_context}

Generate {target} elements if this application has physical infrastructure:
1. Equipment (physical hardware, servers, network equipment, storage devices)
2. Facilities (data centers, offices, locations, server rooms)
3. Distribution Networks (physical distribution channels, network cabling)

Return ONLY valid JSON:
{{
  "elements": [
    {{"name": "...", "type": "Equipment|Facility|DistributionNetwork", "layer": "physical", "description": "..."}}
  ]
}}

If no physical infrastructure is relevant, return empty array: {{"elements": []}}
"""

            response = LLMService.generate_from_prompt(prompt)
            elements = self._parse_elements_response(response, "physical")
            logger.info(f"Generated {len(elements)} physical layer elements")
            return elements

        except Exception as e:
            logger.error(f"Physical layer generation failed: {e}")
            return []

    def generate_implementation_layer(
        self, app: ApplicationComponent, app_context: str
    ) -> List[Dict[str, Any]]:
        """Generate Implementation layer: Work Packages, Plateaus, Gaps."""
        try:
            target = self.config["implementation"]
            lifecycle = app.lifecycle_status or "Active"

            prompt = f"""
Generate ArchiMate 3.2 Implementation & Migration layer elements for this application.

{app_context}

Current Lifecycle Status: {lifecycle}

Generate these elements (target: {target} total):
1. Work Packages (implementation projects, initiatives, migration phases)
2. Plateaus (architecture states - baseline, current, intermediate, target)
3. Gaps (differences between current and target state, capability gaps)

Return ONLY valid JSON:
{{
  "elements": [
    {{"name": "...", "type": "WorkPackage|Plateau|Gap", "layer": "implementation", "description": "..."}}
  ]
}}

CRITICAL: Generate {target} elements total. Be comprehensive about implementation roadmap and migration strategy.
"""

            response = LLMService.generate_from_prompt(prompt)
            elements = self._parse_elements_response(response, "implementation")
            logger.info(f"Generated {len(elements)} implementation layer elements")
            return elements

        except Exception as e:
            logger.error(f"Implementation layer generation failed: {e}")
            return []

    def _parse_elements_response(self, response: str, expected_layer: str) -> List[Dict[str, Any]]:
        """Parse LLM response and extract elements."""
        try:
            # Clean response
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Extract JSON
            if "{" in cleaned:
                start_idx = cleaned.find("{")
                end_idx = cleaned.rfind("}") + 1
                if start_idx != -1 and end_idx > start_idx:
                    cleaned = cleaned[start_idx:end_idx]

            # Parse JSON
            result = json.loads(cleaned)
            elements = result.get("elements", [])

            # Validate and normalize
            validated = []
            for elem in elements:
                if "name" in elem and "type" in elem:
                    # Ensure layer is set correctly
                    if "layer" not in elem or not elem["layer"]:
                        elem["layer"] = expected_layer
                    validated.append(elem)

            return validated

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {expected_layer} layer response: {e}")
            logger.debug(f"Response was: {response[:500]}...")
            return []
        except Exception as e:
            logger.error(f"Error processing {expected_layer} layer response: {e}")
            return []
