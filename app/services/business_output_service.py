"""
Business Output Service - Stakeholder-Specific AI Response Transformation

Transforms AI chat outputs into business-friendly insights tailored for
specific enterprise architecture roles and personas.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class StakeholderRole(Enum):
    """Enterprise architecture stakeholder roles for output transformation"""

    # Architect roles
    ENTERPRISE_ARCHITECT = "enterprise_architect"
    SOLUTIONS_ARCHITECT = "solutions_architect"
    APPLICATION_ARCHITECT = "application_architect"
    INTEGRATION_ARCHITECT = "integration_architect"
    SYSTEMS_ARCHITECT = "systems_architect"
    BUSINESS_ARCHITECT = "business_architect"

    # Analyst roles
    BUSINESS_ANALYST = "business_analyst"
    PRODUCT_ANALYST = "product_analyst"

    # Executive roles
    CIO = "cio"
    EXECUTIVE = "executive"

    # Technical roles
    DEVELOPER = "developer"
    PROJECT_MANAGER = "project_manager"
    VENDOR_MANAGER = "vendor_manager"


# Role configurations with transformation rules
ROLE_CONFIGS = {
    StakeholderRole.ENTERPRISE_ARCHITECT: {
        "name": "Enterprise Architect",
        "description": "Strategic enterprise-wide architecture guidance",
        "icon": "building - 2",
        "color": "purple",
        "focus_areas": ["strategic_alignment", "portfolio_health", "governance", "roadmaps"],
        "output_format": "strategic_analysis",
        "emphasis": ["TOGAF alignment", "enterprise patterns", "strategic recommendations"],
        "include_sections": [
            "executive_summary",
            "strategic_implications",
            "governance_notes",
            "next_steps",
        ],
        "terminology_level": "enterprise",
    },
    StakeholderRole.SOLUTIONS_ARCHITECT: {
        "name": "Solutions Architect",
        "description": "Solution design and integration patterns",
        "icon": "puzzle",
        "color": "blue",
        "focus_areas": [
            "solution_design",
            "integration_patterns",
            "nfr_analysis",
            "vendor_evaluation",
        ],
        "output_format": "solution_specification",
        "emphasis": ["design patterns", "integration complexity", "scalability"],
        "include_sections": [
            "solution_overview",
            "integration_points",
            "nfr_considerations",
            "recommendations",
        ],
        "terminology_level": "technical",
    },
    StakeholderRole.APPLICATION_ARCHITECT: {
        "name": "Application Architect",
        "description": "Application design and modernization",
        "icon": "app-window",
        "color": "green",
        "focus_areas": ["application_design", "modernization", "api_design", "technical_debt"],
        "output_format": "application_analysis",
        "emphasis": ["application health", "modernization paths", "dependencies"],
        "include_sections": [
            "application_overview",
            "health_assessment",
            "modernization_options",
            "action_items",
        ],
        "terminology_level": "technical",
    },
    StakeholderRole.INTEGRATION_ARCHITECT: {
        "name": "Integration Architect",
        "description": "Integration patterns and data flows",
        "icon": "git-merge",
        "color": "orange",
        "focus_areas": ["interfaces", "data_flows", "integration_patterns", "event_management"],
        "output_format": "integration_specification",
        "emphasis": ["data flows", "interface catalog", "event patterns"],
        "include_sections": [
            "integration_overview",
            "data_flows",
            "interface_mapping",
            "pattern_recommendations",
        ],
        "terminology_level": "technical",
    },
    StakeholderRole.SYSTEMS_ARCHITECT: {
        "name": "Systems Architect",
        "description": "Infrastructure and system design",
        "icon": "server",
        "color": "slate",
        "focus_areas": ["infrastructure", "security", "disaster_recovery", "performance"],
        "output_format": "infrastructure_analysis",
        "emphasis": ["infrastructure landscape", "security patterns", "DR/BC considerations"],
        "include_sections": [
            "infrastructure_overview",
            "security_assessment",
            "availability_analysis",
            "recommendations",
        ],
        "terminology_level": "infrastructure",
    },
    StakeholderRole.BUSINESS_ARCHITECT: {
        "name": "Business Architect",
        "description": "Business capability and value stream analysis",
        "icon": "briefcase",
        "color": "amber",
        "focus_areas": ["capabilities", "value_streams", "business_processes", "operating_models"],
        "output_format": "business_analysis",
        "emphasis": ["capability maturity", "value streams", "business alignment"],
        "include_sections": [
            "capability_overview",
            "value_stream_mapping",
            "maturity_assessment",
            "recommendations",
        ],
        "terminology_level": "business",
    },
    StakeholderRole.BUSINESS_ANALYST: {
        "name": "Business Analyst",
        "description": "Requirements and process analysis",
        "icon": "clipboard-list",
        "color": "cyan",
        "focus_areas": ["requirements", "processes", "stakeholders", "use_cases"],
        "output_format": "requirements_analysis",
        "emphasis": ["requirements tracing", "process-capability mapping", "stakeholder impact"],
        "include_sections": [
            "requirements_summary",
            "process_impact",
            "stakeholder_analysis",
            "user_stories",
        ],
        "terminology_level": "business",
    },
    StakeholderRole.PRODUCT_ANALYST: {
        "name": "Product Analyst",
        "description": "Product-capability alignment and roadmaps",
        "icon": "package",
        "color": "pink",
        "focus_areas": ["features", "customer_journeys", "product_roadmap", "market_fit"],
        "output_format": "product_analysis",
        "emphasis": [
            "feature-capability mapping",
            "customer journeys",
            "competitive differentiation",
        ],
        "include_sections": [
            "product_overview",
            "capability_alignment",
            "journey_mapping",
            "roadmap_recommendations",
        ],
        "terminology_level": "product",
    },
    StakeholderRole.CIO: {
        "name": "CIO / IT Executive",
        "description": "Strategic IT leadership and portfolio oversight",
        "icon": "crown",
        "color": "violet",
        "focus_areas": ["portfolio_health", "investments", "risks", "compliance"],
        "output_format": "executive_briefing",
        "emphasis": ["business value", "ROI", "risk landscape", "strategic alignment"],
        "include_sections": [
            "executive_summary",
            "key_metrics",
            "risk_highlights",
            "investment_recommendations",
        ],
        "terminology_level": "executive",
    },
    StakeholderRole.EXECUTIVE: {
        "name": "Executive",
        "description": "Business executive perspective",
        "icon": "briefcase",
        "color": "indigo",
        "focus_areas": ["business_value", "roi", "strategic_outcomes", "risks"],
        "output_format": "executive_summary",
        "emphasis": ["business impact", "ROI", "strategic value"],
        "include_sections": [
            "executive_summary",
            "business_impact",
            "investment_overview",
            "recommendations",
        ],
        "terminology_level": "executive",
    },
    StakeholderRole.DEVELOPER: {
        "name": "Developer",
        "description": "Technical implementation focus",
        "icon": "code",
        "color": "green",
        "focus_areas": ["implementation", "code", "apis", "testing"],
        "output_format": "technical_specification",
        "emphasis": ["implementation details", "code examples", "API contracts"],
        "include_sections": [
            "technical_overview",
            "implementation_guide",
            "api_details",
            "testing_notes",
        ],
        "terminology_level": "developer",
    },
    StakeholderRole.PROJECT_MANAGER: {
        "name": "Project Manager",
        "description": "Project coordination and delivery",
        "icon": "gantt-chart",
        "color": "blue",
        "focus_areas": ["timeline", "resources", "dependencies", "risks"],
        "output_format": "project_summary",
        "emphasis": ["deliverables", "dependencies", "resource requirements"],
        "include_sections": ["project_overview", "deliverables", "dependencies", "risk_register"],
        "terminology_level": "project",
    },
    StakeholderRole.VENDOR_MANAGER: {
        "name": "Vendor Manager",
        "description": "Vendor relationships and procurement",
        "icon": "handshake",
        "color": "teal",
        "focus_areas": ["vendors", "contracts", "procurement", "relationships"],
        "output_format": "vendor_analysis",
        "emphasis": ["vendor evaluation", "contract considerations", "procurement strategy"],
        "include_sections": [
            "vendor_overview",
            "evaluation_criteria",
            "contract_notes",
            "recommendations",
        ],
        "terminology_level": "procurement",
    },
}


class BusinessOutputService:
    """
    Service for transforming AI chat outputs into stakeholder-specific formats.

    Provides role-based transformation of technical AI responses into
    business-friendly insights tailored for different enterprise personas.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_available_roles(self) -> List[Dict[str, Any]]:
        """
        Get list of available stakeholder roles with their configurations.

        Returns:
            List of role configurations with metadata
        """
        roles = []
        for role, config in ROLE_CONFIGS.items():
            roles.append(
                {
                    "value": role.value,
                    "name": config["name"],
                    "description": config["description"],
                    "icon": config["icon"],
                    "color": config["color"],
                    "focus_areas": config["focus_areas"],
                    "output_format": config["output_format"],
                }
            )
        return roles

    def get_role_config(self, role: StakeholderRole) -> Dict[str, Any]:
        """
        Get configuration for a specific role.

        Args:
            role: The stakeholder role

        Returns:
            Role configuration dictionary
        """
        return ROLE_CONFIGS.get(role, {})

    def transform_for_stakeholder(
        self, ai_response: Dict[str, Any], role: StakeholderRole
    ) -> Dict[str, Any]:
        """
        Transform AI response for a specific stakeholder role.

        Args:
            ai_response: Original AI response with 'response', 'domain', 'metadata'
            role: Target stakeholder role

        Returns:
            Transformed response tailored for the stakeholder
        """
        config = ROLE_CONFIGS.get(role)
        if not config:
            return ai_response

        original_response = ai_response.get("response", "")
        domain = ai_response.get("domain", "general")
        metadata = ai_response.get("metadata", {})

        # Build transformed output
        transformed = {
            "original_response": original_response,
            "role": role.value,
            "role_name": config["name"],
            "format": config["output_format"],
            "sections": {},
            "emphasis_points": [],
            "terminology_adjustments": [],
            "metadata": {
                **metadata,
                "transformed_for": role.value,
                "transformation_format": config["output_format"],
            },
        }

        # Generate sections based on role configuration
        for section in config.get("include_sections", []):
            transformed["sections"][section] = self._generate_section(
                section, original_response, role, domain
            )

        # Add emphasis points
        transformed["emphasis_points"] = self._extract_emphasis_points(
            original_response, config.get("emphasis", [])
        )

        # Generate formatted output
        transformed["formatted_response"] = self._format_response(original_response, role, config)

        return transformed

    def _generate_section(
        self, section: str, response: str, role: StakeholderRole, domain: str
    ) -> Dict[str, Any]:
        """Generate content for a specific section based on role."""
        section_generators = {
            "executive_summary": self._generate_executive_summary,
            "strategic_implications": self._generate_strategic_implications,
            "governance_notes": self._generate_governance_notes,
            "next_steps": self._generate_next_steps,
            "solution_overview": self._generate_solution_overview,
            "integration_points": self._generate_integration_points,
            "nfr_considerations": self._generate_nfr_considerations,
            "recommendations": self._generate_recommendations,
            "application_overview": self._generate_application_overview,
            "health_assessment": self._generate_health_assessment,
            "modernization_options": self._generate_modernization_options,
            "action_items": self._generate_action_items,
            "integration_overview": self._generate_integration_overview,
            "data_flows": self._generate_data_flows,
            "interface_mapping": self._generate_interface_mapping,
            "pattern_recommendations": self._generate_pattern_recommendations,
            "infrastructure_overview": self._generate_infrastructure_overview,
            "security_assessment": self._generate_security_assessment,
            "availability_analysis": self._generate_availability_analysis,
            "capability_overview": self._generate_capability_overview,
            "value_stream_mapping": self._generate_value_stream_mapping,
            "maturity_assessment": self._generate_maturity_assessment,
            "requirements_summary": self._generate_requirements_summary,
            "process_impact": self._generate_process_impact,
            "stakeholder_analysis": self._generate_stakeholder_analysis,
            "user_stories": self._generate_user_stories,
            "product_overview": self._generate_product_overview,
            "capability_alignment": self._generate_capability_alignment,
            "journey_mapping": self._generate_journey_mapping,
            "roadmap_recommendations": self._generate_roadmap_recommendations,
            "key_metrics": self._generate_key_metrics,
            "risk_highlights": self._generate_risk_highlights,
            "investment_recommendations": self._generate_investment_recommendations,
            "business_impact": self._generate_business_impact,
            "investment_overview": self._generate_investment_overview,
            "technical_overview": self._generate_technical_overview,
            "implementation_guide": self._generate_implementation_guide,
            "api_details": self._generate_api_details,
            "testing_notes": self._generate_testing_notes,
            "project_overview": self._generate_project_overview,
            "deliverables": self._generate_deliverables,
            "dependencies": self._generate_dependencies,
            "risk_register": self._generate_risk_register,
            "vendor_overview": self._generate_vendor_overview,
            "evaluation_criteria": self._generate_evaluation_criteria,
            "contract_notes": self._generate_contract_notes,
        }

        generator = section_generators.get(section)
        if generator:
            return generator(response, role, domain)

        return {"content": "", "generated": False}

    def _extract_emphasis_points(self, response: str, emphasis_keywords: List[str]) -> List[str]:
        """Extract points from response that match emphasis keywords."""
        points = []
        response_lower = response.lower()

        for keyword in emphasis_keywords:
            if keyword.lower() in response_lower:
                points.append(f"Relevant to: {keyword}")

        return points

    def _format_response(self, response: str, role: StakeholderRole, config: Dict[str, Any]) -> str:
        """Format the response according to role preferences."""
        terminology_level = config.get("terminology_level", "technical")
        output_format = config.get("output_format", "general")

        # Add role-specific header
        formatted = f"## {config['name']} Perspective\n\n"
        formatted += f"*Focus: {', '.join(config.get('focus_areas', [])[:3])}*\n\n"
        formatted += response

        # Add role-specific footer with next steps
        formatted += f"\n\n---\n*Output formatted for {config['name']} ({output_format})*"

        return formatted

    # Section generators - these provide structured content extraction

    def _generate_executive_summary(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Executive Summary",
            "content": self._extract_summary(response, max_sentences=3),
            "generated": True,
        }

    def _generate_strategic_implications(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Strategic Implications",
            "content": "Strategic analysis based on the response context.",
            "generated": True,
        }

    def _generate_governance_notes(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Governance Notes",
            "content": "Governance considerations for this analysis.",
            "generated": True,
        }

    def _generate_next_steps(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Next Steps",
            "content": "Recommended next steps based on the analysis.",
            "generated": True,
        }

    def _generate_solution_overview(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Solution Overview",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_integration_points(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Integration Points",
            "content": "Key integration considerations identified.",
            "generated": True,
        }

    def _generate_nfr_considerations(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Non-Functional Requirements",
            "content": "NFR considerations including scalability, security, performance.",
            "generated": True,
        }

    def _generate_recommendations(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Recommendations",
            "content": "Key recommendations based on the analysis.",
            "generated": True,
        }

    def _generate_application_overview(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Application Overview",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_health_assessment(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Health Assessment",
            "content": "Application health assessment summary.",
            "generated": True,
        }

    def _generate_modernization_options(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Modernization Options",
            "content": "Available modernization paths and recommendations.",
            "generated": True,
        }

    def _generate_action_items(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {"title": "Action Items", "content": "Prioritized action items.", "generated": True}

    def _generate_integration_overview(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Integration Overview",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_data_flows(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Data Flows",
            "content": "Data flow analysis and mapping.",
            "generated": True,
        }

    def _generate_interface_mapping(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Interface Mapping",
            "content": "Interface catalog and mapping details.",
            "generated": True,
        }

    def _generate_pattern_recommendations(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Pattern Recommendations",
            "content": "Recommended integration patterns.",
            "generated": True,
        }

    def _generate_infrastructure_overview(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Infrastructure Overview",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_security_assessment(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Security Assessment",
            "content": "Security posture analysis.",
            "generated": True,
        }

    def _generate_availability_analysis(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Availability Analysis",
            "content": "Availability and disaster recovery assessment.",
            "generated": True,
        }

    def _generate_capability_overview(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Capability Overview",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_value_stream_mapping(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Value Stream Mapping",
            "content": "Value stream analysis and mapping.",
            "generated": True,
        }

    def _generate_maturity_assessment(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Maturity Assessment",
            "content": "Capability maturity assessment.",
            "generated": True,
        }

    def _generate_requirements_summary(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Requirements Summary",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_process_impact(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Process Impact",
            "content": "Business process impact analysis.",
            "generated": True,
        }

    def _generate_stakeholder_analysis(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Stakeholder Analysis",
            "content": "Stakeholder impact and involvement analysis.",
            "generated": True,
        }

    def _generate_user_stories(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "User Stories",
            "content": "Generated user stories based on requirements.",
            "generated": True,
        }

    def _generate_product_overview(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Product Overview",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_capability_alignment(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Capability Alignment",
            "content": "Product-capability alignment analysis.",
            "generated": True,
        }

    def _generate_journey_mapping(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Journey Mapping",
            "content": "Customer journey mapping.",
            "generated": True,
        }

    def _generate_roadmap_recommendations(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Roadmap Recommendations",
            "content": "Product roadmap recommendations.",
            "generated": True,
        }

    def _generate_key_metrics(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Key Metrics",
            "content": "Key performance indicators and metrics.",
            "generated": True,
        }

    def _generate_risk_highlights(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Risk Highlights",
            "content": "Key risks requiring attention.",
            "generated": True,
        }

    def _generate_investment_recommendations(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Investment Recommendations",
            "content": "Investment prioritization recommendations.",
            "generated": True,
        }

    def _generate_business_impact(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Business Impact",
            "content": "Business impact analysis.",
            "generated": True,
        }

    def _generate_investment_overview(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Investment Overview",
            "content": "Investment analysis and ROI considerations.",
            "generated": True,
        }

    def _generate_technical_overview(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Technical Overview",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_implementation_guide(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Implementation Guide",
            "content": "Implementation steps and guidance.",
            "generated": True,
        }

    def _generate_api_details(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "API Details",
            "content": "API specifications and contracts.",
            "generated": True,
        }

    def _generate_testing_notes(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Testing Notes",
            "content": "Testing considerations and requirements.",
            "generated": True,
        }

    def _generate_project_overview(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Project Overview",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_deliverables(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Deliverables",
            "content": "Key deliverables identified.",
            "generated": True,
        }

    def _generate_dependencies(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Dependencies",
            "content": "Project dependencies and prerequisites.",
            "generated": True,
        }

    def _generate_risk_register(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Risk Register",
            "content": "Identified risks and mitigation strategies.",
            "generated": True,
        }

    def _generate_vendor_overview(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Vendor Overview",
            "content": self._extract_summary(response, max_sentences=4),
            "generated": True,
        }

    def _generate_evaluation_criteria(
        self, response: str, role: StakeholderRole, domain: str
    ) -> Dict:
        return {
            "title": "Evaluation Criteria",
            "content": "Vendor evaluation criteria.",
            "generated": True,
        }

    def _generate_contract_notes(self, response: str, role: StakeholderRole, domain: str) -> Dict:
        return {
            "title": "Contract Notes",
            "content": "Contract considerations and notes.",
            "generated": True,
        }

    def _extract_summary(self, text: str, max_sentences: int = 3) -> str:
        """Extract a summary from text by taking first N sentences."""
        if not text:
            return ""

        sentences = text.replace("\n", " ").split(".")
        summary_sentences = [s.strip() for s in sentences[:max_sentences] if s.strip()]

        return ". ".join(summary_sentences) + "." if summary_sentences else ""
