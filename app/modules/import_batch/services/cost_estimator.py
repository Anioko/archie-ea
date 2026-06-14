"""
Unified Cost Estimator Service

Handles AI processing cost estimation for application imports.
Consolidated from batch_import_service.py cost calculation logic.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CostBreakdown:
    """Breakdown of estimated costs by category."""

    archimate_generation: float
    capability_mapping: float
    process_classification: float

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for JSON serialization."""
        return {
            "archimate_generation": self.archimate_generation,
            "capability_mapping": self.capability_mapping,
            "process_classification": self.process_classification,
        }


@dataclass
class CostEstimate:
    """Complete cost estimate for an import operation."""

    total_applications: int
    archimate_mode: str
    enable_ai_generation: bool
    estimated_total_usd: float
    cost_per_application: float
    breakdown: CostBreakdown
    budget_limit_usd: Optional[float] = None
    within_budget: bool = True

    # Expected output metrics
    expected_elements_min: int = 0
    expected_elements_max: int = 0
    elements_per_app_range: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_applications": self.total_applications,
            "archimate_mode": self.archimate_mode,
            "enable_ai_generation": self.enable_ai_generation,
            "estimated_total_usd": self.estimated_total_usd,
            "cost_per_application": self.cost_per_application,
            "breakdown": self.breakdown.to_dict(),
            "budget_limit_usd": self.budget_limit_usd,
            "within_budget": self.within_budget,
            "expected_elements_min": self.expected_elements_min,
            "expected_elements_max": self.expected_elements_max,
            "elements_per_app_range": self.elements_per_app_range,
        }


class CostEstimator:
    """
    Unified cost estimator for AI-powered import operations.

    Provides consistent cost estimation across Quick Mode and Governed Mode imports.
    Cost constants can be overridden via Flask app config (IMPORT_COST_* keys).
    """

    # Default cost constants (USD per application) - overridable via config
    DEFAULT_COST_PER_APP_BASE = Decimal("0.02")
    DEFAULT_COST_CAPABILITY_MAPPING = Decimal("0.01")
    DEFAULT_COST_PROCESS_CLASSIFICATION = Decimal("0.01")

    # ArchiMate mode multipliers
    ARCHIMATE_MODE_MULTIPLIERS = {
        "quick": Decimal("1.0"),
        "standard": Decimal("2.5"),
        "comprehensive": Decimal("5.0"),
    }

    # Expected elements per application by mode
    EXPECTED_ELEMENTS_PER_APP = {
        "quick": {"min": 3, "max": 5},
        "standard": {"min": 8, "max": 12},
        "comprehensive": {"min": 15, "max": 25},
    }

    @property
    def COST_PER_APP_BASE(self):
        """Get base cost per app from config or default."""
        try:
            from flask import current_app
            return Decimal(str(current_app.config.get(
                "IMPORT_COST_PER_APP_BASE", self.DEFAULT_COST_PER_APP_BASE
            )))
        except RuntimeError:
            return self.DEFAULT_COST_PER_APP_BASE

    @property
    def COST_CAPABILITY_MAPPING(self):
        """Get capability mapping cost from config or default."""
        try:
            from flask import current_app
            return Decimal(str(current_app.config.get(
                "IMPORT_COST_CAPABILITY_MAPPING", self.DEFAULT_COST_CAPABILITY_MAPPING
            )))
        except RuntimeError:
            return self.DEFAULT_COST_CAPABILITY_MAPPING

    @property
    def COST_PROCESS_CLASSIFICATION(self):
        """Get process classification cost from config or default."""
        try:
            from flask import current_app
            return Decimal(str(current_app.config.get(
                "IMPORT_COST_PROCESS_CLASSIFICATION", self.DEFAULT_COST_PROCESS_CLASSIFICATION
            )))
        except RuntimeError:
            return self.DEFAULT_COST_PROCESS_CLASSIFICATION

    def estimate_cost(
        self,
        app_count: int,
        mode: str = "standard",
        enable_ai: bool = True,
        budget_limit_usd: Optional[float] = None,
    ) -> CostEstimate:
        """
        Estimate AI processing costs for an import operation.

        Args:
            app_count: Number of applications to process
            mode: ArchiMate generation mode (quick/standard/comprehensive)
            enable_ai: Whether AI generation is enabled
            budget_limit_usd: Optional budget limit to check against

        Returns:
            CostEstimate with full cost breakdown
        """
        mode_multiplier = self.ARCHIMATE_MODE_MULTIPLIERS.get(mode, Decimal("2.5"))

        if enable_ai and app_count > 0:
            archimate_cost = self.COST_PER_APP_BASE * mode_multiplier * app_count
            capability_cost = self.COST_CAPABILITY_MAPPING * app_count
            process_cost = self.COST_PROCESS_CLASSIFICATION * app_count
        else:
            archimate_cost = Decimal("0")
            capability_cost = Decimal("0")
            process_cost = Decimal("0")

        total_cost = archimate_cost + capability_cost + process_cost
        cost_per_app = float(total_cost / app_count) if app_count > 0 else 0.0

        # Check budget
        within_budget = True
        if budget_limit_usd is not None:
            within_budget = float(total_cost) <= budget_limit_usd

        # Calculate expected elements
        elements_range = self.EXPECTED_ELEMENTS_PER_APP.get(mode, {"min": 8, "max": 12})
        expected_min = app_count * elements_range["min"]
        expected_max = app_count * elements_range["max"]

        return CostEstimate(
            total_applications=app_count,
            archimate_mode=mode,
            enable_ai_generation=enable_ai,
            estimated_total_usd=float(total_cost),
            cost_per_application=cost_per_app,
            breakdown=CostBreakdown(
                archimate_generation=float(archimate_cost),
                capability_mapping=float(capability_cost),
                process_classification=float(process_cost),
            ),
            budget_limit_usd=budget_limit_usd,
            within_budget=within_budget,
            expected_elements_min=expected_min,
            expected_elements_max=expected_max,
            elements_per_app_range=f"{elements_range['min']}-{elements_range['max']}",
        )
