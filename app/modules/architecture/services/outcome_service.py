"""
AI-Powered Outcome Management Service for ArchiMate 3.2 Motivation Layer

This service provides comprehensive Outcome modeling and measurement:
- KPI definition and tracking
- Goal realization measurement
- Progress monitoring and alerting
- Outcome achievement analysis
- Baseline vs target tracking

ArchiMate 3.2 Compliance:
- Outcome is a Motivation Layer element
- Outcome realizes Goals
- Outcome is measured through concrete metrics
- Outcome can be assessed via Assessment elements
"""

import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app import db
from app.models import ArchiMateElement, ArchiMateRelationship, ArchitectureModel, Outcome
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class OutcomeService:
    """
    AI-powered service for ArchiMate 3.2 Outcome element management.

    Capabilities:
    - Generate outcomes from goals
    - Define KPI metrics with baselines and targets
    - Track outcome realization progress
    - Alert on at-risk outcomes
    - Analyze achievement trends
    """

    def __init__(self):
        self.llm_service = LLMService()

    # ========================================================================
    # Outcome Generation Methods
    # ========================================================================

    def generate_outcomes_from_goal(self, goal_id: int, num_outcomes: int = 3) -> List[Outcome]:
        """
        Generate measurable outcomes that prove goal achievement.

        Args:
            goal_id: ID of the Goal ArchiMateElement
            num_outcomes: Number of outcomes to generate (default 3)

        Returns:
            List of Outcome instances with KPI definitions

        Example:
            >>> # Goal: "Improve customer satisfaction"
            >>> outcomes = service.generate_outcomes_from_goal(goal_id=5)
            >>> # Returns:
            >>> # - NPS score >60 (currently 45)
            >>> # - CSAT rating >4.5/5 (currently 3.8)
            >>> # - Customer retention >95% (currently 88%)
        """
        goal = db.session.get(ArchiMateElement, goal_id)
        if not goal or goal.type != "Goal":
            raise ValueError(f"Goal {goal_id} not found or not a Goal element")

        prompt = self._build_outcome_generation_prompt(goal, num_outcomes)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            outcomes_data = json.loads(response)

            outcomes = []
            for outcome_info in outcomes_data.get("outcomes", []):
                outcome = self._create_outcome(outcome_info, goal_id, goal.architecture_id)
                outcomes.append(outcome)

            db.session.commit()
            return outcomes

        except Exception as e:
            db.session.rollback()
            raise Exception(f"Outcome generation failed: {str(e)}")

    # ========================================================================
    # KPI Definition Methods
    # ========================================================================

    def define_kpi_metrics(self, outcome_id: int, business_context: Optional[str] = None) -> Dict:
        """
        AI-powered KPI definition for an outcome.

        Generates:
        - Primary metric name
        - Measurement method
        - Data source
        - Collection frequency
        - Target and baseline values
        - Success thresholds

        Args:
            outcome_id: ID of the Outcome
            business_context: Optional context for better KPI definition

        Returns:
            Dict with KPI definition:
            {
                'kpi_metric': 'Net Promoter Score',
                'measurement_method': 'Customer survey after each transaction',
                'data_source': 'CRM system survey module',
                'calculation': '% Promoters (9 - 10) - % Detractors (0 - 6)',
                'frequency': 'monthly',
                'target_value': '65',
                'baseline_value': '45',
                'success_threshold': '>60',
                'warning_threshold': '<55'
            }
        """
        outcome = db.session.get(Outcome, outcome_id)
        if not outcome:
            raise ValueError(f"Outcome {outcome_id} not found")

        prompt = self._build_kpi_definition_prompt(outcome, business_context)

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            kpi_definition = json.loads(response)

            # Update outcome with KPI details
            outcome.kpi_metric = kpi_definition.get("kpi_metric")
            outcome.target_value = kpi_definition.get("target_value")
            outcome.current_value = kpi_definition.get("baseline_value")
            outcome.baseline_value = kpi_definition.get("baseline_value")
            outcome.measurement_unit = kpi_definition.get("measurement_unit")
            outcome.measurement_frequency = kpi_definition.get("frequency", "monthly")

            # Store additional metadata in archimate_element properties
            if outcome.archimate_element:
                props = (
                    json.loads(outcome.archimate_element.properties)
                    if outcome.archimate_element.properties
                    else {}
                )
                props["kpi_definition"] = kpi_definition
                props["defined_at"] = datetime.utcnow().isoformat()
                outcome.archimate_element.properties = json.dumps(props)

            db.session.commit()
            return kpi_definition

        except Exception as e:
            db.session.rollback()
            raise Exception(f"KPI definition failed: {str(e)}")

    # ========================================================================
    # Outcome Tracking Methods
    # ========================================================================

    def track_outcome_realization(
        self, outcome_id: int, actual_value: str, measurement_date: Optional[date] = None
    ) -> Dict:
        """
        Track outcome realization progress.

        Updates current value and analyzes status:
        - on_track: Progressing toward target
        - at_risk: Behind schedule or insufficient progress
        - achieved: Target reached
        - failed: Unlikely to achieve target

        Args:
            outcome_id: ID of the Outcome
            actual_value: Current measured value
            measurement_date: When measurement was taken (defaults to today)

        Returns:
            Dict with tracking analysis:
            {
                'previous_value': '45',
                'current_value': '52',
                'target_value': '65',
                'progress_percentage': 35,  # (52 - 45)/(65 - 45) = 35%
                'status': 'on_track',
                'trend': 'improving',
                'days_remaining': 450,
                'projected_completion': '2026 - 11 - 15',
                'recommendation': 'Continue current initiatives'
            }
        """
        outcome = db.session.get(Outcome, outcome_id)
        if not outcome:
            raise ValueError(f"Outcome {outcome_id} not found")

        measurement_date = measurement_date or date.today()
        previous_value = outcome.current_value

        # Update current value
        outcome.current_value = actual_value

        # Calculate achievement percentage
        achievement_pct = outcome.achievement_percentage

        # Determine status
        status = self._determine_outcome_status(outcome, achievement_pct, measurement_date)
        outcome.realization_status = status

        # If achieved, set achieved_date
        if status == "achieved" and not outcome.achieved_date:
            outcome.achieved_date = measurement_date

        db.session.commit()

        # Generate tracking analysis
        analysis = {
            "previous_value": previous_value,
            "current_value": actual_value,
            "target_value": outcome.target_value,
            "baseline_value": outcome.baseline_value,
            "progress_percentage": achievement_pct,
            "status": status,
            "measurement_date": measurement_date.isoformat(),
            "target_date": outcome.target_date.isoformat() if outcome.target_date else None,
        }

        # Calculate trend and projection
        if previous_value and achievement_pct is not None:
            analysis["trend"] = "improving" if achievement_pct > 0 else "declining"

            if outcome.target_date:
                days_remaining = (outcome.target_date - measurement_date).days
                analysis["days_remaining"] = days_remaining

                # Simple linear projection
                if achievement_pct > 0 and days_remaining > 0:
                    # Estimate days to 100% achievement at current rate
                    analysis["projection"] = self._project_achievement(
                        achievement_pct, days_remaining
                    )

        return analysis

    def get_at_risk_outcomes(
        self, architecture_id: int, risk_threshold: int = 30
    ) -> List[Tuple[Outcome, Dict]]:
        """
        Identify outcomes at risk of not being achieved.

        Args:
            architecture_id: ID of the ArchitectureModel
            risk_threshold: Days before target date to flag as at-risk

        Returns:
            List of (Outcome, risk_analysis) tuples
        """
        outcomes = (
            Outcome.query.filter_by(architecture_id=architecture_id)
            .filter(Outcome.realization_status.in_(["not_started", "in_progress", "at_risk"]))
            .all()
        )

        at_risk = []
        today = date.today()

        for outcome in outcomes:
            if not outcome.target_date:
                continue

            days_remaining = (outcome.target_date - today).days

            # Flag as at-risk if:
            # 1. Less than risk_threshold days remaining
            # 2. Achievement percentage < 50% with < 60 days remaining
            # 3. Achievement percentage < 25% with < 90 days remaining
            achievement = outcome.achievement_percentage or 0

            is_at_risk = False
            risk_reason = []

            if days_remaining < 0:
                is_at_risk = True
                risk_reason.append(f"Overdue by {abs(days_remaining)} days")
            elif days_remaining < risk_threshold:
                is_at_risk = True
                risk_reason.append(f"Only {days_remaining} days remaining")
            elif days_remaining < 60 and achievement < 50:
                is_at_risk = True
                risk_reason.append(f"Only {achievement}% achieved with {days_remaining} days left")
            elif days_remaining < 90 and achievement < 25:
                is_at_risk = True
                risk_reason.append(f"Only {achievement}% achieved with {days_remaining} days left")

            if is_at_risk:
                risk_analysis = {
                    "days_remaining": days_remaining,
                    "achievement_percentage": achievement,
                    "risk_level": "critical" if days_remaining < 0 or achievement < 25 else "high",
                    "risk_reasons": risk_reason,
                    "target_date": outcome.target_date.isoformat(),
                    "current_status": outcome.realization_status,
                }
                at_risk.append((outcome, risk_analysis))

        return at_risk

    # ========================================================================
    # Outcome Analysis Methods
    # ========================================================================

    def analyze_outcome_achievement(
        self, architecture_id: int, time_period: Optional[str] = None
    ) -> Dict:
        """
        Analyze outcome achievement across architecture.

        Args:
            architecture_id: ID of the ArchitectureModel
            time_period: Optional filter ('current_quarter', 'current_year', 'all')

        Returns:
            Dict with achievement statistics:
            {
                'total_outcomes': 15,
                'achieved': 5,
                'on_track': 7,
                'at_risk': 2,
                'failed': 1,
                'overall_achievement_rate': 33,  # 5/15
                'average_progress': 58,
                'outcomes_by_goal': {...}
            }
        """
        outcomes = Outcome.query.filter_by(architecture_id=architecture_id).all()

        if not outcomes:
            return {"total_outcomes": 0}

        # Apply time filter
        if time_period:
            outcomes = self._filter_by_time_period(outcomes, time_period)

        # Calculate statistics
        total = len(outcomes)
        status_counts = {
            "achieved": 0,
            "on_track": 0,
            "at_risk": 0,
            "in_progress": 0,
            "not_started": 0,
            "failed": 0,
        }

        total_progress = 0
        outcomes_with_progress = 0

        for outcome in outcomes:
            status = outcome.realization_status or "not_started"
            status_counts[status] = status_counts.get(status, 0) + 1

            achievement = outcome.achievement_percentage
            if achievement is not None:
                total_progress += achievement
                outcomes_with_progress += 1

        avg_progress = total_progress / outcomes_with_progress if outcomes_with_progress > 0 else 0

        analysis = {
            "total_outcomes": total,
            "achieved": status_counts["achieved"],
            "on_track": status_counts.get("on_track", 0),
            "at_risk": status_counts.get("at_risk", 0),
            "in_progress": status_counts.get("in_progress", 0),
            "not_started": status_counts.get("not_started", 0),
            "failed": status_counts.get("failed", 0),
            "overall_achievement_rate": round((status_counts["achieved"] / total) * 100, 1),
            "average_progress": round(avg_progress, 1),
            "time_period": time_period or "all",
        }

        return analysis

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _create_outcome(self, outcome_info: Dict, goal_id: int, architecture_id: int) -> Outcome:
        """Create Outcome instance with ArchiMate element."""
        # Create ArchiMate Outcome element
        outcome_element = ArchiMateElement(
            name=outcome_info["name"],
            type="Outcome",
            layer="motivation",
            description=outcome_info.get("description", ""),
            architecture_id=architecture_id,
        )
        db.session.add(outcome_element)
        db.session.flush()

        # Create Outcome instance
        outcome = Outcome(
            name=outcome_info["name"],
            description=outcome_info.get("description", ""),
            archimate_element_id=outcome_element.id,
            goal_id=goal_id,
            kpi_metric=outcome_info.get("kpi_metric"),
            target_value=outcome_info.get("target_value"),
            current_value=outcome_info.get("baseline_value"),
            baseline_value=outcome_info.get("baseline_value"),
            measurement_unit=outcome_info.get("measurement_unit"),
            measurement_frequency=outcome_info.get("measurement_frequency", "monthly"),
            target_date=self._parse_date(outcome_info.get("target_date")),
            realization_status="not_started",
            architecture_id=architecture_id,
        )
        db.session.add(outcome)

        # Create realization relationship
        goal_element = db.session.get(ArchiMateElement, goal_id)
        if goal_element:
            relationship = ArchiMateRelationship(
                type="realization",
                source_id=outcome_element.id,
                target_id=goal_id,
                architecture_id=architecture_id,
            )
            db.session.add(relationship)

        return outcome

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    def _determine_outcome_status(
        self, outcome: Outcome, achievement_pct: Optional[float], measurement_date: date
    ) -> str:
        """Determine outcome realization status."""
        if achievement_pct is None:
            return "not_started"

        if achievement_pct >= 100:
            return "achieved"

        if not outcome.target_date:
            return "in_progress" if achievement_pct > 0 else "not_started"

        days_remaining = (outcome.target_date - measurement_date).days

        if days_remaining < 0:
            return "failed" if achievement_pct < 90 else "achieved"

        # Risk-based status determination
        if days_remaining < 30 and achievement_pct < 75:
            return "at_risk"
        elif days_remaining < 60 and achievement_pct < 50:
            return "at_risk"
        elif days_remaining < 90 and achievement_pct < 25:
            return "at_risk"
        elif achievement_pct > 0:
            return "in_progress"
        else:
            return "not_started"

    def _project_achievement(self, current_achievement_pct: float, days_remaining: int) -> Dict:
        """Project when outcome will be achieved."""
        # Simple linear projection
        if current_achievement_pct <= 0:
            return {"projected_date": None, "likelihood": "unlikely"}

        # Estimate days to 100% at current rate
        # This is simplified - real projection would use historical trend
        days_to_complete = (100 / current_achievement_pct) * days_remaining

        projected_date = date.today() + timedelta(days=days_to_complete)

        likelihood = "likely" if days_to_complete <= days_remaining else "unlikely"

        return {
            "projected_date": projected_date.isoformat(),
            "days_to_complete": int(days_to_complete),
            "likelihood": likelihood,
        }

    def _filter_by_time_period(self, outcomes: List[Outcome], time_period: str) -> List[Outcome]:
        """Filter outcomes by time period."""
        today = date.today()

        if time_period == "current_quarter":
            # Get current quarter
            quarter_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
            filtered = [o for o in outcomes if o.target_date and o.target_date >= quarter_start]
        elif time_period == "current_year":
            year_start = date(today.year, 1, 1)
            filtered = [o for o in outcomes if o.target_date and o.target_date >= year_start]
        else:
            filtered = outcomes

        return filtered

    # ========================================================================
    # Prompt Building Methods
    # ========================================================================

    def _build_outcome_generation_prompt(self, goal: ArchiMateElement, num_outcomes: int) -> str:
        """Build outcome generation prompt."""
        return f"""You are a performance management and KPI expert.

Generate {num_outcomes} measurable OUTCOMES that prove achievement of this goal:

Goal: {goal.name}
Description: {goal.description}

For each outcome:
1. Identify a specific measurable end result
2. Define the KPI/metric that proves it
3. Specify realistic target and baseline values
4. Determine measurement frequency
5. Set target achievement date

Return JSON:
{{
  "outcomes": [
    {{
      "name": "Net Promoter Score Achievement",
      "description": "NPS reaches target of 65+, demonstrating strong customer advocacy and satisfaction",
      "kpi_metric": "Net Promoter Score (NPS)",
      "target_value": "65",
      "baseline_value": "45",
      "measurement_unit": "score",
      "measurement_frequency": "monthly",
      "target_date": "2026 - 12 - 31"
    }},
    {{
      "name": "Customer Retention Target",
      "description": "Annual customer retention rate exceeds 95%",
      "kpi_metric": "Annual Customer Retention Rate",
      "target_value": "95",
      "baseline_value": "88",
      "measurement_unit": "percentage",
      "measurement_frequency": "monthly",
      "target_date": "2026 - 12 - 31"
    }}
  ]
}}

Ensure outcomes are:
- MEASURABLE: Clear numeric targets
- ACHIEVABLE: Realistic improvement from baseline
- TIME-BOUND: Specific target dates
- ALIGNED: Directly prove goal achievement
"""

    def _build_kpi_definition_prompt(
        self, outcome: Outcome, business_context: Optional[str]
    ) -> str:
        """Build KPI definition prompt."""
        context_section = f"\n\nBusiness Context:\n{business_context}" if business_context else ""

        return f"""You are a KPI and metrics expert. Define how to measure this outcome.

Outcome: {outcome.name}
Description: {outcome.description}
Current Metric: {outcome.kpi_metric or 'Not defined'}
{context_section}

Provide complete KPI definition:

1. **KPI Metric Name**: Clear, standard metric name
2. **Measurement Method**: How to collect the data
3. **Data Source**: Where the data comes from
4. **Calculation Formula**: How to calculate the metric
5. **Measurement Frequency**: How often to measure
6. **Target Value**: What success looks like
7. **Baseline Value**: Starting point
8. **Success Threshold**: When is outcome achieved?
9. **Warning Threshold**: When to raise alerts?

Return JSON:
{{
  "kpi_metric": "Net Promoter Score",
  "measurement_method": "Customer survey: 'How likely are you to recommend us?' (0 - 10 scale)",
  "data_source": "CRM system survey module, post-transaction surveys",
  "calculation": "% Promoters (score 9 - 10) minus % Detractors (score 0 - 6)",
  "frequency": "monthly",
  "measurement_unit": "score",
  "target_value": "65",
  "baseline_value": "45",
  "success_threshold": "≥60 sustained for 3 months",
  "warning_threshold": "<55 indicates risk",
  "data_quality_requirements": "Minimum 200 responses per month for statistical significance"
}}
"""
