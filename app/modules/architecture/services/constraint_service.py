"""
AI-Powered Constraint Management Service for ArchiMate 3.2 Motivation Layer

This service provides comprehensive Constraint modeling and enforcement:
- Constraint extraction from business context
- Requirement validation against constraints
- Constraint conflict detection
- Feasibility analysis
- Trade-off analysis when constraints conflict

ArchiMate 3.2 Compliance:
- Constraint is a Motivation Layer element
- Constraint restricts realization of goals
- Constraint can influence requirements
- Constraint represents hard/soft limitations
"""

import json
import logging
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from app import db
from app.models import (
    ArchiMateElement,
    ArchiMateRelationship,
    ArchitectureModel,
    BusinessCapability,
    ConstraintElement,
    Requirement,
)
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ConstraintService:
    """
    AI-powered service for ArchiMate 3.2 Constraint element management.

    Capabilities:
    - Extract constraints from business context
    - Validate requirements against constraints
    - Detect constraint conflicts
    - Perform feasibility analysis
    - Recommend trade-offs when constraints conflict
    """

    def __init__(self):
        self.llm_service = LLMService()

    # ========================================================================
    # Constraint Extraction Methods
    # ========================================================================

    def extract_constraints_from_context(
        self, business_context: str, architecture_id: int
    ) -> List[ConstraintElement]:
        """
        Extract all types of constraints from business context using AI.

        Constraint Types:
        - Budget: Financial limitations
        - Timeline: Temporal deadlines
        - Regulatory: Legal/compliance mandates
        - Technical: Technology restrictions
        - Resource: People/skills availability
        - Platform: Infrastructure limitations
        - Vendor: Vendor lock-in, contracts
        - Organizational: Policies, governance

        Args:
            business_context: Text describing business situation/limitations
            architecture_id: ID of the ArchitectureModel

        Returns:
            List of ConstraintElement instances

        Example:
            >>> context = '''
            ... Budget is capped at €5M for this initiative.
            ... Must launch by Q2 2026 (non-negotiable deadline).
            ... GDPR requires EU data residency - cannot use US-based AWS.
            ... Only 2 Java developers available on team.
            ... '''
            >>> constraints = service.extract_constraints_from_context(context, arch_id=1)
            >>> # Returns 4 constraints with types and severities
        """
        prompt = self._build_constraint_extraction_prompt(business_context)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            constraints_data = json.loads(response)

            if not isinstance(constraints_data, dict) or "constraints" not in constraints_data:
                raise ValueError("Invalid response format from LLM")

            constraints = []
            for constraint_info in constraints_data["constraints"]:
                constraint = self._create_constraint(constraint_info, architecture_id)
                constraints.append(constraint)

            db.session.commit()
            return constraints

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Constraint extraction failed: {str(e)}")

    def extract_regulatory_constraints(
        self, business_context: str, architecture_id: int, regulations: Optional[List[str]] = None
    ) -> List[ConstraintElement]:
        """
        Extract regulatory/compliance constraints specifically.

        Args:
            business_context: Business context text
            architecture_id: ID of the ArchitectureModel
            regulations: Optional list of specific regulations to check

        Returns:
            List of regulatory ConstraintElements
        """
        prompt = self._build_regulatory_constraint_prompt(business_context, regulations)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            constraints_data = json.loads(response)

            constraints = []
            for constraint_info in constraints_data.get("constraints", []):
                constraint = self._create_constraint(constraint_info, architecture_id)
                constraints.append(constraint)

            db.session.commit()
            return constraints

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Regulatory constraint extraction failed: {str(e)}")

    # ========================================================================
    # Constraint Validation Methods
    # ========================================================================

    def validate_requirement_against_constraints(
        self, requirement_id: int, constraint_ids: Optional[List[int]] = None
    ) -> Dict:
        """
        Validate if a requirement violates any constraints.

        Args:
            requirement_id: ID of the Requirement to validate
            constraint_ids: Optional specific constraints to check (if None, checks all active)

        Returns:
            Dict with validation results:
            {
                'feasible': False,
                'violations': [
                    {
                        'constraint_id': 3,
                        'constraint_name': 'Budget Cap €5M',
                        'constraint_type': 'budget',
                        'is_hard_constraint': True,
                        'violation': 'Estimated cost €8M exceeds budget cap of €5M',
                        'severity': 'critical',
                        'resolution_options': [
                            'Reduce scope to fit budget',
                            'Seek budget increase approval',
                            'Phase implementation over multiple years'
                        ]
                    }
                ],
                'warnings': [...],
                'feasibility_score': 40  # 0 - 100
            }
        """
        requirement = db.session.get(Requirement, requirement_id)
        if not requirement:
            raise ValueError(f"Requirement {requirement_id} not found")

        # Get constraints to check
        if constraint_ids:
            constraints = ConstraintElement.query.filter(
                ConstraintElement.id.in_(constraint_ids)
            ).all()
        else:
            constraints = ConstraintElement.query.filter_by(
                architecture_id=requirement.architecture_id, status="active"
            ).all()

        if not constraints:
            return {"feasible": True, "violations": [], "warnings": []}

        # Filter to only active constraints
        active_constraints = [c for c in constraints if c.is_active]

        if not active_constraints:
            return {"feasible": True, "violations": [], "warnings": []}

        prompt = self._build_constraint_validation_prompt(requirement, active_constraints)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            validation_result = json.loads(response)
            return validation_result

        except Exception as e:
            raise Exception(f"Constraint validation failed: {str(e)}")

    def validate_architecture_against_constraints(self, architecture_id: int) -> Dict:
        """
        Validate entire architecture against all constraints.

        Checks all requirements and capabilities against all active constraints.

        Args:
            architecture_id: ID of the ArchitectureModel

        Returns:
            Dict with comprehensive validation:
            {
                'total_requirements': 50,
                'feasible_requirements': 38,
                'blocked_requirements': 12,
                'constraint_violations_by_type': {
                    'budget': 5,
                    'timeline': 3,
                    'technical': 4
                },
                'most_restrictive_constraints': [...],
                'overall_feasibility': 76  # %
            }
        """
        requirements = Requirement.query.filter_by(architecture_id=architecture_id).all()

        constraints = ConstraintElement.query.filter_by(
            architecture_id=architecture_id, status="active"
        ).all()

        active_constraints = [c for c in constraints if c.is_active]

        if not requirements:
            return {"total_requirements": 0}

        total_reqs = len(requirements)
        feasible_count = 0
        violations_by_type = {}
        constraint_violation_counts = {}

        for req in requirements:
            validation = self.validate_requirement_against_constraints(
                req.id, [c.id for c in active_constraints]
            )

            if validation.get("feasible", True):
                feasible_count += 1
            else:
                for violation in validation.get("violations", []):
                    constraint_type = violation.get("constraint_type", "unknown")
                    violations_by_type[constraint_type] = (
                        violations_by_type.get(constraint_type, 0) + 1
                    )

                    constraint_id = violation.get("constraint_id")
                    if constraint_id:
                        constraint_violation_counts[constraint_id] = (
                            constraint_violation_counts.get(constraint_id, 0) + 1
                        )

        # Identify most restrictive constraints
        most_restrictive = sorted(
            constraint_violation_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        most_restrictive_constraints = []
        for constraint_id, count in most_restrictive:
            constraint = db.session.get(ConstraintElement, constraint_id)
            if constraint:
                most_restrictive_constraints.append(
                    {
                        "constraint_id": constraint_id,
                        "constraint_name": constraint.name,
                        "constraint_type": constraint.constraint_type,
                        "requirements_blocked": count,
                        "is_hard_constraint": constraint.is_hard_constraint,
                    }
                )

        return {
            "total_requirements": total_reqs,
            "feasible_requirements": feasible_count,
            "blocked_requirements": total_reqs - feasible_count,
            "overall_feasibility": round((feasible_count / total_reqs) * 100, 1),
            "constraint_violations_by_type": violations_by_type,
            "most_restrictive_constraints": most_restrictive_constraints,
            "total_active_constraints": len(active_constraints),
        }

    # ========================================================================
    # Conflict Detection Methods
    # ========================================================================

    def detect_constraint_conflicts(self, architecture_id: int) -> List[Dict]:
        """
        Detect conflicting constraints (mutually exclusive or impossible to satisfy simultaneously).

        Args:
            architecture_id: ID of the ArchitectureModel

        Returns:
            List of conflicts:
            [
                {
                    'constraint1_id': 3,
                    'constraint1_name': 'Must achieve 99.99% uptime',
                    'constraint2_id': 8,
                    'constraint2_name': 'Budget limited to €100K',
                    'conflict_type': 'mutually_exclusive',
                    'severity': 'critical',
                    'explanation': 'Achieving 99.99% uptime requires redundancy costing >€500K, incompatible with €100K budget',
                    'resolution_options': [...]
                }
            ]
        """
        constraints = ConstraintElement.query.filter_by(
            architecture_id=architecture_id, status="active"
        ).all()

        active_constraints = [c for c in constraints if c.is_active]

        if len(active_constraints) < 2:
            return []

        prompt = self._build_conflict_detection_prompt(active_constraints)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            conflicts_data = json.loads(response)
            return conflicts_data.get("conflicts", [])

        except Exception as e:
            raise Exception(f"Conflict detection failed: {str(e)}")

    # ========================================================================
    # Feasibility & Trade-off Analysis
    # ========================================================================

    def analyze_feasibility(
        self, requirement_id: int, constraints: Optional[List[int]] = None
    ) -> Dict:
        """
        Comprehensive feasibility analysis for a requirement.

        Args:
            requirement_id: ID of the Requirement
            constraints: Optional constraint IDs to analyze against

        Returns:
            Dict with feasibility analysis:
            {
                'feasibility_score': 65,  # 0 - 100
                'feasibility_level': 'medium',  # high, medium, low, infeasible
                'critical_blockers': [...],  # Hard constraints violated
                'challenges': [...],  # Soft constraints violated
                'risks': [...],
                'recommended_actions': [...]
            }
        """
        validation = self.validate_requirement_against_constraints(requirement_id, constraints)

        feasibility_score = validation.get("feasibility_score", 100)

        # Determine feasibility level
        if feasibility_score >= 80:
            level = "high"
        elif feasibility_score >= 60:
            level = "medium"
        elif feasibility_score >= 40:
            level = "low"
        else:
            level = "infeasible"

        # Categorize violations
        critical_blockers = []
        challenges = []

        for violation in validation.get("violations", []):
            if violation.get("is_hard_constraint"):
                critical_blockers.append(violation)
            else:
                challenges.append(violation)

        return {
            "feasibility_score": feasibility_score,
            "feasibility_level": level,
            "is_feasible": validation.get("feasible", True),
            "critical_blockers": critical_blockers,
            "challenges": challenges,
            "warnings": validation.get("warnings", []),
            "recommended_actions": self._generate_feasibility_recommendations(
                level, critical_blockers, challenges
            ),
        }

    def recommend_tradeoffs(
        self, architecture_id: int, conflicting_constraints: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        Recommend trade-offs when constraints conflict.

        Args:
            architecture_id: ID of the ArchitectureModel
            conflicting_constraints: Optional IDs of specific conflicting constraints

        Returns:
            List of trade-off recommendations:
            [
                {
                    'scenario': 'Prioritize budget constraint',
                    'keep_constraints': [3, 5],
                    'relax_constraints': [8, 12],
                    'impact': 'Reduced performance, extended timeline',
                    'feasibility_gain': 35,  # % improvement
                    'recommendation': 'Recommended if budget is non-negotiable'
                }
            ]
        """
        if not conflicting_constraints:
            # Detect conflicts first
            conflicts = self.detect_constraint_conflicts(architecture_id)
            if not conflicts:
                return []

            # Extract constraint IDs from conflicts
            conflicting_constraint_ids = set()
            for conflict in conflicts:
                conflicting_constraint_ids.add(conflict.get("constraint1_id"))
                conflicting_constraint_ids.add(conflict.get("constraint2_id"))
            conflicting_constraints = list(conflicting_constraint_ids)

        constraints = ConstraintElement.query.filter(
            ConstraintElement.id.in_(conflicting_constraints)
        ).all()

        prompt = self._build_tradeoff_analysis_prompt(constraints)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            tradeoffs_data = json.loads(response)
            return tradeoffs_data.get("tradeoff_scenarios", [])

        except Exception as e:
            raise Exception(f"Trade-off analysis failed: {str(e)}")

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _create_constraint(self, constraint_info: Dict, architecture_id: int) -> ConstraintElement:
        """Create ConstraintElement with ArchiMate element."""
        # Create ArchiMate Constraint element
        constraint_element = ArchiMateElement(
            name=constraint_info["name"],
            type="Constraint",
            layer="motivation",
            description=constraint_info.get("description", ""),
            architecture_id=architecture_id,
        )
        db.session.add(constraint_element)
        db.session.flush()

        # Parse dates if provided
        effective_from = self._parse_date(constraint_info.get("effective_from"))
        effective_until = self._parse_date(constraint_info.get("effective_until"))

        # Create ConstraintElement instance
        constraint = ConstraintElement(
            name=constraint_info["name"],
            description=constraint_info.get("description", ""),
            archimate_element_id=constraint_element.id,
            constraint_type=constraint_info.get("type", "organizational"),
            is_hard_constraint=constraint_info.get("is_hard", True),
            constraint_value=constraint_info.get("value"),
            constraint_unit=constraint_info.get("unit"),
            violation_consequence=constraint_info.get("consequence"),
            effective_from=effective_from,
            effective_until=effective_until,
            status="active",
            architecture_id=architecture_id,
        )
        db.session.add(constraint)

        return constraint

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    def _generate_feasibility_recommendations(
        self, feasibility_level: str, critical_blockers: List[Dict], challenges: List[Dict]
    ) -> List[str]:
        """Generate recommendations based on feasibility analysis."""
        recommendations = []

        if feasibility_level == "infeasible":
            recommendations.append(
                "CRITICAL: Requirement is not feasible given current constraints"
            )
            if critical_blockers:
                recommendations.append("Address these hard constraint violations first:")
                for blocker in critical_blockers[:3]:
                    recommendations.append(
                        f"  - {blocker.get('constraint_name')}: {blocker.get('violation')}"
                    )

        elif feasibility_level == "low":
            recommendations.append("Requirement faces significant challenges")
            recommendations.append(
                "Consider: Request constraint waivers or reduce requirement scope"
            )

        elif feasibility_level == "medium":
            recommendations.append("Requirement is achievable with adjustments")
            if challenges:
                recommendations.append("Address these soft constraint issues:")
                for challenge in challenges[:2]:
                    recommendations.append(f"  - {challenge.get('constraint_name')}")

        else:  # high
            recommendations.append("Requirement is highly feasible")
            if challenges:
                recommendations.append("Minor optimizations possible by addressing:")
                for challenge in challenges[:1]:
                    recommendations.append(f"  - {challenge.get('constraint_name')}")

        return recommendations

    # ========================================================================
    # Prompt Building Methods
    # ========================================================================

    def _build_constraint_extraction_prompt(self, business_context: str) -> str:
        """Build constraint extraction prompt."""
        return f"""You are an enterprise architect extracting business/technical constraints from context.

Business Context:
{business_context}

Extract all CONSTRAINTS (limitations/restrictions that constrain solution options).

Constraint Types:
1. **Budget**: Financial limitations (CapEx, OpEx, licensing)
2. **Timeline**: Temporal deadlines (launch dates, milestones)
3. **Regulatory**: Legal/compliance mandates (GDPR, HIPAA, data residency)
4. **Technical**: Technology restrictions (platforms, versions, compatibility)
5. **Resource**: People/skills availability (team size, expertise)
6. **Platform**: Infrastructure limitations (on-premises, cloud provider)
7. **Vendor**: Vendor lock-in, existing contracts, enterprise agreements
8. **Organizational**: Internal policies, governance, approval processes

For each constraint:
- name: Concise constraint name
- description: Full constraint description
- type: budget | timeline | regulatory | technical | resource | platform | vendor | organizational
- is_hard: true (cannot violate) | false (negotiable)
- value: Specific constraint value (e.g., "€5M", "Q2 2026", "EU only")
- unit: Unit of measurement (EUR, months, region, etc.)
- consequence: What happens if violated
- effective_from: When constraint starts (YYYY-MM-DD)
- effective_until: When constraint expires (YYYY-MM-DD) or null

Return JSON:
{{
  "constraints": [
    {{
      "name": "Project Budget Cap",
      "description": "Maximum budget allocation for digital transformation initiative is €5M",
      "type": "budget",
      "is_hard": true,
      "value": "€5M",
      "unit": "EUR",
      "consequence": "Project funding will not be approved if budget exceeded",
      "effective_from": "2025 - 01 - 01",
      "effective_until": "2026 - 12 - 31"
    }},
    {{
      "name": "Q2 2026 Launch Deadline",
      "description": "Solution must launch by end of Q2 2026 to meet market window",
      "type": "timeline",
      "is_hard": true,
      "value": "2026 - 06 - 30",
      "unit": "date",
      "consequence": "Miss market opportunity, competitor advantage",
      "effective_from": null,
      "effective_until": "2026 - 06 - 30"
    }},
    {{
      "name": "GDPR Data Residency",
      "description": "All EU customer data must remain within EU geographic boundaries",
      "type": "regulatory",
      "is_hard": true,
      "value": "EU only",
      "unit": "region",
      "consequence": "GDPR violation, fines up to 4% revenue, legal liability",
      "effective_from": "2018 - 05 - 25",
      "effective_until": null
    }}
  ]
}}

Only extract constraints explicitly stated or strongly implied in the context.
"""

    def _build_regulatory_constraint_prompt(
        self, business_context: str, regulations: Optional[List[str]]
    ) -> str:
        """Build regulatory-specific constraint prompt."""
        regs = regulations or ["GDPR", "HIPAA", "PCI-DSS", "SOX", "CCPA"]
        regs_str = ", ".join(regs)

        return f"""Extract regulatory/compliance CONSTRAINTS from business context.

Context:
{business_context}

Focus on: {regs_str}

For each regulatory constraint:
- name, description, type='regulatory'
- is_hard=true (regulatory constraints are non-negotiable)
- value: What the regulation requires
- consequence: Penalties for non-compliance

Return JSON with regulatory constraints only.
"""

    def _build_constraint_validation_prompt(
        self, requirement: Requirement, constraints: List[ConstraintElement]
    ) -> str:
        """Build constraint validation prompt."""
        constraints_list = "\n".join(
            [
                f"ID: {c.id}, Name: {c.name}, Type: {c.constraint_type}, Hard: {c.is_hard_constraint}, Value: {c.constraint_value}, Consequence: {c.violation_consequence}"
                for c in constraints
            ]
        )

        return f"""You are an enterprise architect validating requirement feasibility against constraints.

Requirement:
Title: {requirement.title}
Description: {requirement.description}
Type: {requirement.type}
Category: {requirement.category}

Active Constraints:
{constraints_list}

Validate if the requirement violates any constraints.

For violations:
- Identify which constraint is violated
- Explain how it's violated
- severity: critical (hard constraint), medium (soft constraint)
- Recommend resolution options

Return JSON:
{{
  "feasible": false,
  "violations": [
    {{
      "constraint_id": 3,
      "constraint_name": "Project Budget Cap €5M",
      "constraint_type": "budget",
      "is_hard_constraint": true,
      "violation": "Requirement's estimated implementation cost of €8M exceeds €5M budget cap",
      "severity": "critical",
      "resolution_options": [
        "Reduce requirement scope to fit €5M budget",
        "Seek CFO approval for budget increase to €8M",
        "Phase implementation over 2 years (€4M per year)",
        "Explore lower-cost implementation alternatives"
      ]
    }}
  ],
  "warnings": [
    {{
      "constraint_id": 7,
      "message": "Requirement timeline is tight given Q2 2026 deadline. Monitor closely."
    }}
  ],
  "feasibility_score": 40
}}

Score: 100 = fully feasible, 0 = completely blocked.
"""

    def _build_conflict_detection_prompt(self, constraints: List[ConstraintElement]) -> str:
        """Build conflict detection prompt."""
        constraints_list = "\n".join(
            [
                f"ID: {c.id}, Name: {c.name}, Type: {c.constraint_type}, Value: {c.constraint_value}, Hard: {c.is_hard_constraint}"
                for c in constraints
            ]
        )

        return f"""Detect conflicting constraints (mutually exclusive or impossible to satisfy together).

Constraints:
{constraints_list}

Identify conflicts where:
- Mutually exclusive: Satisfying both is impossible
- Practically incompatible: Very difficult to satisfy both simultaneously
- Insufficient resources: Combined requirements exceed available resources

Return JSON:
{{
  "conflicts": [
    {{
      "constraint1_id": 5,
      "constraint1_name": "Achieve 99.99% uptime (4 nines)",
      "constraint2_id": 12,
      "constraint2_name": "Budget limited to €100K",
      "conflict_type": "mutually_exclusive",
      "severity": "critical",
      "explanation": "Achieving 99.99% uptime requires multi-region redundancy, load balancing, and failover systems costing minimum €500K. This is incompatible with €100K budget constraint.",
      "resolution_options": [
        "Reduce uptime requirement to 99.9% (achievable with €100K)",
        "Increase budget to €500K to support 99.99% target",
        "Accept higher risk and attempt 99.99% with limited redundancy"
      ]
    }}
  ]
}}

Return empty array if no conflicts.
"""

    def _build_tradeoff_analysis_prompt(self, constraints: List[ConstraintElement]) -> str:
        """Build trade-off analysis prompt."""
        constraints_list = "\n".join(
            [
                f"ID: {c.id}, Name: {c.name}, Type: {c.constraint_type}, Hard: {c.is_hard_constraint}"
                for c in constraints
            ]
        )

        return f"""Recommend trade-off scenarios for conflicting constraints.

Conflicting Constraints:
{constraints_list}

Generate 3 - 4 trade-off scenarios showing different prioritization choices.

Return JSON:
{{
  "tradeoff_scenarios": [
    {{
      "scenario": "Prioritize Budget Constraint",
      "description": "Accept budget limitation, adjust other requirements accordingly",
      "keep_constraints": [12],
      "relax_constraints": [5, 8],
      "impact": "Reduced performance (99.9% vs 99.99%), extended timeline (+3 months)",
      "feasibility_gain": 45,
      "pros": ["Stays within budget", "No additional funding needed"],
      "cons": ["Lower performance", "Longer delivery time"],
      "recommendation": "Recommended if budget is absolutely non-negotiable"
    }},
    {{
      "scenario": "Prioritize Performance Constraint",
      "description": "Achieve 99.99% uptime target, seek budget increase",
      "keep_constraints": [5],
      "relax_constraints": [12],
      "impact": "Budget increase to €500K required",
      "feasibility_gain": 60,
      "pros": ["Meets performance targets", "Best customer experience"],
      "cons": ["Requires budget approval", "Higher ongoing costs"],
      "recommendation": "Recommended if performance is critical differentiator"
    }}
  ]
}}
"""
