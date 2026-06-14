"""
AI-Powered Goal Management Service for ArchiMate 3.2 Motivation Layer

This service provides comprehensive Goal modeling with SMART validation:
- Goal extraction from strategic documents
- SMART validation (Specific, Measurable, Achievable, Relevant, Time-bound)
- Goal decomposition (strategic → tactical → operational)
- Goal-to-Outcome mapping
- Goal-to-Capability alignment
- Goal hierarchy management

ArchiMate 3.2 Compliance:
- Goal is a Motivation Layer element
- Represents a high-level statement of intent or desired state
- Can be realized by Outcomes
- Can be influenced by Drivers
- Can constrain Requirements
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
    Outcome,
)
from app.models.implementation_migration import WorkPackage
from app.models.motivation import Goal
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class GoalService:
    """
    AI-powered service for ArchiMate 3.2 Goal element management.

    Capabilities:
    - Extract goals from strategic plans
    - Validate goals against SMART criteria
    - Decompose strategic goals into tactical objectives
    - Map goals to measurable outcomes
    - Align goals with business capabilities
    """

    def __init__(self):
        self.llm_service = LLMService()

    # ========================================================================
    # Goal Extraction Methods
    # ========================================================================

    def extract_goals_from_strategy(
        self, strategic_plan: str, architecture_id: int, auto_validate_smart: bool = True
    ) -> List[ArchiMateElement]:
        """
        Extract strategic goals from planning documents using AI.

        Args:
            strategic_plan: Strategic planning document text
            architecture_id: ID of the ArchitectureModel
            auto_validate_smart: If True, automatically validates and corrects non-SMART goals

        Returns:
            List of Goal ArchiMateElements

        Example:
            >>> plan = "We aim to increase customer satisfaction and reduce costs by 20% over next 2 years"
            >>> goals = service.extract_goals_from_strategy(plan, arch_id=1)
            >>> # Returns 2 goals: customer satisfaction (vague → corrected), cost reduction (SMART)
        """
        prompt = self._build_goal_extraction_prompt(strategic_plan, auto_validate_smart)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            goals_data = json.loads(response)

            if not isinstance(goals_data, dict) or "goals" not in goals_data:
                raise ValueError("Invalid response format from LLM")

            goals = []
            for goal_info in goals_data["goals"]:
                goal_element = self._create_goal_element(goal_info, architecture_id)
                goals.append(goal_element)

            db.session.commit()
            return goals

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Goal extraction failed: {str(e)}")

    # ========================================================================
    # SMART Validation Methods
    # ========================================================================

    def validate_smart_goal(self, goal_text: str, strategic_context: Optional[str] = None) -> Dict:
        """
        Validate if a goal meets SMART criteria.

        SMART Criteria:
        - S (Specific): Clear, unambiguous target state
        - M (Measurable): Quantifiable metrics/indicators
        - A (Achievable): Realistic given constraints
        - R (Relevant): Aligned with strategic direction
        - T (Time-bound): Clear deadline or timeframe

        Args:
            goal_text: The goal statement to validate
            strategic_context: Optional organizational strategy for Relevance assessment

        Returns:
            Dict with validation results:
            {
                'is_smart': True/False,
                'specific': {'valid': True, 'score': 8, 'feedback': '...'},
                'measurable': {'valid': True, 'score': 9, 'feedback': '...'},
                'achievable': {'valid': True, 'score': 7, 'feedback': '...'},
                'relevant': {'valid': True, 'score': 8, 'feedback': '...'},
                'time_bound': {'valid': True, 'score': 10, 'feedback': '...'},
                'overall_score': 84,  # Average of individual scores
                'improved_goal': 'Improve NPS from 45 to 60 by Q4 2026'  # If not SMART
            }
        """
        prompt = self._build_smart_validation_prompt(goal_text, strategic_context)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            validation = json.loads(response)
            return validation

        except Exception as e:
            raise Exception(f"SMART validation failed: {str(e)}")

    def validate_and_improve_goal(
        self, goal_id: int, strategic_context: Optional[str] = None
    ) -> Dict:
        """
        Validate existing goal and improve it if not SMART.

        Args:
            goal_id: ID of the Goal ArchiMateElement
            strategic_context: Optional strategic context for validation

        Returns:
            Dict with validation results and improved goal if needed
        """
        goal = db.session.get(ArchiMateElement, goal_id)
        if not goal or goal.type != "Goal":
            raise ValueError(f"Goal {goal_id} not found or not a Goal element")

        goal_text = goal.description or goal.name

        validation = self.validate_smart_goal(goal_text, strategic_context)

        # If not SMART and improved version provided, update goal
        if not validation.get("is_smart") and validation.get("improved_goal"):
            props = json.loads(goal.properties) if goal.properties else {}
            props["original_goal"] = goal_text
            props["smart_validation"] = validation
            props["validated_at"] = datetime.utcnow().isoformat()

            goal.description = validation["improved_goal"]
            goal.properties = json.dumps(props)

            db.session.commit()

        return validation

    # ========================================================================
    # Goal Decomposition Methods
    # ========================================================================

    def decompose_goal(self, goal_id: int, decomposition_levels: int = 2) -> List[ArchiMateElement]:
        """
        Decompose a strategic goal into tactical/operational sub-goals.

        Goal Hierarchy:
        - Level 0: Strategic Goal (enterprise-wide, 3 - 5 years)
        - Level 1: Tactical Objectives (business unit, 1 - 2 years)
        - Level 2: Operational Goals (team/process, quarterly/annual)

        Args:
            goal_id: ID of the parent Goal to decompose
            decomposition_levels: How many levels deep to decompose (1 - 3)

        Returns:
            List of sub-goal ArchiMateElements with aggregation relationships

        Example:
            >>> # Strategic: "Achieve €50M ARR by 2028"
            >>> sub_goals = service.decompose_goal(goal_id=1, levels=2)
            >>> # Tactical: "Increase customer base 40%", "Improve retention to 95%", "Launch 2 new products"
            >>> # Operational: "Acquire 1000 customers/quarter", "Reduce churn to <1%/month", etc.
        """
        parent_goal = db.session.get(ArchiMateElement, goal_id)
        if not parent_goal or parent_goal.type != "Goal":
            raise ValueError(f"Goal {goal_id} not found")

        prompt = self._build_goal_decomposition_prompt(parent_goal, decomposition_levels)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            decomposition_data = json.loads(response)

            sub_goals = []
            for level_data in decomposition_data.get("decomposition", []):
                for goal_info in level_data.get("goals", []):
                    sub_goal = self._create_goal_element(goal_info, parent_goal.architecture_id)
                    sub_goals.append(sub_goal)

                    # Create aggregation relationship (parent aggregates sub-goals)
                    self._create_relationship(
                        parent_goal.id, sub_goal.id, "aggregation", parent_goal.architecture_id
                    )

            db.session.commit()
            return sub_goals

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Goal decomposition failed: {str(e)}")

    # ========================================================================
    # Goal-Outcome Mapping Methods
    # ========================================================================

    def map_goals_to_outcomes(self, goal_id: int, generate_kpis: bool = True) -> List[Outcome]:
        """
        Generate measurable outcomes that prove goal achievement.

        An Outcome is the end result that realizes the Goal.

        Args:
            goal_id: ID of the Goal ArchiMateElement
            generate_kpis: If True, generates KPI definitions for each outcome

        Returns:
            List of Outcome instances with KPI metrics

        Example:
            >>> # Goal: "Improve customer satisfaction"
            >>> outcomes = service.map_goals_to_outcomes(goal_id=5)
            >>> # Outcomes:
            >>> # - NPS score >60 (currently 45)
            >>> # - CSAT rating >4.5/5 (currently 3.8)
            >>> # - Customer retention >95% (currently 88%)
        """
        goal = db.session.get(ArchiMateElement, goal_id)
        if not goal or goal.type != "Goal":
            raise ValueError(f"Goal {goal_id} not found")

        prompt = self._build_outcome_generation_prompt(goal, generate_kpis)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            outcomes_data = json.loads(response)

            outcomes = []
            for outcome_info in outcomes_data.get("outcomes", []):
                # Create ArchiMate Outcome element
                outcome_element = ArchiMateElement(
                    name=outcome_info["name"],
                    type="Outcome",
                    layer="motivation",
                    description=outcome_info.get("description", ""),
                    architecture_id=goal.architecture_id,
                )
                db.session.add(outcome_element)
                db.session.flush()  # Get ID

                # Create Outcome model instance
                outcome = Outcome(
                    name=outcome_info["name"],
                    description=outcome_info.get("description", ""),
                    archimate_element_id=outcome_element.id,
                    goal_id=goal.id,
                    kpi_metric=outcome_info.get("kpi_metric"),
                    target_value=outcome_info.get("target_value"),
                    current_value=outcome_info.get("baseline_value"),
                    baseline_value=outcome_info.get("baseline_value"),
                    measurement_unit=outcome_info.get("measurement_unit"),
                    measurement_frequency=outcome_info.get("measurement_frequency", "monthly"),
                    target_date=self._parse_date(outcome_info.get("target_date")),
                    realization_status="not_started",
                    architecture_id=goal.architecture_id,
                )
                db.session.add(outcome)
                outcomes.append(outcome)

                # Create realization relationship (Outcome realizes Goal)
                self._create_relationship(
                    outcome_element.id, goal.id, "realization", goal.architecture_id
                )

            db.session.commit()
            return outcomes

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Outcome generation failed: {str(e)}")

    # ========================================================================
    # Goal-Capability Alignment Methods
    # ========================================================================

    def align_goals_to_capabilities(
        self, goal_id: int, capability_ids: Optional[List[int]] = None
    ) -> List[Tuple[BusinessCapability, Dict]]:
        """
        Align goal with business capabilities required to achieve it.

        Identifies:
        - Which capabilities must mature to achieve goal
        - Current vs required maturity level
        - Gap analysis for each capability
        - Investment priorities

        Args:
            goal_id: ID of the Goal ArchiMateElement
            capability_ids: Optional list of capability IDs to assess (if None, uses AI to identify)

        Returns:
            List of tuples: (BusinessCapability, alignment_data)
            alignment_data = {
                'relevance': 'high/medium/low',
                'current_maturity': 2,
                'required_maturity': 4,
                'maturity_gap': 2,
                'investment_priority': 'critical/high/medium/low',
                'rationale': '...'
            }
        """
        goal = db.session.get(ArchiMateElement, goal_id)
        if not goal or goal.type != "Goal":
            raise ValueError(f"Goal {goal_id} not found")

        if not capability_ids:
            # Use AI to identify relevant capabilities
            capability_ids = self._identify_relevant_capabilities(goal)

        capabilities = BusinessCapability.query.filter(
            BusinessCapability.id.in_(capability_ids)
        ).all()

        prompt = self._build_capability_alignment_prompt(goal, capabilities)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            alignment_data = json.loads(response)

            results = []
            for align in alignment_data.get("alignments", []):
                cap_id = align["capability_id"]
                capability = next((c for c in capabilities if c.id == cap_id), None)
                if capability:
                    results.append((capability, align))

            return results

        except Exception as e:
            raise Exception(f"Capability alignment failed: {str(e)}")

    # ========================================================================
    # Goal-to-WorkPackage Methods
    # ========================================================================

    def create_work_packages_from_goal(
        self, goal_id: int, work_package_descriptions: Optional[List[str]] = None
    ) -> List:
        """
        Generate WorkPackages from a Goal to enable execution planning.

        WorkPackages are the execution units that realize Goals.

        Args:
            goal_id: ID of the Goal model (not ArchiMateElement)
            work_package_descriptions: Optional list of work package descriptions.
                                      If None, uses AI to generate from goal.

        Returns:
            List of WorkPackage instances

        Example:
            >>> goal = Goal.query.get(1)
            >>> work_packages = service.create_work_packages_from_goal(goal.id)
            >>> # Returns: [WorkPackage("Q1 Planning"), WorkPackage("Q2 Implementation"), ...]
        """
        from app.models.implementation_migration import WorkPackage
        from app.models.motivation import Goal

        goal = db.session.get(Goal, goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")

        if not work_package_descriptions:
            # Use AI to generate work packages from goal
            prompt = self._build_work_package_generation_prompt(goal)

            try:
                response = self.llm_service.generate_from_prompt(prompt)
                work_packages_data = json.loads(response)
                work_package_descriptions = [
                    wp.get("description", wp.get("name", ""))
                    for wp in work_packages_data.get("work_packages", [])
                ]
            except Exception as e:
                raise Exception(f"Work package generation failed: {str(e)}")

        work_packages = []
        for i, wp_desc in enumerate(work_package_descriptions):
            work_package = WorkPackage(
                name=f"{goal.name} - Work Package {i + 1}",
                description=wp_desc,
                goal_id=goal.id,
                architecture_id=goal.architecture_id,
                status="planned",
                priority=goal.priority if hasattr(goal, "priority") else "medium",
                start_date=goal.start_date,
                target_date=goal.target_date,
                sequence_order=i + 1,
            )
            db.session.add(work_package)
            work_packages.append(work_package)

        db.session.commit()
        return work_packages

    def get_goal_progress_from_work_packages(self, goal_id: int) -> Dict:
        """
        Calculate goal progress based on WorkPackage completion.

        Args:
            goal_id: ID of the Goal model

        Returns:
            Dict with progress metrics:
            {
                'total_work_packages': 5,
                'completed_work_packages': 2,
                'in_progress_work_packages': 2,
                'planned_work_packages': 1,
                'completion_percentage': 40,
                'estimated_completion_date': '2024 - 12 - 31',
                'on_track': True/False
            }
        """
        goal = db.session.get(Goal, goal_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")

        work_packages = WorkPackage.query.filter_by(goal_id=goal_id).all()

        total = len(work_packages)
        completed = sum(1 for wp in work_packages if wp.status == "completed")
        in_progress = sum(1 for wp in work_packages if wp.status in ["in_progress", "active"])
        planned = sum(1 for wp in work_packages if wp.status == "planned")

        completion_percentage = (completed / total * 100) if total > 0 else 0

        # Estimate completion date from latest work package target date
        latest_date = None
        for wp in work_packages:
            if wp.target_date:
                if not latest_date or wp.target_date > latest_date:
                    latest_date = wp.target_date

        # Check if on track (completion % matches time elapsed %)
        on_track = True
        if goal.start_date and goal.target_date and latest_date:
            total_days = (goal.target_date - goal.start_date).days
            elapsed_days = (date.today() - goal.start_date).days
            if total_days > 0:
                time_elapsed_pct = (elapsed_days / total_days) * 100
                on_track = completion_percentage >= time_elapsed_pct - 10  # 10% tolerance

        return {
            "total_work_packages": total,
            "completed_work_packages": completed,
            "in_progress_work_packages": in_progress,
            "planned_work_packages": planned,
            "completion_percentage": round(completion_percentage, 1),
            "estimated_completion_date": latest_date.isoformat() if latest_date else None,
            "on_track": on_track,
        }

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _create_goal_element(self, goal_info: Dict, architecture_id: int) -> ArchiMateElement:
        """Create ArchiMateElement for a goal."""
        properties = {
            "smart_validated": goal_info.get("is_smart", False),
            "smart_scores": goal_info.get("smart_scores", {}),
            "goal_level": goal_info.get("level", "strategic"),  # strategic, tactical, operational
            "timeframe": goal_info.get("timeframe"),
            "metrics": goal_info.get("metrics", []),
            "created_at": datetime.utcnow().isoformat(),
        }

        goal = ArchiMateElement(
            name=goal_info["name"],
            type="Goal",
            layer="motivation",
            description=goal_info.get("description", ""),
            documentation=goal_info.get("details", ""),
            properties=json.dumps(properties),
            priority=goal_info.get("priority", "medium"),
            status="proposed",
            architecture_id=architecture_id,
        )

        db.session.add(goal)
        return goal

    def _create_relationship(
        self, source_id: int, target_id: int, rel_type: str, architecture_id: int
    ) -> ArchiMateRelationship:
        """Create ArchiMate relationship."""
        relationship = ArchiMateRelationship(
            type=rel_type, source_id=source_id, target_id=target_id, architecture_id=architecture_id
        )
        db.session.add(relationship)
        return relationship

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    def _identify_relevant_capabilities(self, goal: ArchiMateElement) -> List[int]:
        """Use AI to identify capabilities relevant to goal."""
        all_caps = BusinessCapability.query.filter_by(architecture_id=goal.architecture_id).all()

        if not all_caps:
            return []

        prompt = f"""Identify which business capabilities are most relevant to achieving this goal:

