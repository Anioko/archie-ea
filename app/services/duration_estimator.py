"""
Predictive Duration Estimator for Implementation Planning

Simple statistical model for estimating work package duration based on historical data.
Uses median-based estimation with complexity multipliers.
"""

import logging
from statistics import median, mean, stdev
from typing import Dict, List, Optional, Any
from datetime import timedelta

from sqlalchemy import func

from app import db
from app.models.implementation_migration import WorkPackage as ImplementationWorkPackage

logger = logging.getLogger(__name__)


class DurationEstimator:
    """
    Predict work package duration based on historical actuals.
    """

    # Complexity multipliers based on capability depth
    COMPLEXITY_MULTIPLIERS = {
        "low": 0.8,
        "medium": 1.0,
        "high": 1.5,
        "critical": 2.5,
    }

    # Gap type difficulty factors (derived from historical variance)
    GAP_TYPE_FACTORS = {
        "capability": 1.0,
        "application": 1.2,
        "technology": 1.4,
        "process": 1.1,
        "data": 1.3,
        "integration": 1.5,
        "security": 1.3,
        "compliance": 1.2,
    }

    def __init__(self, min_samples: int = 3):
        self.min_samples = min_samples

    def estimate_duration(
        self,
        gap_type: Optional[str] = None,
        priority: str = "medium",
        complexity: str = "medium",
        has_dependencies: bool = False,
    ) -> Dict[str, Any]:
        """
        Estimate duration in hours and days for a work package.

        Args:
            gap_type: Type of gap (capability, application, etc.)
            priority: Work package priority
            complexity: low, medium, high, critical
            has_dependencies: Whether work package has dependencies

        Returns:
            Dict with estimated_hours, estimated_days, confidence, and factors
        """
        # Get historical data
        historical = self._get_historical_data(gap_type, priority)

        if len(historical) < self.min_samples:
            # Use fallback estimation based on priority
            return self._fallback_estimate(gap_type, priority, complexity, has_dependencies)

        # Calculate base estimate (median of actuals)
        actuals = [wp.actual_effort_hours for wp in historical if wp.actual_effort_hours]
        if not actuals:
            return self._fallback_estimate(gap_type, priority, complexity, has_dependencies)

        base_hours = median(actuals)

        # Apply modifiers
        complexity_mult = self.COMPLEXITY_MULTIPLIERS.get(complexity, 1.0)
        gap_factor = self.GAP_TYPE_FACTORS.get(gap_type, 1.0) if gap_type else 1.0
        dependency_factor = 1.2 if has_dependencies else 1.0

        # Priority affects confidence but not duration (higher priority = faster, but we don't model that)
        estimated_hours = base_hours * complexity_mult * gap_factor * dependency_factor

        # Calculate confidence based on variance
        confidence = self._calculate_confidence(actuals, len(historical))

        # Prediction interval (simple: ±1 std dev)
        try:
            std = stdev(actuals)
            lower_bound = max(estimated_hours - std, min(actuals))
            upper_bound = estimated_hours + std
        except (ValueError, TypeError):
            lower_bound = estimated_hours * 0.7
            upper_bound = estimated_hours * 1.5

        return {
            "estimated_hours": round(estimated_hours, 1),
            "estimated_days": round(estimated_hours / 8, 1),  # 8-hour workday
            "confidence": confidence,
            "range": {
                "low": round(lower_bound, 1),
                "high": round(upper_bound, 1),
            },
            "factors": {
                "base_median": round(base_hours, 1),
                "complexity_multiplier": complexity_mult,
                "gap_type_factor": gap_factor,
                "dependency_factor": dependency_factor,
            },
            "samples": len(historical),
            "method": "historical_median",
        }

    def _get_historical_data(
        self,
        gap_type: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[ImplementationWorkPackage]:
        """Get completed work packages matching criteria."""
        query = ImplementationWorkPackage.query.filter(
            ImplementationWorkPackage.status == "completed",
            ImplementationWorkPackage.actual_effort_hours.isnot(None),
            ImplementationWorkPackage.actual_effort_hours > 0,
        )

        if priority:
            query = query.filter(ImplementationWorkPackage.priority == priority)

        # Gap type filtering would require a join or metadata field
        # For now, we filter by priority only

        return query.order_by(ImplementationWorkPackage.completed_date.desc()).limit(100).all()

    def _fallback_estimate(
        self,
        gap_type: Optional[str],
        priority: str,
        complexity: str,
        has_dependencies: bool,
    ) -> Dict[str, Any]:
        """Fallback when insufficient historical data."""
        # Priority-based base hours
        priority_hours = {
            "low": 16,
            "medium": 40,
            "high": 80,
            "critical": 160,
        }

        base = priority_hours.get(priority, 40)
        complexity_mult = self.COMPLEXITY_MULTIPLIERS.get(complexity, 1.0)
        gap_factor = self.GAP_TYPE_FACTORS.get(gap_type, 1.0) if gap_type else 1.0
        dependency_factor = 1.2 if has_dependencies else 1.0

        estimated_hours = base * complexity_mult * gap_factor * dependency_factor

        return {
            "estimated_hours": round(estimated_hours, 1),
            "estimated_days": round(estimated_hours / 8, 1),
            "confidence": "low",
            "range": {
                "low": round(estimated_hours * 0.5, 1),
                "high": round(estimated_hours * 2.0, 1),
            },
            "factors": {
                "base_priority_hours": base,
                "complexity_multiplier": complexity_mult,
                "gap_type_factor": gap_factor,
                "dependency_factor": dependency_factor,
            },
            "samples": 0,
            "method": "fallback_priority_based",
        }

    def _calculate_confidence(self, actuals: List[float], sample_size: int) -> str:
        """Calculate confidence level based on variance and sample size."""
        if sample_size < 3:
            return "low"
        if sample_size < 10:
            return "medium"

        try:
            cv = stdev(actuals) / mean(actuals)  # Coefficient of variation
            if cv < 0.3:
                return "high"
            elif cv < 0.6:
                return "medium"
            else:
                return "low"
        except (ValueError, TypeError, ZeroDivisionError):
            return "medium"

    def get_estimation_accuracy(self) -> Dict[str, Any]:
        """
        Analyze how accurate past estimations were.
        Returns accuracy metrics for model validation.
        """
        completed = ImplementationWorkPackage.query.filter(
            ImplementationWorkPackage.status == "completed",
            ImplementationWorkPackage.actual_effort_hours.isnot(None),
            ImplementationWorkPackage.estimated_effort_hours.isnot(None),
        ).all()

        if not completed:
            return {"error": "No completed work packages with estimates"}

        errors = []
        for wp in completed:
            if wp.estimated_effort_hours > 0:
                error_pct = (
                    (wp.actual_effort_hours - wp.estimated_effort_hours)
                    / wp.estimated_effort_hours
                ) * 100
                errors.append(error_pct)

        if not errors:
            return {"error": "No valid estimates to compare"}

        return {
            "sample_size": len(errors),
            "mean_error_pct": round(mean(errors), 1),
            "median_error_pct": round(median(errors), 1),
            "std_dev": round(stdev(errors), 1) if len(errors) > 1 else 0,
            "within_25pct": sum(1 for e in errors if abs(e) <= 25),
            "accuracy_rate": round(sum(1 for e in errors if abs(e) <= 25) / len(errors) * 100, 1),
        }

    def suggest_buffer(self, estimated_hours: float, confidence: str) -> float:
        """Suggest contingency buffer based on confidence."""
        buffers = {
            "high": 0.1,    # 10% buffer
            "medium": 0.25,  # 25% buffer
            "low": 0.5,     # 50% buffer
        }
        buffer_pct = buffers.get(confidence, 0.25)
        return round(estimated_hours * (1 + buffer_pct), 1)
