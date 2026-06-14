"""
Motivational Element Generator Service

AI-powered generation of ArchiMate 3.2 Motivational Layer elements from
problem descriptions. Extracts Drivers, Goals, Requirements, Constraints,
Principles, and Assessments using LLM services with automatic fallback.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.models import (
    ConstraintType,
    DriverType,
    RequirementType,
    SolutionAssessment,
    SolutionConstraint,
    SolutionDriver,
    SolutionGoal,
    SolutionPrinciple,
    SolutionRequirement,
)
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class MotivationalElementGenerator:
    """
    AI-powered generator for ArchiMate 3.2 Motivational Layer elements.

    Uses LLMService with automatic fallback across providers.
    """

    def __init__(self):
        self.llm_service = LLMService()

    def generate_all_elements(
        self, problem_description: str, business_context: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate all motivational elements from problem description.

        Args:
            problem_description: The business problem/need
            business_context: Optional additional context

        Returns:
            Dict with keys: drivers, goals, requirements, constraints, principles, assessments
        """
        logger.info("Generating all motivational elements from problem description")

        full_context = problem_description
        if business_context:
            full_context += f"\n\nAdditional Context:\n{business_context}"

        try:
            # Generate all elements in one comprehensive LLM call
            prompt = self._build_comprehensive_prompt(full_context)

            response = self.llm_service.generate_text(
                prompt=prompt,
                max_tokens=3000,
                temperature=0.7,
            )

            # Parse structured response
            elements = self._parse_comprehensive_response(response)

            logger.info(
                f"Generated {len(elements.get('drivers', []))} drivers, "
                f"{len(elements.get('goals', []))} goals, "
                f"{len(elements.get('requirements', []))} requirements"
            )

            return elements

        except Exception as e:
            logger.error(f"Error generating motivational elements: {e}")
            # Return empty structure on error
            return {
                "drivers": [],
                "goals": [],
                "requirements": [],
                "constraints": [],
                "principles": [],
                "assessments": [],
            }

    def generate_drivers(self, problem_description: str) -> List[Dict[str, Any]]:
        """
        Generate business drivers from problem description.

        Returns list of driver dicts with: name, description, driver_type, impact_level
        """
        prompt = f"""Analyze this business problem and identify the key business drivers (motivating forces):

Problem: {problem_description}

Extract 3 - 5 business drivers. For each driver, identify:
1. Name (concise, 2 - 5 words)
2. Description (1 - 2 sentences explaining the driver)
3. Type (technology, stakeholder, external, or internal)
4. Impact level (1 - 5, where 5 is highest business impact)

Return ONLY valid JSON in this format:
{{
  "drivers": [
    {{
      "name": "Digital Transformation Mandate",
      "description": "Board directive to modernize legacy systems",
      "driver_type": "stakeholder",
      "impact_level": 5
    }}
  ]
}}"""

        try:
            response = self.llm_service.generate_text(prompt, max_tokens=1500, temperature=0.7)
            parsed = self._parse_json_response(response)

            drivers = parsed.get("drivers", [])

            # Validate and normalize
            for driver in drivers:
                driver["ai_generated"] = True
                driver["ai_confidence"] = 0.8
                # Normalize driver_type to enum value
                if isinstance(driver.get("driver_type"), str):
                    driver["driver_type"] = driver["driver_type"].lower()

            return drivers

        except Exception as e:
            logger.error(f"Error generating drivers: {e}")
            return []

    def generate_goals(self, problem_description: str) -> List[Dict[str, Any]]:
        """
        Generate business goals from problem description.

        Returns list of goal dicts with: name, description, priority
        """
        prompt = f"""Analyze this business problem and identify the key business goals (desired end-states):

Problem: {problem_description}

Extract 3 - 5 business goals. For each goal:
1. Name (concise, action-oriented)
2. Description (specific, measurable outcome)
3. Priority (1 - 5, where 1 is highest priority)
4. Measurement criteria (how success is measured)

Return ONLY valid JSON in this format:
{{
  "goals": [
    {{
      "name": "Reduce operational costs by 30%",
      "description": "Achieve 30% reduction in operating expenses through automation and consolidation",
      "priority": 1,
      "measurement_criteria": "Monthly operating expense reports"
    }}
  ]
}}"""

        try:
            response = self.llm_service.generate_text(prompt, max_tokens=1500, temperature=0.7)
            parsed = self._parse_json_response(response)

            goals = parsed.get("goals", [])

            for goal in goals:
                goal["ai_generated"] = True
                goal["ai_confidence"] = 0.8

            return goals

        except Exception as e:
            logger.error(f"Error generating goals: {e}")
            return []

    def generate_requirements(self, problem_description: str) -> List[Dict[str, Any]]:
        """
        Generate requirements (functional, quality, constraint).

        Returns list of requirement dicts with: name, description, requirement_type, priority
        """
        prompt = f"""Analyze this business problem and extract key requirements:

Problem: {problem_description}

Identify 5 - 10 requirements across these types:
- Functional: What the solution must DO
- Quality: Non-functional attributes (performance, scalability, security, etc.)
- Constraint: Absolute limitations or boundaries

For each requirement:
1. Name (concise, clear)
2. Description (specific, testable)
3. Type (functional, quality, or constraint)
4. Priority (1 - 5, where 1 is critical)
5. Is mandatory (true/false)

Return ONLY valid JSON in this format:
{{
  "requirements": [
    {{
      "name": "Multi-currency support",
      "description": "System must support transactions in GBP, EUR, and USD",
      "requirement_type": "functional",
      "priority": 2,
      "is_mandatory": true
    }}
  ]
}}"""

        try:
            response = self.llm_service.generate_text(prompt, max_tokens=2000, temperature=0.7)
            parsed = self._parse_json_response(response)

            requirements = parsed.get("requirements", [])

            for req in requirements:
                req["ai_generated"] = True
                req["ai_confidence"] = 0.75
                # Normalize requirement_type
                if isinstance(req.get("requirement_type"), str):
                    req["requirement_type"] = req["requirement_type"].lower()

            return requirements

        except Exception as e:
            logger.error(f"Error generating requirements: {e}")
            return []

    def generate_constraints(
        self,
        problem_description: str,
        budget_min: Optional[float] = None,
        budget_max: Optional[float] = None,
        timeline_months: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate constraints (hard limitations).

        Returns list of constraint dicts with: name, description, constraint_type, severity
        """
        context = problem_description
        if budget_min or budget_max:
            context += f"\n\nBudget: £{budget_min or 0:,.0f} - £{budget_max or 0:,.0f}"
        if timeline_months:
            context += f"\nTimeline: {timeline_months} months"

        prompt = f"""Analyze this problem and identify hard constraints (non-negotiable limitations):

{context}

Identify 3 - 7 constraints across these types:
- Budget: Financial limitations
- Timeline: Time constraints
- Resource: People, skills, availability limitations
- Compliance: Regulatory requirements
- Technical: Technology stack, integration constraints
- Organizational: Organizational policies, culture

For each constraint:
1. Name (concise)
2. Description (specific impact)
3. Type (budget, timeline, resource, compliance, technical, organizational)
4. Severity (1 - 5, where 5 is absolute hard constraint)

Return ONLY valid JSON in this format:
{{
  "constraints": [
    {{
      "name": "GDPR Compliance Mandatory",
      "description": "Solution must be fully GDPR compliant for EU customer data",
      "constraint_type": "compliance",
      "severity": 5,
      "value": "GDPR",
      "unit": "compliance"
    }}
  ]
}}"""

        try:
            response = self.llm_service.generate_text(prompt, max_tokens=1500, temperature=0.7)
            parsed = self._parse_json_response(response)

            constraints = parsed.get("constraints", [])

            for constraint in constraints:
                constraint["ai_generated"] = True
                # Normalize constraint_type
                if isinstance(constraint.get("constraint_type"), str):
                    constraint["constraint_type"] = constraint["constraint_type"].lower()

            return constraints

        except Exception as e:
            logger.error(f"Error generating constraints: {e}")
            return []

    def generate_principles(
        self, problem_description: str, organization_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate architecture principles.

        Returns list of principle dicts with: name, statement, rationale, implications
        """
        context = problem_description
        if organization_context:
            context += f"\n\nOrganizational Context: {organization_context}"

        prompt = f"""Based on this problem, recommend 3 - 5 architecture principles to guide the solution:

{context}

For each principle:
1. Name (concise, memorable)
2. Statement (clear, actionable guideline)
3. Rationale (why this principle matters)
4. Implications (impact on solution design)
5. Priority (1 - 5)

Return ONLY valid JSON in this format:
{{
  "principles": [
    {{
      "name": "Cloud First",
      "statement": "Prioritize cloud-native solutions over on-premise alternatives",
      "rationale": "Reduces infrastructure costs and improves scalability",
      "implications": "All new solutions should be designed for cloud deployment",
      "priority": 2
    }}
  ]
}}"""

        try:
            response = self.llm_service.generate_text(prompt, max_tokens=1500, temperature=0.7)
            parsed = self._parse_json_response(response)

            principles = parsed.get("principles", [])

            for principle in principles:
                principle["ai_generated"] = True
                principle["ai_confidence"] = 0.7

            return principles

        except Exception as e:
            logger.error(f"Error generating principles: {e}")
            return []

    def generate_assessments(self, problem_description: str) -> List[Dict[str, Any]]:
        """
        Generate current state assessments.

        Returns list of assessment dicts with: aspect, current_state, target_state, gap_severity
        """
        prompt = f"""Analyze this problem and assess the current state vs. target state:

Problem: {problem_description}

Identify 3 - 5 key aspects to assess. For each:
1. Aspect (what is being assessed)
2. Current state (as-is situation)
3. Target state (desired future state)
4. Gap analysis (what's missing/needs improvement)
5. Gap severity (1 - 5, where 5 is critical gap)

Return ONLY valid JSON in this format:
{{
  "assessments": [
    {{
      "aspect": "Process Automation",
      "current_state": "70% manual processes with paper-based workflows",
      "target_state": "95% automated with digital workflows",
      "gap_analysis": "Lack of workflow engine and integration capabilities",
      "gap_severity": 4
    }}
  ]
}}"""

        try:
            response = self.llm_service.generate_text(prompt, max_tokens=1500, temperature=0.7)
            parsed = self._parse_json_response(response)

            assessments = parsed.get("assessments", [])

            for assessment in assessments:
                assessment["ai_generated"] = True

            return assessments

        except Exception as e:
            logger.error(f"Error generating assessments: {e}")
            return []

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _build_comprehensive_prompt(self, problem_description: str) -> str:
        """Build comprehensive prompt for all motivational elements."""
        return f"""Analyze this business problem and extract ALL motivational layer elements per ArchiMate 3.2:

Problem: {problem_description}

Extract the following:

1. DRIVERS (3 - 5): What's motivating this need?
   - name, description, driver_type (technology/stakeholder/external/internal), impact_level (1 - 5)

2. GOALS (3 - 5): What outcomes are desired?
   - name, description, priority (1 - 5), measurement_criteria

3. REQUIREMENTS (5 - 10): What must the solution do/be?
   - name, description, requirement_type (functional/quality/constraint), priority (1 - 5), is_mandatory (true/false)

4. CONSTRAINTS (3 - 7): What are the hard limitations?
   - name, description, constraint_type (budget/timeline/resource/compliance/technical/organizational), severity (1 - 5)

5. PRINCIPLES (3 - 5): What guidelines should guide design?
   - name, statement, rationale, implications, priority (1 - 5)

6. ASSESSMENTS (3 - 5): Current vs. target state analysis
   - aspect, current_state, target_state, gap_analysis, gap_severity (1 - 5)

Return ONLY valid JSON with this structure:
{{
  "drivers": [...],
  "goals": [...],
  "requirements": [...],
  "constraints": [...],
  "principles": [...],
  "assessments": [...]
}}"""

    def _parse_comprehensive_response(self, response: str) -> Dict[str, List[Dict]]:
        """Parse comprehensive LLM response."""
        try:
            parsed = self._parse_json_response(response)

            # Ensure all keys exist
            result = {
                "drivers": parsed.get("drivers", []),
                "goals": parsed.get("goals", []),
                "requirements": parsed.get("requirements", []),
                "constraints": parsed.get("constraints", []),
                "principles": parsed.get("principles", []),
                "assessments": parsed.get("assessments", []),
            }

            # Add AI metadata
            for driver in result["drivers"]:
                driver["ai_generated"] = True
                driver["ai_confidence"] = 0.8
                if isinstance(driver.get("driver_type"), str):
                    driver["driver_type"] = driver["driver_type"].lower()

            for req in result["requirements"]:
                req["ai_generated"] = True
                req["ai_confidence"] = 0.75
                if isinstance(req.get("requirement_type"), str):
                    req["requirement_type"] = req["requirement_type"].lower()

            for constraint in result["constraints"]:
                constraint["ai_generated"] = True
                if isinstance(constraint.get("constraint_type"), str):
                    constraint["constraint_type"] = constraint["constraint_type"].lower()

            for principle in result["principles"]:
                principle["ai_generated"] = True
                principle["ai_confidence"] = 0.7

            for goal in result["goals"]:
                goal["ai_generated"] = True
                goal["ai_confidence"] = 0.8

            for assessment in result["assessments"]:
                assessment["ai_generated"] = True

            return result

        except Exception as e:
            logger.error(f"Error parsing comprehensive response: {e}")
            return {
                "drivers": [],
                "goals": [],
                "requirements": [],
                "constraints": [],
                "principles": [],
                "assessments": [],
            }

    def _parse_json_response(self, response: str) -> Dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            # Find the first { and last }
            start = response.find("{")
            end = response.rfind("}")
            if start != -1 and end != -1:
                response = response[start : end + 1]

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nResponse: {response[:500]}")
            raise