Goal: {goal.name}
Description: {goal.description}

Available Capabilities:
{json.dumps([{'id': c.id, 'name': c.name, 'description': c.description} for c in all_caps[:50]], indent=2)}

Return JSON with IDs of relevant capabilities:
{{"capability_ids": [1, 5, 12]}}
"""

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            data = json.loads(response)
            return data.get("capability_ids", [])
        except Exception:
            logger.debug("Failed to identify relevant capabilities", exc_info=True)
            return []

    # ========================================================================
    # Prompt Building Methods
    # ========================================================================

    def _build_goal_extraction_prompt(self, strategic_plan: str, auto_validate_smart: bool) -> str:
        """Build goal extraction prompt."""
        smart_instruction = (
            """
For each goal, validate if it's SMART:
- If NOT SMART, provide an improved SMART version
- Mark is_smart: true/false
- Provide SMART scores for each criterion (0 - 10)
"""
            if auto_validate_smart
            else ""
        )

        return f"""You are a strategic planning expert and enterprise architect.

Extract all strategic goals from this document:

{strategic_plan}

{smart_instruction}

For each goal, provide:
- name: Concise goal statement (10 - 15 words max)
- description: Detailed description (SMART if validated)
- level: 'strategic', 'tactical', or 'operational'
- timeframe: Time period (e.g., "2024 - 2026", "Q1 - Q4 2025")
- priority: 'critical', 'high', 'medium', 'low'
- metrics: List of measurable success indicators
- is_smart: true/false
- smart_scores: {{specific: 8, measurable: 9, achievable: 7, relevant: 9, time_bound: 10}}

