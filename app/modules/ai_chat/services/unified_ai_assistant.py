"""
-> app.modules.ai_chat.services.ai_assistant_service

Unified AI Assistant Service

Provides intelligent, context-aware assistance for enterprise architects
with deep understanding of ArchiMate 3.2 and TOGAF frameworks.

Features:
- ArchiMate 3.2 element guidance and validation
- TOGAF ADM phase recommendations
- Real-time architecture workflow assistance
- Context-aware suggestions during modeling
- Compliance checking against architectural principles
"""

import logging
from datetime import datetime
from typing import Any, Dict

from app.services.context_aware_ai_helper import ContextAwareAIHelper
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class UnifiedAIAssistant:
    """
    Unified AI Assistant for Enterprise Architecture

    Combines context awareness with deep ArchiMate 3.2 and TOGAF knowledge
    to provide intelligent guidance throughout architecture activities.
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.context_helper = ContextAwareAIHelper()
        self.archimate_knowledge = self._load_archimate_knowledge()
        self.togaf_knowledge = self._load_togaf_knowledge()

    def _load_archimate_knowledge(self) -> Dict[str, Any]:
        """Load ArchiMate 3.2 knowledge base"""
        return {
            "layers": {
                "business": [
                    "Business Actor",
                    "Business Role",
                    "Business Collaboration",
                    "Business Interface",
                    "Business Process",
                    "Business Function",
                    "Business Interaction",
                    "Business Event",
                    "Business Service",
                    "Business Object",
                    "Contract",
                    "Product",
                    "Representation",
                ],
                "application": [
                    "Application Component",
                    "Application Collaboration",
                    "Application Interface",
                    "Application Function",
                    "Application Interaction",
                    "Application Process",
                    "Application Event",
                    "Application Service",
                    "Data Object",
                ],
                "technology": [
                    "Node",
                    "Device",
                    "System Software",
                    "Technology Collaboration",
                    "Technology Interface",
                    "Technology Function",
                    "Technology Process",
                    "Technology Interaction",
                    "Technology Event",
                    "Technology Service",
                    "Artifact",
                    "Communication Network",
                    "Path",
                ],
                "physical": ["Equipment", "Facility", "Distribution Network", "Material"],
                "motivation": [
                    "Stakeholder",
                    "Driver",
                    "Assessment",
                    "Goal",
                    "Outcome",
                    "Principle",
                    "Requirement",
                    "Constraint",
                ],
                "strategy": ["Resource", "Capability", "Value Stream", "Course of Action"],
                "implementation_migration": [
                    "Work Package",
                    "Deliverable",
                    "Implementation Event",
                    "Plateau",
                    "Gap",
                ],
            },
            "relationships": [
                "Composition",
                "Aggregation",
                "Assignment",
                "Realization",
                "Serving",
                "Access",
                "Influence",
                "Association",
                "Specialization",
                "Flow",
                "Triggering",
                "Grouping",
            ],
            "principles": [
                "Elements should be modeled at appropriate level of abstraction",
                "Use specialization for detailed modeling",
                "Relationships should have clear semantics",
                "Views should serve stakeholder needs",
            ],
        }

    def _load_togaf_knowledge(self) -> Dict[str, Any]:
        """Load TOGAF ADM knowledge base"""
        return {
            "phases": {
                "preliminary": "Framework and principles for architecture",
                "architecture_vision": "Business requirements and architecture vision",
                "business_architecture": "Business strategy, governance, organization",
                "information_systems_architectures": "Data and application architectures",
                "technology_architecture": "Infrastructure and technology components",
                "opportunities_and_solutions": "Identify and evaluate solution options",
                "migration_planning": "Implementation and migration planning",
                "implementation_governance": "Governance of implementation",
                "architecture_change_management": "Manage changes to architecture",
                "requirements_management": "Manage requirements throughout ADM",
            },
            "artifacts": {
                "catalogs": ["Business Capability Catalog", "Application Portfolio Catalog"],
                "diagrams": ["Business Capability Map", "Value Stream Map"],
                "matrices": ["Business Capability/Application Matrix"],
                "principles": ["Architecture Principles", "Business Principles"],
            },
            "building_blocks": {
                "architecture_building_blocks": "Reusable components",
                "solution_building_blocks": "Implementation components",
            },
        }

    def get_guidance(self, context: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """
        Provide intelligent guidance based on context and user query

        Args:
            context: Current user context (page, workflow, data)
            user_query: User's question or request for guidance

        Returns:
            Dict with guidance, suggestions, and next steps
        """
        try:
            # Analyze context
            context_analysis = self._analyze_context(context)

            # Determine guidance type
            guidance_type = self._classify_guidance_request(user_query, context_analysis)

            # Generate appropriate guidance
            if guidance_type == "archimate_modeling":
                guidance = self._get_archimate_guidance(user_query, context_analysis)
            elif guidance_type == "togaf_phase":
                guidance = self._get_togaf_guidance(user_query, context_analysis)
            elif guidance_type == "validation":
                guidance = self._get_validation_guidance(user_query, context_analysis)
            elif guidance_type == "best_practice":
                guidance = self._get_best_practice_guidance(user_query, context_analysis)
            else:
                guidance = self._get_general_guidance(user_query, context_analysis)

            return {
                "guidance": guidance,
                "context_analysis": context_analysis,
                "guidance_type": guidance_type,
                "timestamp": datetime.utcnow().isoformat(),
                "confidence": self._calculate_confidence(guidance),
            }

        except Exception as e:
            logger.error(f"Error generating guidance: {e}")
            return {
                "guidance": "I apologize, but I encountered an error while generating guidance. Please try rephrasing your question.",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _analyze_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze current user context"""
        analysis = {
            "current_page": context.get("page", "unknown"),
            "workflow_stage": context.get("workflow", "unknown"),
            "active_elements": context.get("elements", []),
            "user_role": context.get("role", "architect"),
            "domain_focus": self._determine_domain_focus(context),
        }

        # Add ArchiMate/TOGAF specific analysis
        analysis["archimate_layer"] = self._identify_archimate_layer(context)
        analysis["togaf_phase"] = self._identify_togaf_phase(context)

        return analysis

    def _classify_guidance_request(self, query: str, context: Dict[str, Any]) -> str:
        """Classify the type of guidance requested"""
        query_lower = query.lower()

        # ArchiMate modeling guidance
        if any(
            term in query_lower
            for term in ["archimate", "element", "relationship", "layer", "model"]
        ):
            return "archimate_modeling"

        # TOGAF phase guidance
        if any(
            term in query_lower for term in ["togaf", "adm", "phase", "artifact", "deliverable"]
        ):
            return "togaf_phase"

        # Validation guidance
        if any(term in query_lower for term in ["validate", "check", "compliance", "correct"]):
            return "validation"

        # Best practice guidance
        if any(term in query_lower for term in ["best practice", "recommend", "should", "how to"]):
            return "best_practice"

        return "general"

    def _get_archimate_guidance(self, query: str, context: Dict[str, Any]) -> str:
        """Provide ArchiMate-specific guidance"""
        layer = context.get("archimate_layer", "business")

        prompt = f"""
        As an ArchiMate 3.2 expert, provide guidance for: {query}

        Context:
        - Current layer: {layer}
        - Available elements: {self.archimate_knowledge['layers'].get(layer, [])}
        - Relationships: {self.archimate_knowledge['relationships']}

        Provide specific, actionable guidance following ArchiMate best practices.
        """

        try:
            response = self.llm_service.generate_from_prompt(prompt=prompt, max_tokens=500)
            return response
        except Exception as e:
            logger.error(f"ArchiMate guidance error: {e}")
            raise

    def _get_togaf_guidance(self, query: str, context: Dict[str, Any]) -> str:
        """Provide TOGAF-specific guidance"""
        phase = context.get("togaf_phase", "preliminary")

        prompt = f"""
        As a TOGAF expert, provide guidance for: {query}

        Context:
        - Current ADM phase: {phase}
        - Phase description: {self.togaf_knowledge['phases'].get(phase, 'Unknown phase')}

        Provide guidance aligned with TOGAF ADM processes and artifacts.
        """

        try:
            response = self.llm_service.generate_from_prompt(prompt=prompt, max_tokens=500)
            return response
        except Exception as e:
            logger.error(f"TOGAF guidance error: {e}")
            raise

    def _get_validation_guidance(self, query: str, context: Dict[str, Any]) -> str:
        """Provide validation guidance"""
        return f"""
        For validation in {context.get('domain_focus', 'enterprise architecture')}:

        1. Check element relationships follow ArchiMate semantics
        2. Ensure layering is maintained (business → application → technology)
        3. Validate against organizational principles
        4. Verify stakeholder requirements are addressed
        5. Confirm traceability to business objectives

        Use the validation tools available in the platform for automated checking.
        """

    def _get_best_practice_guidance(self, query: str, context: Dict[str, Any]) -> str:
        """Provide best practice guidance"""
        return f"""
        Best practices for {context.get('domain_focus', 'architecture modeling')}:

        • Start with business capabilities and value streams
        • Use appropriate level of abstraction
        • Maintain clear relationships and dependencies
        • Document assumptions and constraints
        • Validate with stakeholders regularly
        • Follow established frameworks (TOGAF, ArchiMate)

        Consider the context of your current work and organizational standards.
        """

    def _get_general_guidance(self, query: str, context: Dict[str, Any]) -> str:
        """Provide general guidance"""
        prompt = f"""
        Provide helpful guidance for an enterprise architect regarding: {query}

        Consider the context of enterprise architecture, ArchiMate modeling, and TOGAF framework.
        Keep the response practical and actionable.
        """

        try:
            response = self.llm_service.generate_from_prompt(prompt=prompt, max_tokens=300)
            return response
        except Exception as e:
            logger.error(f"General guidance error: {e}")
            raise  # Re-raise to let outer error handler catch it

    def _determine_domain_focus(self, context: Dict[str, Any]) -> str:
        """Determine the domain focus from context"""
        page = context.get("page", "").lower()
        workflow = context.get("workflow", "").lower()

        if "capability" in page or "business" in workflow:
            return "business architecture"
        elif "application" in page or "system" in workflow:
            return "application architecture"
        elif "technology" in page or "infrastructure" in workflow or "technology" in workflow:
            return "technology architecture"
        elif (
            "governance" in page
            or "compliance" in page
            or "governance" in workflow
            or "compliance" in workflow
        ):
            return "architecture governance"
        else:
            return "enterprise architecture"

    def _identify_archimate_layer(self, context: Dict[str, Any]) -> str:
        """Identify the current ArchiMate layer"""
        domain = self._determine_domain_focus(context)

        layer_map = {
            "business architecture": "business",
            "application architecture": "application",
            "technology architecture": "technology",
            "architecture governance": "motivation",
        }

        return layer_map.get(domain, "business")

    def _identify_togaf_phase(self, context: Dict[str, Any]) -> str:
        """Identify the current TOGAF ADM phase"""
        workflow = context.get("workflow", "").lower()

        if "vision" in workflow:
            return "architecture_vision"
        elif "business" in workflow:
            return "business_architecture"
        elif "application" in workflow or "data" in workflow:
            return "information_systems_architectures"
        elif "technology" in workflow or "infrastructure" in workflow:
            return "technology_architecture"
        elif "solution" in workflow or "evaluation" in workflow:
            return "opportunities_and_solutions"
        elif "migration" in workflow or "implementation" in workflow or "planning" in workflow:
            return "migration_planning"
        else:
            return "preliminary"

    def _calculate_confidence(self, guidance: str) -> float:
        """Calculate confidence score for the guidance"""
        # Simple heuristic based on guidance length and specificity
        if len(guidance) < 50:
            return 0.5
        elif len(guidance) > 200:
            return 0.9
        else:
            return 0.7
