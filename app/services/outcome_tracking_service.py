"""
Outcome Tracking Service

Service for managing solution benefits realization tracking:
- Create outcomes from AI recommendations
- Record and track measurements
- Calculate variances and realization scores
- Generate benefits reports

Integrates with:
- SolutionOutcome, SolutionOutcomeMeasurement, SolutionBenefitRealization models
- Solution and SolutionAnalysisSession for context
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models.solution_outcomes import (
    OutcomeType,
    RealizationStatus,
    SolutionOutcome,
    SolutionOutcomeMeasurement,
    TrackingStatus,
)
from app.models.solution_sad_models import SolutionBenefitRealization

logger = logging.getLogger(__name__)


class OutcomeTrackingService:
    """
    Service for managing solution outcome tracking and benefits realization.

    Provides comprehensive capabilities:
    - Outcome creation from AI recommendations
    - Measurement recording and tracking
    - Variance calculation and analysis
    - Benefits realization reporting
    - Prediction accuracy analysis
    """

    # Default measurement frequency in days
    DEFAULT_MEASUREMENT_FREQUENCY = 30

    # Outcome type mapping from recommendation fields
    RECOMMENDATION_OUTCOME_MAPPING = {
        "cost_savings": OutcomeType.COST,
        "cost_reduction": OutcomeType.COST,
        "cost_avoidance": OutcomeType.COST,
        "timeline_reduction": OutcomeType.TIMELINE,
        "time_to_market": OutcomeType.TIMELINE,
        "delivery_improvement": OutcomeType.TIMELINE,
        "quality_improvement": OutcomeType.QUALITY,
        "defect_reduction": OutcomeType.QUALITY,
        "reliability_improvement": OutcomeType.QUALITY,
        "new_capability": OutcomeType.CAPABILITY,
        "capability_enhancement": OutcomeType.CAPABILITY,
        "risk_reduction": OutcomeType.RISK,
        "compliance_improvement": OutcomeType.RISK,
        "revenue_increase": OutcomeType.BENEFIT,
        "efficiency_gain": OutcomeType.BENEFIT,
        "customer_satisfaction": OutcomeType.BENEFIT,
    }

    # =========================================================================
    # OUTCOME CREATION
    # =========================================================================

    def create_outcomes_from_recommendation(
        self,
        solution_id: int,
        recommendation: dict,
        session_id: int = None,
        created_by_id: int = None,
    ) -> List[SolutionOutcome]:
        """
        Create outcome tracking records from a solution recommendation.

        Parses the recommendation dict to extract predicted outcomes
        and creates tracking records for each.

        Args:
            solution_id: ID of the solution to track
            recommendation: Dict containing recommendation data with expected outcomes
            session_id: Optional session ID for traceability
            created_by_id: User ID who created the outcomes

        Returns:
            List of created SolutionOutcome records
        """
        created_outcomes = []

        # Extract outcomes from recommendation structure
        expected_outcomes = recommendation.get("expected_outcomes", [])
        if not expected_outcomes:
            # Try alternative structures
            expected_outcomes = recommendation.get("benefits", [])

        # Also check for direct financial estimates
        if recommendation.get("estimated_cost_min") or recommendation.get("estimated_cost_max"):
            cost_outcome = {
                "type": "cost",
                "name": "Implementation Cost",
                "description": "Total implementation cost for the solution",
                "predicted_value": recommendation.get("estimated_cost_max")
                or recommendation.get("estimated_cost_min"),
                "unit": recommendation.get("cost_currency", "USD"),
                "confidence": recommendation.get("confidence", 0.8),
            }
            expected_outcomes.append(cost_outcome)

        # Extract timeline if present
        if recommendation.get("timeline_months"):
            timeline_outcome = {
                "type": "timeline",
                "name": "Implementation Timeline",
                "description": "Time to implement the solution",
                "predicted_value": recommendation.get("timeline_months"),
                "unit": "months",
                "confidence": recommendation.get("confidence", 0.8),
            }
            expected_outcomes.append(timeline_outcome)

        # Create outcome records
        for outcome_data in expected_outcomes:
            outcome = self._create_outcome_from_dict(
                solution_id=solution_id,
                session_id=session_id,
                outcome_data=outcome_data,
                created_by_id=created_by_id,
            )
            if outcome:
                created_outcomes.append(outcome)

        db.session.commit()
        logger.info(f"Created {len(created_outcomes)} outcomes for solution {solution_id}")
        return created_outcomes

    def _create_outcome_from_dict(
        self,
        solution_id: int,
        session_id: int,
        outcome_data: dict,
        created_by_id: int,
    ) -> Optional[SolutionOutcome]:
        """Create a single outcome from a dict."""
        # Determine outcome type
        outcome_type_str = outcome_data.get("type", "").lower()
        outcome_type = self.RECOMMENDATION_OUTCOME_MAPPING.get(
            outcome_type_str, OutcomeType.BENEFIT
        )

        # Handle enum value if passed directly
        if outcome_type_str in [e.value for e in OutcomeType]:
            outcome_type = OutcomeType(outcome_type_str)

        # Parse predicted value
        predicted_value = outcome_data.get("predicted_value") or outcome_data.get("value")
        if predicted_value is not None:
            try:
                predicted_value = Decimal(str(predicted_value))
            except (ValueError, TypeError):
                predicted_value = None

        # Parse predicted date
        predicted_date = None
        date_str = outcome_data.get("predicted_date") or outcome_data.get("target_date")
        if date_str:
            if isinstance(date_str, date):
                predicted_date = date_str
            elif isinstance(date_str, str):
                try:
                    predicted_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
                except ValueError:
                    pass

        # Set default next measurement date
        next_measurement = date.today() + timedelta(days=self.DEFAULT_MEASUREMENT_FREQUENCY)

        outcome = SolutionOutcome(
            solution_id=solution_id,
            session_id=session_id,
            outcome_type=outcome_type,
            name=outcome_data.get("name", f"{outcome_type.value.title()} Outcome"),
            description=outcome_data.get("description"),
            predicted_value=predicted_value,
            predicted_unit=outcome_data.get("unit") or outcome_data.get("predicted_unit"),
            predicted_date=predicted_date,
            prediction_confidence=outcome_data.get("confidence")
            or outcome_data.get("prediction_confidence"),
            tracking_status=TrackingStatus.NOT_STARTED,
            next_measurement_date=next_measurement,
            created_by_id=created_by_id,
        )

        db.session.add(outcome)
        return outcome

    def create_outcome(
        self,
        solution_id: int,
        outcome_type: OutcomeType,
        name: str,
        description: str = None,
        predicted_value: float = None,
        predicted_unit: str = None,
        predicted_date: date = None,
        prediction_confidence: float = None,
        session_id: int = None,
        created_by_id: int = None,
    ) -> SolutionOutcome:
        """
        Create a single outcome tracking record.

        Args:
            solution_id: Solution ID
            outcome_type: Type of outcome
            name: Outcome name
            description: Optional description
            predicted_value: Expected value
            predicted_unit: Unit of measurement
            predicted_date: Expected achievement date
            prediction_confidence: Confidence level (0 - 1)
            session_id: Optional session ID
            created_by_id: User ID

        Returns:
            Created SolutionOutcome
        """
        next_measurement = date.today() + timedelta(days=self.DEFAULT_MEASUREMENT_FREQUENCY)

        outcome = SolutionOutcome(
            solution_id=solution_id,
            session_id=session_id,
            outcome_type=outcome_type,
            name=name,
            description=description,
            predicted_value=Decimal(str(predicted_value)) if predicted_value else None,
            predicted_unit=predicted_unit,
            predicted_date=predicted_date,
            prediction_confidence=prediction_confidence,
            tracking_status=TrackingStatus.NOT_STARTED,
            next_measurement_date=next_measurement,
            created_by_id=created_by_id,
        )

        db.session.add(outcome)
        db.session.commit()

        logger.info(f"Created outcome {outcome.id}: {name}")
        return outcome

    # =========================================================================
    # MEASUREMENT RECORDING
    # =========================================================================

    def record_measurement(
        self,
        outcome_id: int,
        value: float,
        user_id: int,
        notes: str = None,
        evidence_links: List[str] = None,
        measured_at: datetime = None,
    ) -> SolutionOutcomeMeasurement:
        """
        Record a new measurement for an outcome.

        Updates the outcome's actual value and recalculates variance.

        Args:
            outcome_id: Outcome to measure
            value: Measured value
            user_id: User recording the measurement
            notes: Optional notes
            evidence_links: Optional list of evidence URLs
            measured_at: Measurement timestamp (defaults to now)

        Returns:
            Created SolutionOutcomeMeasurement
        """
        outcome = db.session.get(SolutionOutcome, outcome_id)
        if not outcome:
            raise ValueError(f"Outcome {outcome_id} not found")

        measurement = SolutionOutcomeMeasurement(
            outcome_id=outcome_id,
            measured_value=Decimal(str(value)),
            measured_at=measured_at or datetime.utcnow(),
            measured_by_id=user_id,
            notes=notes,
            evidence_links=evidence_links,
        )

        db.session.add(measurement)

        # Update outcome with latest measurement
        outcome.actual_value = Decimal(str(value))
        outcome.actual_date = measurement.measured_at.date()
        outcome.last_measured_at = measurement.measured_at
        outcome.tracking_status = TrackingStatus.IN_PROGRESS

        # Calculate variance and update status
        outcome.calculate_variance()
        outcome.update_status_from_variance()

        # Set next measurement date
        outcome.next_measurement_date = date.today() + timedelta(
            days=self.DEFAULT_MEASUREMENT_FREQUENCY
        )

        db.session.commit()

        logger.info(f"Recorded measurement {measurement.id} for outcome {outcome_id}: {value}")
        return measurement

    def get_measurement_history(
        self,
        outcome_id: int,
        limit: int = None,
    ) -> List[SolutionOutcomeMeasurement]:
        """Get measurement history for an outcome."""
        query = SolutionOutcomeMeasurement.query.filter(
            SolutionOutcomeMeasurement.outcome_id == outcome_id
        ).order_by(SolutionOutcomeMeasurement.measured_at.desc())

        if limit:
            query = query.limit(limit)

        return query.all()

    # =========================================================================
    # VARIANCE CALCULATION
    # =========================================================================

    def calculate_variance(self, outcome_id: int) -> dict:
        """
        Calculate variance between predicted and actual for an outcome.

        Returns detailed variance analysis.

        Args:
            outcome_id: Outcome ID

        Returns:
            Dict with variance details
        """
        outcome = db.session.get(SolutionOutcome, outcome_id)
        if not outcome:
            raise ValueError(f"Outcome {outcome_id} not found")

        # Calculate variance
        variance_pct = outcome.calculate_variance()
        outcome.update_status_from_variance()
        db.session.commit()

        # Determine variance interpretation
        is_favorable = False
        if variance_pct is not None:
            is_lower_better = outcome.outcome_type in [
                OutcomeType.COST,
                OutcomeType.TIMELINE,
                OutcomeType.RISK,
            ]
            is_favorable = (variance_pct < 0) if is_lower_better else (variance_pct > 0)

        return {
            "outcome_id": outcome_id,
            "outcome_name": outcome.name,
            "outcome_type": outcome.outcome_type.value,
            "predicted_value": float(outcome.predicted_value) if outcome.predicted_value else None,
            "actual_value": float(outcome.actual_value) if outcome.actual_value else None,
            "variance_percentage": variance_pct,
            "variance_absolute": float(outcome.actual_value - outcome.predicted_value)
            if outcome.actual_value and outcome.predicted_value
            else None,
            "is_favorable": is_favorable,
            "tracking_status": outcome.tracking_status.value,
            "prediction_confidence": outcome.prediction_confidence,
        }

    # =========================================================================
    # SOLUTION REALIZATION SUMMARY
    # =========================================================================

    def get_solution_realization_summary(self, solution_id: int) -> dict:
        """
        Get aggregate realization status for a solution.

        Provides a comprehensive view of all outcomes and their status.

        Args:
            solution_id: Solution ID

        Returns:
            Dict with realization summary
        """
        outcomes = SolutionOutcome.query.filter(SolutionOutcome.solution_id == solution_id).all()

        if not outcomes:
            return {
                "solution_id": solution_id,
                "total_outcomes": 0,
                "status": "no_outcomes",
                "message": "No outcomes defined for this solution",
            }

        # Count by status
        status_counts = {}
        for status in TrackingStatus:
            status_counts[status.value] = 0
        for outcome in outcomes:
            if outcome.tracking_status:
                status_counts[outcome.tracking_status.value] += 1

        # Count by type
        type_counts = {}
        for outcome_type in OutcomeType:
            type_counts[outcome_type.value] = 0
        for outcome in outcomes:
            if outcome.outcome_type:
                type_counts[outcome.outcome_type.value] += 1

        # Calculate overall metrics
        outcomes_with_variance = [o for o in outcomes if o.variance_percentage is not None]
        avg_variance = None
        if outcomes_with_variance:
            avg_variance = sum(o.variance_percentage for o in outcomes_with_variance) / len(
                outcomes_with_variance
            )

        # Determine overall status
        achieved_count = status_counts.get(TrackingStatus.ACHIEVED.value, 0) + status_counts.get(
            TrackingStatus.EXCEEDED.value, 0
        )
        missed_count = status_counts.get(TrackingStatus.MISSED.value, 0)
        total = len(outcomes)

        if achieved_count == total:
            overall_status = "fully_realized"
        elif achieved_count > total * 0.8:
            overall_status = "on_track"
        elif missed_count > total * 0.3:
            overall_status = "off_track"
        else:
            overall_status = "in_progress"

        return {
            "solution_id": solution_id,
            "total_outcomes": total,
            "status_breakdown": status_counts,
            "type_breakdown": type_counts,
            "average_variance_percentage": avg_variance,
            "achieved_count": achieved_count,
            "missed_count": missed_count,
            "overall_status": overall_status,
            "outcomes": [o.to_dict() for o in outcomes],
        }

    # =========================================================================
    # BENEFITS REPORTING
    # =========================================================================

    def generate_benefits_report(
        self,
        solution_id: int,
        period_start: date,
        period_end: date,
        created_by_id: int,
    ) -> SolutionBenefitRealization:
        """
        Generate a benefits realization report for a period.

        Aggregates outcome data into a comprehensive benefits report.

        Args:
            solution_id: Solution ID
            period_start: Report period start
            period_end: Report period end
            created_by_id: User generating the report

        Returns:
            Created SolutionBenefitRealization
        """
        # Check for existing report
        existing = SolutionBenefitRealization.query.filter(
            SolutionBenefitRealization.solution_id == solution_id,
            SolutionBenefitRealization.reporting_period_start == period_start,
            SolutionBenefitRealization.reporting_period_end == period_end,
        ).first()

        if existing:
            # Update existing report
            report = existing
        else:
            report = SolutionBenefitRealization(
                solution_id=solution_id,
                reporting_period_start=period_start,
                reporting_period_end=period_end,
                created_by_id=created_by_id,
            )
            db.session.add(report)

        # Get outcomes for this solution
        outcomes = SolutionOutcome.query.filter(SolutionOutcome.solution_id == solution_id).all()

        # Aggregate by type
        cost_outcomes = [o for o in outcomes if o.outcome_type == OutcomeType.COST]
        benefit_outcomes = [o for o in outcomes if o.outcome_type == OutcomeType.BENEFIT]
        quality_outcomes = [o for o in outcomes if o.outcome_type == OutcomeType.QUALITY]

        # Calculate financial metrics
        if cost_outcomes:
            planned_costs = [o.predicted_value for o in cost_outcomes if o.predicted_value]
            actual_costs = [o.actual_value for o in cost_outcomes if o.actual_value]
            if planned_costs:
                report.planned_cost_savings = sum(planned_costs)
            if actual_costs:
                report.actual_cost_savings = sum(actual_costs)

        # Calculate efficiency gains (from benefit outcomes)
        efficiency_outcomes = [
            o for o in benefit_outcomes if "efficiency" in (o.name or "").lower()
        ]
        if efficiency_outcomes:
            planned_eff = [o.predicted_value for o in efficiency_outcomes if o.predicted_value]
            actual_eff = [o.actual_value for o in efficiency_outcomes if o.actual_value]
            if planned_eff:
                report.planned_efficiency_gain_percent = float(sum(planned_eff)) / len(planned_eff)
            if actual_eff:
                report.actual_efficiency_gain_percent = float(sum(actual_eff)) / len(actual_eff)

        # Calculate quality improvements
        if quality_outcomes:
            planned_quality = [o.predicted_value for o in quality_outcomes if o.predicted_value]
            actual_quality = [o.actual_value for o in quality_outcomes if o.actual_value]
            if planned_quality:
                report.planned_quality_improvement_percent = float(sum(planned_quality)) / len(
                    planned_quality
                )
            if actual_quality:
                report.actual_quality_improvement_percent = float(sum(actual_quality)) / len(
                    actual_quality
                )

        # Calculate realization score and status
        report.calculate_realization_score()
        report.update_status_from_score()

        # Generate executive summary
        report.executive_summary = self._generate_executive_summary(report, outcomes)

        db.session.commit()

        logger.info(f"Generated benefits report {report.id} for solution {solution_id}")
        return report

    def _generate_executive_summary(
        self,
        report: SolutionBenefitRealization,
        outcomes: List[SolutionOutcome],
    ) -> str:
        """Generate executive summary text for a benefits report."""
        achieved = len(
            [
                o
                for o in outcomes
                if o.tracking_status in [TrackingStatus.ACHIEVED, TrackingStatus.EXCEEDED]
            ]
        )
        total = len(outcomes)
        score = report.realization_score or 0

        summary_parts = [
            f"Benefits Realization Report for period {report.reporting_period_start} to {report.reporting_period_end}.",
            f"Overall realization score: {score:.1f}%.",
            f"Status: {report.status.value.replace('_', ' ').title()}.",
            f"{achieved} of {total} outcomes achieved or exceeded.",
        ]

        if report.actual_cost_savings and report.planned_cost_savings:
            cost_pct = float(report.actual_cost_savings / report.planned_cost_savings * 100)
            summary_parts.append(f"Cost savings at {cost_pct:.1f}% of target.")

        return " ".join(summary_parts)

    # =========================================================================
    # OUTCOMES REQUIRING MEASUREMENT
    # =========================================================================

    def get_outcomes_requiring_measurement(self, days_overdue: int = 7) -> List[SolutionOutcome]:
        """
        Find outcomes that need measurement updates.

        Returns outcomes where next_measurement_date has passed.

        Args:
            days_overdue: Number of days past due to include

        Returns:
            List of outcomes needing measurement
        """
        cutoff_date = date.today() - timedelta(days=days_overdue)

        return (
            SolutionOutcome.query.filter(
                SolutionOutcome.tracking_status.in_(
                    [
                        TrackingStatus.NOT_STARTED,
                        TrackingStatus.IN_PROGRESS,
                    ]
                ),
                or_(
                    SolutionOutcome.next_measurement_date <= date.today(),
                    SolutionOutcome.next_measurement_date.is_(None),
                ),
            )
            .order_by(SolutionOutcome.next_measurement_date.asc())
            .all()
        )

    def get_overdue_outcomes_by_solution(self, solution_id: int) -> List[SolutionOutcome]:
        """Get overdue outcomes for a specific solution."""
        return (
            SolutionOutcome.query.filter(
                SolutionOutcome.solution_id == solution_id,
                SolutionOutcome.tracking_status.in_(
                    [
                        TrackingStatus.NOT_STARTED,
                        TrackingStatus.IN_PROGRESS,
                    ]
                ),
                SolutionOutcome.next_measurement_date <= date.today(),
            )
            .order_by(SolutionOutcome.next_measurement_date.asc())
            .all()
        )

    # =========================================================================
    # PREDICTION ACCURACY ANALYSIS
    # =========================================================================

    def compare_prediction_accuracy(self, session_id: int) -> dict:
        """
        Analyze how accurate the AI predictions were for a session.

        Compares predicted vs actual values across all outcomes
        linked to a session.

        Args:
            session_id: Session ID to analyze

        Returns:
            Dict with prediction accuracy analysis
        """
        outcomes = SolutionOutcome.query.filter(SolutionOutcome.session_id == session_id).all()

        if not outcomes:
            return {
                "session_id": session_id,
                "total_outcomes": 0,
                "message": "No outcomes linked to this session",
            }

        # Analyze outcomes with both predicted and actual values
        measurable_outcomes = [
            o for o in outcomes if o.predicted_value is not None and o.actual_value is not None
        ]

        if not measurable_outcomes:
            return {
                "session_id": session_id,
                "total_outcomes": len(outcomes),
                "measurable_outcomes": 0,
                "message": "No outcomes with both predicted and actual values",
            }

        # Calculate accuracy metrics
        accuracy_by_type = {}
        for outcome_type in OutcomeType:
            type_outcomes = [o for o in measurable_outcomes if o.outcome_type == outcome_type]
            if type_outcomes:
                variances = [
                    abs(o.variance_percentage)
                    for o in type_outcomes
                    if o.variance_percentage is not None
                ]
                if variances:
                    accuracy_by_type[outcome_type.value] = {
                        "count": len(type_outcomes),
                        "avg_variance_pct": sum(variances) / len(variances),
                        "max_variance_pct": max(variances),
                        "min_variance_pct": min(variances),
                    }

        # Overall accuracy
        all_variances = [
            abs(o.variance_percentage)
            for o in measurable_outcomes
            if o.variance_percentage is not None
        ]
        overall_accuracy = (
            100 - (sum(all_variances) / len(all_variances)) if all_variances else None
        )

        # Confidence correlation
        outcomes_with_confidence = [
            o
            for o in measurable_outcomes
            if o.prediction_confidence is not None and o.variance_percentage is not None
        ]

        confidence_correlation = None
        if len(outcomes_with_confidence) >= 3:
            # Simple correlation: do high-confidence predictions have lower variance?
            high_conf = [o for o in outcomes_with_confidence if o.prediction_confidence >= 0.8]
            low_conf = [o for o in outcomes_with_confidence if o.prediction_confidence < 0.8]

            if high_conf and low_conf:
                high_conf_avg_var = sum(abs(o.variance_percentage) for o in high_conf) / len(
                    high_conf
                )
                low_conf_avg_var = sum(abs(o.variance_percentage) for o in low_conf) / len(low_conf)
                confidence_correlation = {
                    "high_confidence_avg_variance": high_conf_avg_var,
                    "low_confidence_avg_variance": low_conf_avg_var,
                    "correlation_valid": high_conf_avg_var < low_conf_avg_var,
                }

        return {
            "session_id": session_id,
            "total_outcomes": len(outcomes),
            "measurable_outcomes": len(measurable_outcomes),
            "overall_accuracy_score": overall_accuracy,
            "accuracy_by_type": accuracy_by_type,
            "confidence_correlation": confidence_correlation,
            "outcomes_achieved": len(
                [
                    o
                    for o in measurable_outcomes
                    if o.tracking_status in [TrackingStatus.ACHIEVED, TrackingStatus.EXCEEDED]
                ]
            ),
            "outcomes_missed": len(
                [o for o in measurable_outcomes if o.tracking_status == TrackingStatus.MISSED]
            ),
        }

    # =========================================================================
    # DASHBOARD AND REPORTING
    # =========================================================================

    def get_outcomes_dashboard(self) -> dict:
        """
        Get dashboard metrics for outcome tracking.

        Returns:
            Dict with dashboard data
        """
        # Overall counts
        total_outcomes = SolutionOutcome.query.count()
        outcomes_by_status = (
            db.session.query(SolutionOutcome.tracking_status, func.count(SolutionOutcome.id))
            .group_by(SolutionOutcome.tracking_status)
            .all()
        )

        outcomes_by_type = (
            db.session.query(SolutionOutcome.outcome_type, func.count(SolutionOutcome.id))
            .group_by(SolutionOutcome.outcome_type)
            .all()
        )

        # Recent measurements
        recent_measurements = (
            SolutionOutcomeMeasurement.query.order_by(SolutionOutcomeMeasurement.measured_at.desc())
            .limit(10)
            .all()
        )

        # Overdue outcomes
        overdue_outcomes = self.get_outcomes_requiring_measurement(days_overdue=0)

        # Benefit reports
        recent_reports = (
            SolutionBenefitRealization.query.order_by(SolutionBenefitRealization.created_at.desc())
            .limit(5)
            .all()
        )

        return {
            "total_outcomes": total_outcomes,
            "status_breakdown": {s.value if s else "unknown": c for s, c in outcomes_by_status},
            "type_breakdown": {t.value if t else "unknown": c for t, c in outcomes_by_type},
            "overdue_count": len(overdue_outcomes),
            "recent_measurements": [m.to_dict() for m in recent_measurements],
            "recent_reports": [r.to_dict() for r in recent_reports],
        }