Return JSON:
{{
  "goals": [
    {{
      "name": "Achieve €50M ARR by end of 2028",
      "description": "Grow annual recurring revenue from current €25M to €50M (100% increase) by December 31, 2028 through customer acquisition, retention, and expansion",
      "level": "strategic",
      "timeframe": "2024 - 2028",
      "priority": "critical",
      "metrics": ["ARR", "Customer count", "Average contract value", "Retention rate"],
      "is_smart": true,
      "smart_scores": {{"specific": 10, "measurable": 10, "achievable": 8, "relevant": 9, "time_bound": 10}}
    }},
    {{
      "name": "Improve customer satisfaction",
      "description": "Increase Net Promoter Score (NPS) from current 45 to 65+ by Q4 2026",
      "level": "strategic",
      "timeframe": "2024 - 2026",
      "priority": "high",
      "metrics": ["NPS", "CSAT", "Customer retention rate"],
      "is_smart": true,
      "smart_scores": {{"specific": 9, "measurable": 10, "achievable": 8, "relevant": 9, "time_bound": 10}},
      "original_vague": "Improve customer satisfaction"
    }}
  ]
}}

Extract only goals explicitly stated in the document.
"""

    def _build_smart_validation_prompt(
        self, goal_text: str, strategic_context: Optional[str]
    ) -> str:
        """Build SMART validation prompt."""
        context_section = (
            f"""
