"""
-> app.modules.ai_chat.services.ai_assistant_service

Solution AI Service

Provides AI-powered element suggestions for solution architecture design.
Uses UnifiedAILLMService with Anthropic/OpenAI fallback to suggest
ArchiMate elements across all 6 layers based on solution description and capabilities.
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Capability quality scoring (pure Python, no LLM) ─────────────────

_PROJECT_VERBS = {
    "implement", "migrate", "deploy", "build", "install", "upgrade",
    "configure", "set up", "integrate", "develop", "create", "design",
    "run", "execute", "launch",
}

_TECHNOLOGY_NAMES = {
    "kubernetes", "aws", "azure", "gcp", "salesforce", "sap", "oracle",
    "docker", "terraform", "jenkins", "kafka", "redis", "mongodb",
    "postgresql", "mysql", "elasticsearch", "grafana", "jira", "servicenow",
    "snowflake", "databricks", "tableau", "power bi", "sharepoint",
}

_ROLE_PATTERNS = {
    "chief", "officer", "manager", "director", "analyst", "engineer",
    "architect", "specialist", "coordinator", "lead", "head of",
}

_STOPWORDS = {"the", "and", "of", "for", "in", "to", "a", "an", "is", "on", "with", "by"}


def _tokenize(text: str) -> set:
    """Split text into lowercase word tokens, removing stopwords."""
    words = set(text.lower().split())
    return words - _STOPWORDS


def _token_overlap(a: str, b: str) -> float:
    """Token overlap score between two strings. 0.0-1.0."""
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    shared = tokens_a & tokens_b
    return len(shared) / max(len(tokens_a), len(tokens_b))


def score_capability_quality(
    name: str,
    description: str = "",
    brief: str = "",
    other_names: list = None,
) -> dict:
    """Score a single AI-derived capability on 5 quality dimensions.

    Returns dict with 'score' (0.0-1.0), 'checks' (dict of booleans),
    and 'warnings' (list of strings).
    """
    other_names = other_names or []
    warnings = []
    checks = {}
    name_lower = name.lower()
    words = name.split()

    # 1. Naming: no project verbs
    has_verb = any(v in name_lower for v in _PROJECT_VERBS)
    checks["naming"] = not has_verb
    if has_verb:
        matched = [v for v in _PROJECT_VERBS if v in name_lower]
        warnings.append(
            f"Contains action verb '{matched[0]}' — this looks like a project, not a capability"
        )

    # 2. Specificity: 2-8 words
    word_count = len(words)
    checks["specificity"] = 2 <= word_count <= 8
    if word_count < 2:
        warnings.append(f"Too vague ({word_count} word) — APQC capabilities are typically 2-8 words")
    elif word_count > 8:
        warnings.append(f"Too specific ({word_count} words) — consider a shorter, broader name")

    # 3. Overlap: no near-duplicate in same batch
    has_overlap = False
    for other in other_names:
        if _token_overlap(name, other) >= 0.7:
            has_overlap = True
            warnings.append(f"Near-duplicate of '{other}' in the same suggestion batch")
            break
    checks["overlap"] = not has_overlap

    # 4. Scope: not a technology, role, or activity
    has_tech = any(t in name_lower for t in _TECHNOLOGY_NAMES)
    has_role = any(r in name_lower for r in _ROLE_PATTERNS)
    checks["scope"] = not has_tech and not has_role
    if has_tech:
        matched = [t for t in _TECHNOLOGY_NAMES if t in name_lower]
        warnings.append(f"Contains technology name '{matched[0]}' — may be a product, not a capability")
    if has_role:
        matched = [r for r in _ROLE_PATTERNS if r in name_lower]
        warnings.append(f"Contains role pattern '{matched[0]}' — may be a role, not a capability")

    # 5. Relevance: at least some connection to the problem brief
    if brief:
        relevance_score = _token_overlap(name + " " + description, brief)
        checks["relevance"] = relevance_score >= 0.1
        if relevance_score < 0.1:
            warnings.append("No apparent connection to the stated business problem")
    else:
        checks["relevance"] = True  # No brief to compare against — pass by default

    score = sum(1 for v in checks.values() if v) / 5
    return {"score": score, "checks": checks, "warnings": warnings}


class SolutionAIService:
    """
    AI service for solution architecture element suggestions.

    Uses LLM to analyze solution description and capabilities to suggest
    appropriate ArchiMate elements for each layer.
    """

    # ArchiMate layer information for prompts
    LAYER_INFO = {
        "motivation": {
            "description": "Why the solution exists - stakeholders, goals, drivers, requirements",
            "elements": [
                "Stakeholder",
                "Driver",
                "Assessment",
                "Goal",
                "Outcome",
                "Constraint",
                "Principle",
                "Requirement",
                "Value",
                "Meaning",
            ],
        },
        "strategy": {
            "description": "Strategic direction - resources, capabilities, value streams",
            "elements": ["Resource", "Capability", "CourseOfAction", "ValueStream"],
        },
        "business": {
            "description": "Business operations - actors, roles, processes, services",
            "elements": [
                "BusinessActor",
                "BusinessRole",
                "BusinessProcess",
                "BusinessService",
                "BusinessCollaboration",
                "BusinessInterface",
                "BusinessEvent",
                "BusinessFunction",
                "BusinessInteraction",
                "Contract",
                "Product",
                "Representation",
            ],
        },
        "application": {
            "description": "Applications - components, services, data objects",
            "elements": [
                "ApplicationComponent",
                "ApplicationService",
                "ApplicationInterface",
                "ApplicationCollaboration",
                "ApplicationEvent",
                "ApplicationFunction",
                "ApplicationProcess",
                "ApplicationInteraction",
                "DataObject",
            ],
        },
        "technology": {
            "description": "Infrastructure - nodes, devices, networks, artifacts",
            "elements": [
                "Node",
                "Device",
                "SystemSoftware",
                "TechnologyCollaboration",
                "TechnologyInterface",
                "Path",
                "CommunicationNetwork",
                "TechnologyFunction",
                "TechnologyProcess",
                "TechnologyInteraction",
                "TechnologyEvent",
                "TechnologyService",
                "Artifact",
                "Material",
                "DistributionNetwork",
                "Facility",
                "Equipment",
            ],
        },
        "implementation": {
            "description": "Delivery - work packages, deliverables, plateaus, gaps",
            "elements": ["WorkPackage", "Deliverable", "Plateau", "Gap", "ImplementationEvent"],
        },
    }

    def __init__(self):
        """Initialize the solution AI service."""
        self.llm_service = None
        self._init_llm_service()

    def _init_llm_service(self):
        """Initialize the LLM service with fallback."""
        try:
            from .unified_ai_llm_service import UnifiedAILLMService

            self.llm_service = UnifiedAILLMService()
            logger.info("Solution AI service initialized with UnifiedAILLMService")
        except ImportError as e:
            logger.warning(f"UnifiedAILLMService not available: {e}")
            self.llm_service = None

    def suggest_elements(
        self,
        solution_description: str,
        capabilities: Optional[List[Dict]] = None,
        solution_type: Optional[str] = None,
        business_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Use AI to suggest ArchiMate elements for all 6 layers.

        Args:
            solution_description: Description of the solution
            capabilities: List of selected capabilities with categories
            solution_type: Type of solution (Platform, Product, Service, Integration)
            business_domain: Business domain of the solution

        Returns:
            Dictionary with suggested elements per layer
        """
        if not self.llm_service:
            return self._get_fallback_suggestions(solution_description, capabilities)

        try:
            prompt = self._build_archimate_prompt(
                solution_description, capabilities, solution_type, business_domain
            )

            # Try to generate using LLM
            result = self.llm_service.generate_text(prompt=prompt, max_tokens=4000, temperature=0.7)

            if result.get("success") and result.get("text"):
                parsed = self._parse_llm_response(result["text"])
                if parsed:
                    return {"success": True, "suggestions": parsed, "source": "ai"}

            # Fallback if LLM fails
            logger.warning("LLM generation failed, using fallback suggestions")
            return self._get_fallback_suggestions(solution_description, capabilities)

        except Exception as e:
            logger.error(f"Error generating element suggestions: {e}")
            return self._get_fallback_suggestions(solution_description, capabilities)

    def _build_archimate_prompt(
        self,
        description: str,
        capabilities: Optional[List[Dict]],
        solution_type: Optional[str],
        business_domain: Optional[str],
    ) -> str:
        """Build the prompt for ArchiMate element suggestion."""

        capability_text = ""
        if capabilities:
            cap_list = []
            for cap in capabilities:
                cat = cap.get("category", "required")
                name = cap.get("name", "Unknown")
                cap_list.append(f"  - {name} ({cat})")
            capability_text = "Selected capabilities:\n" + "\n".join(cap_list)

        layer_descriptions = []
        for layer, info in self.LAYER_INFO.items():
            elements = ", ".join(info["elements"][:5]) + "..."
            layer_descriptions.append(
                f"- {layer.upper()}: {info['description']} (e.g., {elements})"
            )

        prompt = f"""You are an enterprise architecture expert specializing in ArchiMate 3.2.
Analyze the following solution and suggest appropriate ArchiMate elements for each layer.

SOLUTION DETAILS:
- Description: {description}
- Type: {solution_type or 'Not specified'}
- Business Domain: {business_domain or 'Not specified'}
{capability_text}

ARCHIMATE LAYERS TO POPULATE:
{chr(10).join(layer_descriptions)}

For each layer, suggest 2 - 5 specific elements that would be part of this solution architecture.
Each element should have a name, brief description, a rationale explaining what specific
architecture question or gap this element addresses, and a decision_point label that groups
related elements under a common architecture concern (e.g., "Integration complexity",
"Data ownership", "Security boundary", "Scalability", "Business process alignment").

Respond in JSON format:
{{
    "motivation": [
        {{"element_type": "Stakeholder", "name": "Example Name", "description": "Brief description", "rationale": "Explains what architecture question this element answers", "decision_point": "Governance structure"}},
        ...
    ],
    "strategy": [...],
    "business": [...],
    "application": [...],
    "technology": [...],
    "implementation": [...]
}}

Ensure suggestions are specific to the solution described, not generic.
Focus on the most important elements for each layer.
For each element, explain what specific architecture question or gap this element addresses.
Group related elements under a decision_point label."""

        return prompt

    def _parse_llm_response(self, response_text: str) -> Optional[Dict[str, List[Dict]]]:
        """Parse the LLM response into structured suggestions."""
        try:
            # Try to find JSON in the response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                parsed = json.loads(json_str)

                # Validate structure
                valid_layers = [
                    "motivation",
                    "strategy",
                    "business",
                    "application",
                    "technology",
                    "implementation",
                ]
                result = {}

                for layer in valid_layers:
                    if layer in parsed and isinstance(parsed[layer], list):
                        result[layer] = parsed[layer]
                    else:
                        result[layer] = []

                return result

            return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return None

    def _get_fallback_suggestions(
        self, description: str, capabilities: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Generate fallback suggestions when LLM is not available.
        Provides basic template-based suggestions.
        """
        suggestions = {
            "motivation": [
                {
                    "element_type": "Stakeholder",
                    "name": "Solution Owner",
                    "description": "Primary stakeholder responsible for the solution",
                    "rationale": "Identifies who is accountable for solution outcomes and governance decisions",
                    "decision_point": "Governance structure",
                },
                {
                    "element_type": "Goal",
                    "name": "Business Value Delivery",
                    "description": "Main goal of the solution",
                    "rationale": "Defines the measurable business outcome the architecture must deliver",
                    "decision_point": "Governance structure",
                },
                {
                    "element_type": "Requirement",
                    "name": "Core Requirements",
                    "description": "Key requirements for the solution",
                    "rationale": "Captures the constraints that shape technology and design choices",
                    "decision_point": "Governance structure",
                },
            ],
            "strategy": [
                {
                    "element_type": "Capability",
                    "name": "Solution Capability",
                    "description": "Primary capability enabled by the solution",
                    "rationale": "Maps the solution to the enterprise capability model for gap analysis",
                    "decision_point": "Business process alignment",
                },
                {
                    "element_type": "ValueStream",
                    "name": "Value Delivery",
                    "description": "Value stream the solution supports",
                    "rationale": "Shows how the solution contributes to end-to-end value creation",
                    "decision_point": "Business process alignment",
                },
            ],
            "business": [
                {
                    "element_type": "BusinessProcess",
                    "name": "Core Process",
                    "description": "Main business process supported",
                    "rationale": "Identifies the process boundary the solution automates or enhances",
                    "decision_point": "Business process alignment",
                },
                {
                    "element_type": "BusinessService",
                    "name": "Business Service",
                    "description": "Business service provided",
                    "rationale": "Defines the service contract between business and application layers",
                    "decision_point": "Integration complexity",
                },
            ],
            "application": [
                {
                    "element_type": "ApplicationComponent",
                    "name": "Main Application",
                    "description": "Primary application component",
                    "rationale": "Determines build-vs-buy scope and integration surface area",
                    "decision_point": "Integration complexity",
                },
                {
                    "element_type": "ApplicationService",
                    "name": "Application Service",
                    "description": "Service provided by the application",
                    "rationale": "Defines the API boundary for consumers and downstream systems",
                    "decision_point": "Integration complexity",
                },
                {
                    "element_type": "DataObject",
                    "name": "Core Data",
                    "description": "Main data objects managed",
                    "rationale": "Clarifies data ownership and determines master data responsibilities",
                    "decision_point": "Data ownership",
                },
            ],
            "technology": [
                {
                    "element_type": "Node",
                    "name": "Infrastructure Node",
                    "description": "Infrastructure hosting the solution",
                    "rationale": "Determines hosting model and scalability characteristics",
                    "decision_point": "Scalability",
                },
                {
                    "element_type": "TechnologyService",
                    "name": "Platform Service",
                    "description": "Technology service utilized",
                    "rationale": "Identifies platform dependencies and security boundary implications",
                    "decision_point": "Security boundary",
                },
            ],
            "implementation": [
                {
                    "element_type": "WorkPackage",
                    "name": "Implementation Phase",
                    "description": "Main implementation work package",
                    "rationale": "Scopes the delivery effort for planning and resource allocation",
                    "decision_point": "Delivery planning",
                },
                {
                    "element_type": "Deliverable",
                    "name": "Solution Deliverable",
                    "description": "Key deliverable of the solution",
                    "rationale": "Defines the tangible output that validates architecture compliance",
                    "decision_point": "Delivery planning",
                },
            ],
        }

        # Add capability-based suggestions if capabilities are provided
        if capabilities:
            for cap in capabilities[:3]:  # Limit to first 3
                cap_name = cap.get("name", "Capability")
                suggestions["strategy"].append(
                    {
                        "element_type": "Capability",
                        "name": cap_name,
                        "description": f"Capability: {cap_name}",
                        "rationale": f"Maps {cap_name} to the enterprise capability model for coverage analysis",
                        "decision_point": "Business process alignment",
                    }
                )

        return {"success": True, "suggestions": suggestions, "source": "fallback"}

    CAPABILITY_SUGGESTION_PROMPT = """You are a Solution Architect designing the capability architecture for a business solution.

BUSINESS PROBLEM:
{solution_description}

MOTIVATION CONTEXT (reference by prefixed ID):
{motivation_elements_with_ids}

EXISTING CAPABILITY CATALOG (APQC hierarchy — reference where applicable):
{capability_catalog}

TASK:
Derive 5-10 capabilities this solution needs to succeed. Think like a Solution
Architect: what business capabilities must exist for this solution to deliver value?

RULES:
1. Derive capabilities from the PROBLEM, not from the catalog. The catalog is
   reference material, not a constraint.
2. If a needed capability exists in the catalog, use its EXACT name and set
   "existing": true.
3. If a needed capability is SIMILAR to one in the catalog but not exact, set
   "existing": false and include "closest_match": "Exact Catalog Name".
4. If a needed capability is entirely new, set "existing": false with no
   closest_match.
5. Prefer specific capabilities over broad ones.
6. Each must explain WHY this solution needs it.
7. Categorize each as: required (core to the solution), optional (enhances it), or future (later phase).
8. For each capability, include "derived_from": a list of prefixed motivation element IDs
   (from the MOTIVATION CONTEXT above) that justify this capability.
   Every capability MUST trace to at least one driver or goal.

Respond in JSON format:
{{
    "capabilities": [
        {{"name": "Capability name", "description": "What this does", "category": "required", "rationale": "Why needed", "existing": true, "closest_match": null, "derived_from": ["drv_42", "goal_67"]}}
    ],
    "gap_summary": "Brief: N needed, M exist, K new"
}}"""

    def _get_capability_suggestion_prompt(self) -> str:
        """Return DB-overridden capability suggestion prompt or default."""
        try:
            from app.models.ai_service import AIPromptTemplate
            override = AIPromptTemplate.query.filter_by(
                name="solution_prompt_capability_suggestion"
            ).first()
            if override and override.system_prompt:
                return override.system_prompt
        except Exception as exc:
            logger.debug("Prompt override lookup failed: %s", exc)
        return self.CAPABILITY_SUGGESTION_PROMPT

    def suggest_capabilities(
        self,
        solution_description: str,
        solution_type: Optional[str] = None,
        business_domain: Optional[str] = None,
        existing_capabilities: Optional[List[Dict]] = None,
        motivation_elements: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Use AI to suggest capabilities for a solution.

        Args:
            solution_description: Description of the solution
            solution_type: Type of solution
            business_domain: Business domain
            existing_capabilities: List of existing capabilities in the system
            motivation_elements: List of dicts with id, type, name for traceability

        Returns:
            Dictionary with suggested capability names and categories
        """
        try:
            # Build grouped catalog: "01 Product and Solution Management\n  1.1 Develop strategy\n  1.2 ..."
            catalog_lines = []
            if existing_capabilities:
                # Group by L1 parent (capabilities with code like "01", "02" are L1)
                by_parent = {}
                for cap in existing_capabilities:
                    name = cap.get("name", "")
                    # L1 caps start with 2-digit number, L2 with "N.N", L3 with "N.N.N"
                    parts = name.split(" ", 1)
                    code = parts[0] if parts else ""
                    if "." not in code and code.isdigit():
                        # L1 parent
                        by_parent.setdefault(code, {"name": name, "children": []})
                    elif "." in code:
                        parent_code = code.split(".")[0]
                        by_parent.setdefault(parent_code, {"name": parent_code, "children": []})
                        by_parent[parent_code]["children"].append(name)
                    else:
                        catalog_lines.append(f"- {name}")

                for code in sorted(by_parent.keys()):
                    group = by_parent[code]
                    catalog_lines.append(f"\n## {group['name']}")
                    for child in group["children"]:
                        catalog_lines.append(f"  - {child}")

            catalog_text = "\n".join(catalog_lines) if catalog_lines else "No capabilities available"

            # Build motivation context with prefixed IDs for traceability
            mot_lines = []
            if motivation_elements:
                _PREFIX_MAP = {"Driver": "drv", "Goal": "goal", "Constraint": "con"}
                for m in motivation_elements:
                    prefix = _PREFIX_MAP.get(m.get("type", ""), "drv")
                    prefixed_id = f"{prefix}_{m['id']}"
                    mot_lines.append(f"- {m['type']} ({prefixed_id}): {m['name']}")
            mot_text = "\n".join(mot_lines) if mot_lines else "No motivation elements provided"

            prompt_template = self._get_capability_suggestion_prompt()
            prompt = prompt_template.format(
                solution_description=solution_description,
                capability_catalog=catalog_text,
                motivation_elements_with_ids=mot_text,
            )

            # Use the same LLM pathway as the orchestrator (works with DB-stored API keys)
            from app.modules.ai_chat.services.llm_service import LLMService
            provider, model = LLMService._get_configured_provider()
            raw_text, _ = LLMService._call_llm(prompt=prompt, model=model, provider=provider)

            if not raw_text:
                return {"success": False, "error": "LLM returned empty response", "capabilities": []}

            logger.info("Capability suggestion raw response (%d chars): %s", len(raw_text), raw_text[:300])
            parsed, gap_summary = self._parse_capability_response(raw_text)
            if parsed:
                return {"success": True, "capabilities": parsed, "gap_summary": gap_summary or "", "source": "ai"}

            logger.warning("Failed to parse capability response: %s", raw_text[:500])
            return {"success": False, "error": "Failed to parse LLM response", "capabilities": []}

        except Exception as e:
            logger.error(f"Error suggesting capabilities: {e}")
            return {"success": False, "error": str(e), "capabilities": []}

    def _parse_capability_response(self, response_text: str) -> tuple:
        """Parse capability suggestions from LLM response.

        Returns (capabilities_list, gap_summary) or (None, None).
        """
        import re
        try:
            # Strip markdown code fences if present
            text = response_text.strip()
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```\s*$', '', text)

            json_start = text.find("{")
            json_end = text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = text[json_start:json_end]
                parsed = json.loads(json_str)

                if "capabilities" in parsed and isinstance(parsed["capabilities"], list):
                    gap_summary = parsed.get("gap_summary", "")
                    return parsed["capabilities"], gap_summary

            return None, None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse capability response: {e}")
            return None, None

    def generate_requirements(
        self,
        solution_description: str,
        capabilities: Optional[List[Dict]] = None,
        solution_type: Optional[str] = None,
        business_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI-powered requirements from solution description.

        Uses existing MotivationLayerService patterns to generate:
        - Functional Requirements
        - Non-Functional Requirements (Quality Attributes)
        - Constraints

        Args:
            solution_description: Description of the solution
            capabilities: List of selected capabilities
            solution_type: Type of solution
            business_domain: Business domain

        Returns:
            Dictionary with generated requirements
        """
        if not self.llm_service:
            return self._get_fallback_requirements(solution_description, capabilities)

        try:
            capability_text = ""
            if capabilities:
                cap_list = [
                    f"  - {c.get('name', 'Unknown')} ({c.get('category', 'required')})"
                    for c in capabilities[:10]
                ]
                capability_text = "Selected capabilities:\n" + "\n".join(cap_list)

            prompt = f"""You are an expert Enterprise Architect specializing in ArchiMate 3.2 Motivation Layer.
Your task is to generate comprehensive requirements from a solution description.

SOLUTION DETAILS:
- Description: {solution_description}
- Type: {solution_type or 'Not specified'}
- Business Domain: {business_domain or 'Not specified'}
{capability_text}

Generate requirements covering:

1. **Functional Requirements**: What the system MUST do
   - Use clear, testable language (MUST, SHALL keywords)
   - Include specific functionality needed

2. **Non-Functional Requirements**: Quality attributes
   - Performance (response times, throughput)
   - Security (authentication, encryption)
   - Scalability (concurrent users)
   - Availability (uptime SLA)
   - Usability
   - Compliance

3. **Constraints**: Restrictions on implementation
   - Technical constraints
   - Budget/resource constraints
   - Timeline constraints

For each requirement provide:
- title: Clear requirement title
- description: Detailed description using RFC 2119 keywords (MUST, SHALL, SHOULD, MAY)
- category: "Functional", "Non-Functional", or "Constraint"
- type: Subcategory (e.g., "performance", "security", "usability", "data", "integration", "budget", "timeline")
- priority: "critical", "high", "medium", or "low"
- rationale: WHY this requirement exists
- acceptance_criteria: How to verify (1 - 2 bullet points)

Return ONLY a JSON object:
{{
    "requirements": [
        {{
            "title": "System SHALL validate input data",
            "description": "The system MUST validate all user input against defined business rules before processing.",
            "category": "Functional",
            "type": "data_validation",
            "priority": "high",
            "rationale": "Ensures data integrity and prevents invalid data",
            "acceptance_criteria": ["All inputs validated within 100ms", "Error messages display for invalid data"]
        }}
    ]
}}

Generate 8 - 12 well-structured requirements covering functional, non-functional, and constraints.
"""

            result = self.llm_service.generate_text(prompt=prompt, max_tokens=4000, temperature=0.7)

            if result.get("success") and result.get("text"):
                parsed = self._parse_requirements_response(result["text"])
                if parsed:
                    return {"success": True, "requirements": parsed, "source": "ai"}

            logger.warning("LLM generation failed, using fallback requirements")
            return self._get_fallback_requirements(solution_description, capabilities)

        except Exception as e:
            logger.error(f"Error generating requirements: {e}")
            return self._get_fallback_requirements(solution_description, capabilities)

    def _parse_requirements_response(self, response_text: str) -> Optional[List[Dict]]:
        """Parse requirements from LLM response."""
        try:
            # Extract JSON from response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "{" in response_text and "}" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()

            parsed = json.loads(json_text)

            if "requirements" in parsed and isinstance(parsed["requirements"], list):
                return parsed["requirements"]

            return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse requirements JSON: {e}")
            return None

    def _get_fallback_requirements(
        self, description: str, capabilities: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Generate fallback requirements when LLM is not available."""
        requirements = [
            {
                "title": "System SHALL provide secure user authentication",
                "description": "The system MUST implement secure authentication with MFA support.",
                "category": "Non-Functional",
                "type": "security",
                "priority": "critical",
                "rationale": "Ensure authorized access and protect sensitive data",
                "acceptance_criteria": [
                    "MFA implemented",
                    "Session timeout after 30 min inactivity",
                ],
            },
            {
                "title": "System SHALL meet performance requirements",
                "description": "The system MUST respond to user requests within 2 seconds under normal load.",
                "category": "Non-Functional",
                "type": "performance",
                "priority": "high",
                "rationale": "Ensure good user experience and productivity",
                "acceptance_criteria": [
                    "95% requests < 2 sec response time",
                    "Support 100 concurrent users",
                ],
            },
            {
                "title": "System SHALL provide data validation",
                "description": "The system MUST validate all user input before processing.",
                "category": "Functional",
                "type": "data_validation",
                "priority": "high",
                "rationale": "Prevent data corruption and security vulnerabilities",
                "acceptance_criteria": ["Input validation on all forms", "Clear error messages"],
            },
            {
                "title": "System SHALL ensure data integrity",
                "description": "The system MUST maintain ACID compliance for all transactions.",
                "category": "Non-Functional",
                "type": "reliability",
                "priority": "high",
                "rationale": "Ensure business data consistency and auditability",
                "acceptance_criteria": [
                    "Transaction rollback on failure",
                    "Audit trail maintained",
                ],
            },
            {
                "title": "System SHALL provide availability SLA",
                "description": "The system SHOULD provide 99.5% uptime during business hours.",
                "category": "Non-Functional",
                "type": "availability",
                "priority": "medium",
                "rationale": "Ensure business continuity and user productivity",
                "acceptance_criteria": ["Monthly uptime > 99.5%", "Scheduled maintenance windows"],
            },
            {
                "title": "Implementation SHALL follow budget constraints",
                "description": "Implementation MUST be completed within approved budget allocation.",
                "category": "Constraint",
                "type": "budget",
                "priority": "high",
                "rationale": "Financial governance and project viability",
                "acceptance_criteria": ["Monthly budget tracking", "Variance < 10%"],
            },
        ]

        # Add capability-based requirements if provided
        if capabilities:
            for cap in capabilities[:3]:
                cap_name = cap.get("name", "Capability")
                requirements.append(
                    {
                        "title": f"System SHALL support {cap_name}",
                        "description": f"The system MUST provide functionality to support the {cap_name} capability.",
                        "category": "Functional",
                        "type": "capability",
                        "priority": cap.get("category", "required") == "required"
                        and "high"
                        or "medium",
                        "rationale": f"Enable {cap_name} business capability",
                        "acceptance_criteria": [
                            f"{cap_name} functionality available",
                            "User acceptance testing passed",
                        ],
                    }
                )

        return {"success": True, "requirements": requirements, "source": "fallback"}

    def generate_roadmap_items(
        self,
        solution_description: str,
        capabilities: Optional[List[Dict]] = None,
        solution_type: Optional[str] = None,
        archimate_elements: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Generate implementation roadmap items for the solution.

        Creates work packages organized by implementation phase.

        Args:
            solution_description: Description of the solution
            capabilities: List of capabilities
            solution_type: Type of solution
            archimate_elements: ArchiMate elements by layer

        Returns:
            Dictionary with roadmap items organized by phase
        """
        if not self.llm_service:
            return self._get_fallback_roadmap(solution_description, capabilities)

        try:
            capability_text = ""
            if capabilities:
                cap_list = [
                    f"  - {c.get('name', 'Unknown')} ({c.get('category', 'required')})"
                    for c in capabilities[:10]
                ]
                capability_text = "Capabilities to implement:\n" + "\n".join(cap_list)

            elements_text = ""
            if archimate_elements:
                for layer, elems in archimate_elements.items():
                    if elems:
                        elem_names = [e.get("name", "Unknown") for e in elems[:5]]
                        elements_text += (
                            f"\n{layer.title()} layer elements: {', '.join(elem_names)}"
                        )

            prompt = f"""You are an enterprise architecture expert creating an implementation roadmap.

SOLUTION DETAILS:
- Description: {solution_description}
- Type: {solution_type or 'Not specified'}
{capability_text}
{elements_text}

Create an implementation roadmap with work packages organized into phases:
- Phase 1: Foundation (infrastructure, core setup)
- Phase 2: Core Features (main functionality)
- Phase 3: Enhancement (additional features)
- Phase 4: Go-Live (deployment, training)

For each work package provide:
- name: Work package name
- description: What will be delivered
- phase: "phase1", "phase2", "phase3", or "phase4"
- priority: "critical", "high", "medium", or "low"
- duration_weeks: Estimated duration in weeks
- dependencies: List of dependent work package names

Return ONLY a JSON object:
{{
    "roadmap_items": [
        {{
            "name": "Infrastructure Setup",
            "description": "Provision cloud infrastructure and networking",
            "phase": "phase1",
            "priority": "critical",
            "duration_weeks": 2,
            "dependencies": []
        }}
    ]
}}

Generate 8 - 15 work packages covering the full implementation lifecycle.
"""

            result = self.llm_service.generate_text(prompt=prompt, max_tokens=3000, temperature=0.7)

            if result.get("success") and result.get("text"):
                parsed = self._parse_roadmap_response(result["text"])
                if parsed:
                    return {"success": True, "roadmap_items": parsed, "source": "ai"}

            return self._get_fallback_roadmap(solution_description, capabilities)

        except Exception as e:
            logger.error(f"Error generating roadmap: {e}")
            return self._get_fallback_roadmap(solution_description, capabilities)

    def _parse_roadmap_response(self, response_text: str) -> Optional[List[Dict]]:
        """Parse roadmap items from LLM response."""
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "{" in response_text and "}" in response_text:
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()

            parsed = json.loads(json_text)

            if "roadmap_items" in parsed and isinstance(parsed["roadmap_items"], list):
                return parsed["roadmap_items"]

            return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse roadmap JSON: {e}")
            return None

    def _get_fallback_roadmap(
        self, description: str, capabilities: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Generate fallback roadmap when LLM is not available."""
        roadmap_items = [
            {
                "name": "Infrastructure Setup",
                "description": "Provision cloud infrastructure, networking, and security baseline",
                "phase": "phase1",
                "priority": "critical",
                "duration_weeks": 2,
                "dependencies": [],
            },
            {
                "name": "Development Environment",
                "description": "Setup CI/CD pipelines, code repositories, and dev tools",
                "phase": "phase1",
                "priority": "high",
                "duration_weeks": 1,
                "dependencies": ["Infrastructure Setup"],
            },
            {
                "name": "Core Application Framework",
                "description": "Implement base application architecture and patterns",
                "phase": "phase2",
                "priority": "critical",
                "duration_weeks": 4,
                "dependencies": ["Development Environment"],
            },
            {
                "name": "Database Design & Implementation",
                "description": "Design and implement data model and database",
                "phase": "phase2",
                "priority": "high",
                "duration_weeks": 3,
                "dependencies": ["Core Application Framework"],
            },
            {
                "name": "User Authentication & Authorization",
                "description": "Implement security features including SSO integration",
                "phase": "phase2",
                "priority": "critical",
                "duration_weeks": 2,
                "dependencies": ["Core Application Framework"],
            },
            {
                "name": "Core Feature Implementation",
                "description": "Develop main business features and workflows",
                "phase": "phase2",
                "priority": "high",
                "duration_weeks": 6,
                "dependencies": [
                    "Database Design & Implementation",
                    "User Authentication & Authorization",
                ],
            },
            {
                "name": "Integration Development",
                "description": "Build integrations with external systems",
                "phase": "phase3",
                "priority": "high",
                "duration_weeks": 4,
                "dependencies": ["Core Feature Implementation"],
            },
            {
                "name": "Advanced Features",
                "description": "Implement additional features and enhancements",
                "phase": "phase3",
                "priority": "medium",
                "duration_weeks": 3,
                "dependencies": ["Core Feature Implementation"],
            },
            {
                "name": "Performance Optimization",
                "description": "Optimize application performance and scalability",
                "phase": "phase3",
                "priority": "medium",
                "duration_weeks": 2,
                "dependencies": ["Core Feature Implementation"],
            },
            {
                "name": "User Acceptance Testing",
                "description": "Conduct UAT with business stakeholders",
                "phase": "phase4",
                "priority": "critical",
                "duration_weeks": 2,
                "dependencies": ["Integration Development", "Advanced Features"],
            },
            {
                "name": "Training & Documentation",
                "description": "Create user guides and conduct training sessions",
                "phase": "phase4",
                "priority": "high",
                "duration_weeks": 2,
                "dependencies": ["User Acceptance Testing"],
            },
            {
                "name": "Production Deployment",
                "description": "Deploy solution to production environment",
                "phase": "phase4",
                "priority": "critical",
                "duration_weeks": 1,
                "dependencies": ["Training & Documentation"],
            },
        ]

        return {"success": True, "roadmap_items": roadmap_items, "source": "fallback"}
