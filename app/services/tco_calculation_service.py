"""
TCO (Total Cost of Ownership) Calculation Service

Enterprise-grade service for calculating and analyzing Total Cost of Ownership
with comprehensive error handling and validation.

Features:
- Safe TCO calculations with divide-by-zero protection
- Cost breakdown analysis
- ROI calculations
- Cost trend analysis
- Financial risk assessment
"""

import logging
from datetime import date, datetime
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Dict, List, Optional, Tuple, Union

from .. import db
from ..models.application_portfolio import ApplicationComponent

logger = logging.getLogger(__name__)


class TCOCalculationService:
    """
    Enterprise service for TCO calculations with comprehensive error handling.

    Provides safe financial calculations with proper validation and error reporting.
    """

    def __init__(self):
        """Initialize TCO calculation service."""
        self.logger = logging.getLogger(__name__)

        # Cost component weights for analysis
        self.cost_weights = {
            "license": 0.30,  # 30% of TCO
            "maintenance": 0.25,  # 25% of TCO
            "infrastructure": 0.20,  # 20% of TCO
            "support": 0.15,  # 15% of TCO
            "implementation": 0.10,  # 10% of TCO (one-time)
        }

    def calculate_tco_breakdown(
        self, application: ApplicationComponent
    ) -> Dict[str, Union[float, str]]:
        """
        Calculate comprehensive TCO breakdown with divide-by-zero protection.

        Args:
            application: ApplicationComponent instance

        Returns:
            Dictionary with TCO breakdown and safety metrics
        """
        try:
            # Extract cost components safely
            costs = self._extract_cost_components(application)

            # Calculate total TCO
            total_tco = self._safe_sum(costs.values())

            if total_tco <= 0:
                return {
                    "total_tco": 0.0,
                    "license_cost": 0.0,
                    "maintenance_cost": 0.0,
                    "infrastructure_cost": 0.0,
                    "support_cost": 0.0,
                    "implementation_cost": 0.0,
                    "cost_breakdown": {},
                    "risk_level": "low",
                    "message": "No cost data available",
                }

            # Calculate percentages with divide-by-zero protection
            cost_breakdown = {}
            for component, cost in costs.items():
                percentage = self._safe_percentage(cost, total_tco)
                cost_breakdown[component] = {
                    "absolute": float(cost or 0),
                    "percentage": percentage,
                    "weight": self.cost_weights.get(component.replace("_cost", ""), 0.0),
                }

            # Assess financial risk
            risk_level = self._assess_financial_risk(costs, total_tco)

            return {
                "total_tco": float(total_tco),
                "license_cost": float(costs.get("license_cost", 0) or 0),
                "maintenance_cost": float(costs.get("maintenance_cost", 0) or 0),
                "infrastructure_cost": float(costs.get("infrastructure_cost", 0) or 0),
                "support_cost": float(costs.get("support_cost", 0) or 0),
                "implementation_cost": float(costs.get("implementation_cost", 0) or 0),
                "cost_breakdown": cost_breakdown,
                "risk_level": risk_level,
                "calculated_at": datetime.utcnow().isoformat(),
                "message": "TCO calculation completed successfully",
            }

        except Exception as e:
            self.logger.error(
                f"Error calculating TCO breakdown for application {application.id}: {e}"
            )
            return {
                "total_tco": 0.0,
                "license_cost": 0.0,
                "maintenance_cost": 0.0,
                "infrastructure_cost": 0.0,
                "support_cost": 0.0,
                "implementation_cost": 0.0,
                "cost_breakdown": {},
                "risk_level": "high",
                "error": str(e),
                "message": "TCO calculation failed",
            }

    def calculate_roi_score(
        self, application: ApplicationComponent
    ) -> Dict[str, Union[float, str]]:
        """
        Calculate ROI score with comprehensive error handling.

        Args:
            application: ApplicationComponent instance

        Returns:
            Dictionary with ROI metrics and validation
        """
        try:
            total_tco = self._safe_sum(
                [
                    application.license_cost or 0,
                    application.maintenance_cost or 0,
                    application.infrastructure_cost or 0,
                    application.support_cost or 0,
                ]
            )

            roi_score = application.roi_score

            if total_tco <= 0:
                return {
                    "roi_score": 0.0,
                    "total_tco": 0.0,
                    "roi_category": "no_data",
                    "investment_efficiency": 0.0,
                    "message": "No TCO data available for ROI calculation",
                }

            # Calculate investment efficiency
            investment_efficiency = self._safe_divide(roi_score or 0, total_tco)

            # Categorize ROI
            roi_category = self._categorize_roi(roi_score or 0)

            return {
                "roi_score": float(roi_score or 0),
                "total_tco": float(total_tco),
                "roi_category": roi_category,
                "investment_efficiency": float(investment_efficiency),
                "calculated_at": datetime.utcnow().isoformat(),
                "message": "ROI calculation completed successfully",
            }

        except Exception as e:
            self.logger.error(f"Error calculating ROI for application {application.id}: {e}")
            return {
                "roi_score": 0.0,
                "total_tco": 0.0,
                "roi_category": "error",
                "investment_efficiency": 0.0,
                "error": str(e),
                "message": "ROI calculation failed",
            }

    def _extract_cost_components(
        self, application: ApplicationComponent
    ) -> Dict[str, Optional[float]]:
        """Safely extract cost components from application."""
        return {
            "license_cost": self._safe_float(application.license_cost),
            "maintenance_cost": self._safe_float(application.maintenance_cost),
            "infrastructure_cost": self._safe_float(application.infrastructure_cost),
            "support_cost": self._safe_float(application.support_cost),
            "implementation_cost": self._safe_float(application.implementation_cost),
        }

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float with error handling."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError, InvalidOperation):
            return None

    def _safe_sum(self, values: List[Optional[float]]) -> float:
        """Safely sum values with None handling."""
        try:
            return sum(v or 0 for v in values)
        except Exception:
            return 0.0

    def _safe_divide(self, numerator: float, denominator: float, default: float = 0.0) -> float:
        """
        Safely divide two numbers with comprehensive error handling.

        Args:
            numerator: The dividend
            denominator: The divisor
            default: Default value if division fails

        Returns:
            Result of division or default value
        """
        try:
            if denominator == 0:
                self.logger.warning("Division by zero attempted, returning default value")
                return default

            # Handle edge cases
            if not isinstance(numerator, (int, float, Decimal)) or not isinstance(
                denominator, (int, float, Decimal)
            ):
                return default

            # Convert to float for consistency
            num_float = float(numerator)
            den_float = float(denominator)

            # Additional safety checks
            if abs(den_float) < 1e-10:  # Very small number threshold
                self.logger.warning(f"Denominator too small ({den_float}), returning default")
                return default

            result = num_float / den_float

            # Check for reasonable results
            if abs(result) > 1e10:  # Very large result threshold
                self.logger.warning(f"Division result too large ({result}), returning default")
                return default

            return result

        except (ZeroDivisionError, InvalidOperation, ValueError, TypeError, OverflowError) as e:
            self.logger.warning(f"Safe division failed: {e}, returning default value")
            return default
        except Exception as e:
            self.logger.error(f"Unexpected error in safe division: {e}, returning default value")
            return default

    def _safe_percentage(self, part: float, whole: float) -> float:
        """Safely calculate percentage with divide-by-zero protection."""
        return self._safe_divide(part, whole, 0.0) * 100

    def _assess_financial_risk(self, costs: Dict[str, Optional[float]], total_tco: float) -> str:
        """Assess financial risk based on cost distribution."""
        try:
            if total_tco <= 0:
                return "low"

            # Check for unusual cost patterns
            cost_ratios = {}
            for component, cost in costs.items():
                if cost and cost > 0:
                    ratio = self._safe_divide(cost, total_tco)
                    cost_ratios[component] = ratio

            # Risk factors
            risk_factors = []

            # High implementation cost relative to annual costs
            impl_ratio = cost_ratios.get("implementation_cost", 0)
            if impl_ratio > 0.5:  # Implementation cost > 50% of total
                risk_factors.append("high_implementation")

            # Low maintenance cost (potential underestimation)
            maint_ratio = cost_ratios.get("maintenance_cost", 0)
            if maint_ratio < 0.1:  # Maintenance cost < 10% of total
                risk_factors.append("low_maintenance")

            # No license cost for commercial software
            license_cost = costs.get("license_cost", 0)
            if license_cost == 0 and total_tco > 10000:  # High TCO but no license cost
                risk_factors.append("missing_license")

            # Determine risk level
            if len(risk_factors) >= 2:
                return "high"
            elif len(risk_factors) == 1:
                return "medium"
            else:
                return "low"

        except Exception as e:
            self.logger.error(f"Error assessing financial risk: {e}")
            return "high"  # Default to high risk on error

    def _categorize_roi(self, roi_score: float) -> str:
        """Categorize ROI score into meaningful categories."""
        if roi_score >= 150:
            return "excellent"
        elif roi_score >= 100:
            return "good"
        elif roi_score >= 50:
            return "moderate"
        elif roi_score >= 0:
            return "poor"
        else:
            return "negative"

    def generate_cost_trend_analysis(self, application_id: int, years: int = 3) -> Dict:
        """
        Generate cost trend analysis for an application.

        Args:
            application_id: Application ID
            years: Number of years to analyze

        Returns:
            Dictionary with trend analysis
        """
        try:
            application = ApplicationComponent.query.get(application_id)
            if not application:
                return {"error": "Application not found", "message": "Invalid application ID"}

            current_costs = self._extract_cost_components(application)
            total_tco = self._safe_sum(current_costs.values())

            # Generate projected costs (simple inflation model)
            inflation_rate = 0.03  # 3% annual inflation
            trends = {}

            for year in range(1, years + 1):
                year_costs = {}
                year_total = 0

                for component, cost in current_costs.items():
                    if cost and cost > 0:
                        # Apply inflation to recurring costs (not implementation)
                        if component != "implementation_cost":
                            inflated_cost = cost * ((1 + inflation_rate) ** year)
                        else:
                            inflated_cost = cost  # Implementation cost stays constant

                        year_costs[component] = float(inflated_cost)
                        year_total += inflated_cost

                trends[f"year_{year}"] = {
                    "costs": year_costs,
                    "total": float(year_total),
                    "inflation_adjusted": True,
                }

            return {
                "application_id": application_id,
                "current_tco": float(total_tco),
                "trends": trends,
                "inflation_rate": inflation_rate,
                "analysis_years": years,
                "generated_at": datetime.utcnow().isoformat(),
                "message": "Cost trend analysis completed successfully",
            }

        except Exception as e:
            self.logger.error(
                f"Error generating cost trend analysis for application {application_id}: {e}"
            )
            return {
                "error": str(e),
                "message": "Cost trend analysis failed",
                "application_id": application_id,
            }