Strategic Context:
{strategic_context}

Use this context to evaluate Relevance.
"""
            if strategic_context
            else ""
        )

        return f"""You are a strategic planning expert. Evaluate if this goal meets SMART criteria.

Goal: {goal_text}

{context_section}

Evaluate each SMART criterion:

**S - Specific** (Score 0 - 10):
- Does it clearly state WHAT will be achieved?
- Is the target state unambiguous?
- Score: 10 = Crystal clear, 5 = Somewhat vague, 0 = Completely unclear

**M - Measurable** (Score 0 - 10):
- Can progress be quantified?
- Are metrics/KPIs identified?
- Is current baseline and target specified?
- Score: 10 = Fully quantified with metrics, 5 = Some metrics, 0 = No way to measure

**A - Achievable** (Score 0 - 10):
- Is this realistic given typical organizational constraints?
- Is the timeframe reasonable for the target?
- Score: 10 = Definitely achievable, 5 = Challenging but possible, 0 = Impossible

**R - Relevant** (Score 0 - 10):
- Does this align with strategic direction?
- Is this important to the business?
- Score: 10 = Critical strategic priority, 5 = Somewhat relevant, 0 = Irrelevant

**T - Time-bound** (Score 0 - 10):
- Is there a clear deadline?
- Is the timeframe specific enough?
- Score: 10 = Exact date, 5 = Vague timeframe, 0 = No deadline

Return JSON:
{{
  "is_smart": false,
  "specific": {{
    "valid": false,
    "score": 4,
    "feedback": "Goal lacks clarity on what specific outcome is expected. Doesn't specify what aspect of customer satisfaction or by how much."
  }},
  "measurable": {{
    "valid": false,
    "score": 2,
    "feedback": "No metrics defined. How will satisfaction be measured? NPS? CSAT? Retention?"
  }},
  "achievable": {{
    "valid": true,
    "score": 7,
    "feedback": "Improving satisfaction is generally achievable, but cannot assess fully without specific target"
  }},
  "relevant": {{
    "valid": true,
    "score": 9,
    "feedback": "Customer satisfaction is always relevant to business success"
  }},
  "time_bound": {{
    "valid": false,
    "score": 0,
    "feedback": "No deadline specified. When should this be achieved?"
  }},
  "overall_score": 44,
  "improved_goal": "Increase Net Promoter Score (NPS) from current baseline of 45 to 65+ by Q4 2026"
}}
"""

    def _build_goal_decomposition_prompt(
        self, parent_goal: ArchiMateElement, decomposition_levels: int
    ) -> str:
        """Build goal decomposition prompt."""
        return f"""You are a strategic planning expert. Decompose this high-level goal into specific sub-goals.

Parent Goal:
Name: {parent_goal.name}
Description: {parent_goal.description}

Decompose into {decomposition_levels} levels:
- Level 1: Tactical objectives (supporting the strategic goal)
- Level 2: Operational goals (specific actions/initiatives)

Each sub-goal should:
1. Be SMART (specific, measurable, achievable, relevant, time-bound)
2. Contribute to achieving the parent goal
3. Be independently executable
4. Have clear ownership potential

Return JSON:
{{
  "decomposition": [
    {{
      "level": 1,
      "description": "Tactical objectives",
      "goals": [
        {{
          "name": "Increase customer acquisition by 40%",
          "description": "Acquire 2000 new customers (from 5000 to 7000) by end of 2026",
          "level": "tactical",
          "timeframe": "2024 - 2026",
          "priority": "critical",
          "metrics": ["New customer count", "CAC", "Conversion rate"],
          "contribution": "40% of ARR growth comes from new customers"
        }},
        {{
          "name": "Improve customer retention to 95%",
          "description": "Increase annual retention rate from 88% to 95% by Q4 2026",
          "level": "tactical",
          "timeframe": "2024 - 2026",
          "priority": "high",
          "metrics": ["Annual retention rate", "Churn rate", "Customer lifetime value"],
          "contribution": "Higher retention compounds revenue growth"
        }}
      ]
    }},
    {{
      "level": 2,
      "description": "Operational goals",
      "goals": [
        {{
          "name": "Launch customer success program by Q2 2025",
          "description": "Implement proactive customer success program covering all accounts >€50K ARR by Q2 2025",
          "level": "operational",
          "timeframe": "Q1 - Q2 2025",
          "priority": "high",
          "metrics": ["CS program coverage", "QBR completion rate", "Expansion revenue"],
          "contribution": "Customer success drives retention and expansion"
        }}
      ]
    }}
  ]
}}
"""

    def _build_outcome_generation_prompt(self, goal: ArchiMateElement, generate_kpis: bool) -> str:
        """Build outcome generation prompt."""
        kpi_instruction = (
            """
For each outcome, define the KPI:
- kpi_metric: Name of the metric
- target_value: Specific target to achieve
- baseline_value: Current/starting value
- measurement_unit: Unit of measurement
- measurement_frequency: How often to measure
"""
            if generate_kpis
            else ""
        )

        return f"""You are a performance management and KPI expert.

For this goal, identify measurable OUTCOMES that prove achievement:

Goal: {goal.name}
Description: {goal.description}

An Outcome is an end result that can be measured. For each outcome:
1. Identify a specific measurable result
2. Define the KPI/metric that proves it
3. Specify target and baseline values
4. Describe how to measure it

{kpi_instruction}

Return JSON:
{{
  "outcomes": [
    {{
      "name": "Net Promoter Score Achievement",
      "description": "NPS reaches target of 65+, demonstrating strong customer advocacy",
      "kpi_metric": "Net Promoter Score (NPS)",
      "target_value": "65",
      "baseline_value": "45",
      "measurement_unit": "score",
      "measurement_frequency": "monthly",
      "target_date": "2026 - 12 - 31"
    }},
    {{
      "name": "Customer Satisfaction Rating",
      "description": "CSAT rating exceeds 4.5/5.0 across all touchpoints",
      "kpi_metric": "Customer Satisfaction Score (CSAT)",
      "target_value": "4.5",
      "baseline_value": "3.8",
      "measurement_unit": "rating",
      "measurement_frequency": "monthly",
      "target_date": "2026 - 12 - 31"
    }}
  ]
}}
"""

    def _build_work_package_generation_prompt(self, goal) -> str:
        """Build work package generation prompt from goal."""
        return f"""You are a project planning expert. Generate WORK PACKAGES to achieve this goal.

Goal: {goal.name}
Description: {goal.description}
Target Date: {goal.target_date or 'Not specified'}
Goal Type: {goal.goal_type or 'strategic'}

A Work Package is a discrete unit of work with defined deliverables. Break down the goal into:
1. Logical phases or milestones
2. Specific activities needed
3. Dependencies between work packages
4. Realistic timeframes

Each work package should:
- Be independently executable
- Have clear deliverables
- Have a defined timeframe
- Contribute directly to goal achievement

Return JSON:
{{
  "work_packages": [
    {{
      "name": "Phase 1: Planning and Design",
      "description": "Complete detailed planning, architecture design, and resource allocation",
      "duration_weeks": 8,
      "dependencies": [],
      "deliverables": ["Architecture Design Document", "Resource Plan", "Risk Assessment"]
    }},
    {{
      "name": "Phase 2: Implementation",
      "description": "Execute the implementation according to the plan",
      "duration_weeks": 16,
      "dependencies": ["Phase 1: Planning and Design"],
      "deliverables": ["Implementation Complete", "Test Results", "Documentation"]
    }}
  ]
}}
"""

    def _build_capability_alignment_prompt(
        self, goal: ArchiMateElement, capabilities: List[BusinessCapability]
    ) -> str:
        """Build capability alignment prompt."""
        cap_list = "\n".join(
            [
                f"ID: {c.id}, Name: {c.name}, Current Maturity: {c.current_maturity_level or 'unknown'}"
                for c in capabilities
            ]
        )

        return f"""You are an enterprise architect analyzing goal-capability alignment.

Goal: {goal.name}
Description: {goal.description}

Capabilities:
{cap_list}

For each capability, assess:
1. **Relevance**: How important is this capability to achieving the goal?
   - high: Critical, goal cannot be achieved without maturing this capability
   - medium: Important, contributes significantly
   - low: Minor contribution

2. **Required Maturity**: What CMM level (1 - 5) is needed?
   - Level 1: Initial (ad-hoc)
   - Level 2: Managed (documented processes)
   - Level 3: Defined (standardized)
   - Level 4: Quantitatively Managed (measured)
   - Level 5: Optimizing (continuous improvement)

3. **Investment Priority**: Based on maturity gap and relevance
   - critical: Large gap + high relevance
   - high: Medium gap + high relevance, or large gap + medium relevance
   - medium: Small gap + high relevance, or medium gap + medium relevance
   - low: Small gap + medium/low relevance

Return JSON:
{{
  "alignments": [
    {{
      "capability_id": 1,
      "relevance": "high",
      "current_maturity": 2,
      "required_maturity": 4,
      "maturity_gap": 2,
      "investment_priority": "critical",
      "rationale": "Customer success capability currently ad-hoc (Level 2). Need standardized, measured processes (Level 4) to achieve 95% retention target. This is critical path to goal."
    }}
  ]
}}
"""
