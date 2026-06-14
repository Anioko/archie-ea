"""
Solution Cost Service - Multi-year TCO Analysis — canonical v2 implementation

Service for managing solution cost models with:
- Cost model creation and line item management
- Year-by-year projection calculations
- TCO and NPV calculations
- Multi-option comparison and analysis
- Variance tracking between projected and actual costs
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple  # dead-code-ok

from sqlalchemy import func  # dead-code-ok

from app import db
from app.models.solution_cost_model import (
    SolutionCostComparison,
    SolutionCostLineItem,
    SolutionCostModel,
    SolutionCostYearlyProjection,
)

logger = logging.getLogger(__name__)


class SolutionCostService:
    """Service for managing solution cost models"""

    # Category mappings for projections
    CAPEX_CATEGORIES = {
        "hardware": "capex_hardware",
        "software": "capex_software",
        "services": "capex_services",
        "other": "capex_other",
    }

    OPEX_CATEGORIES = {
        "licensing": "opex_licensing",
        "maintenance": "opex_maintenance",
        "support": "opex_support",
        "infrastructure": "opex_infrastructure",
        "personnel": "opex_personnel",
        "other": "opex_other",
    }

    def create_cost_model(
        self,
        solution_id: int,
        name: str,
        projection_years: int = 5,
        currency: str = "USD",
        discount_rate: float = 0.10,
        inflation_rate: float = 0.03,
        description: str = None,
        created_by_id: int = None,
    ) -> SolutionCostModel:
        """
        Create a new cost model for a solution.

        Args:
            solution_id: ID of the solution this cost model belongs to
            name: Name of the cost model
            projection_years: Number of years to project (default 5)
            currency: Currency code (default USD)
            discount_rate: Discount rate for NPV calculations (default 10%)
            inflation_rate: Annual inflation rate (default 3%)
            description: Optional description
            created_by_id: ID of the user creating the model

        Returns:
            Created SolutionCostModel instance
        """
        cost_model = SolutionCostModel(
            solution_id=solution_id,
            name=name,
            description=description,
            currency=currency,
            projection_years=projection_years,
            discount_rate=discount_rate,
            inflation_rate=inflation_rate,
            created_by_id=created_by_id,
            status="draft",
        )

        db.session.add(cost_model)
        db.session.commit()

        logger.info(f"Created cost model '{name}' for solution {solution_id}")
        return cost_model

    def add_line_item(
        self,
        cost_model_id: int,
        category: str,
        cost_type: str,
        name: str,
        unit_cost: float,
        quantity: int = 1,
        frequency: str = "one_time",
        start_year: int = 1,
        end_year: int = None,
        annual_growth_rate: float = 0,
        description: str = None,
        vendor_product_id: int = None,
    ) -> SolutionCostLineItem:
        """
        Add a cost line item to a cost model.

        Args:
            cost_model_id: ID of the cost model
            category: Cost category (hardware, software, services, personnel, infrastructure, other)
            cost_type: Type of cost (capex, opex)
            name: Name of the line item
            unit_cost: Cost per unit
            quantity: Number of units (default 1)
            frequency: Cost frequency (one_time, monthly, annual)
            start_year: Year when cost starts (default 1)
            end_year: Year when cost ends (None = ongoing)
            annual_growth_rate: Annual growth rate for recurring costs (default 0)
            description: Optional description
            vendor_product_id: Optional link to vendor product

        Returns:
            Created SolutionCostLineItem instance
        """
        cost_model = SolutionCostModel.query.get(cost_model_id)
        if not cost_model:
            raise ValueError(f"Cost model {cost_model_id} not found")

        line_item = SolutionCostLineItem(
            cost_model_id=cost_model_id,
            category=category,
            cost_type=cost_type.lower(),
            name=name,
            description=description,
            unit_cost=Decimal(str(unit_cost)),
            quantity=quantity,
            frequency=frequency,
            start_year=start_year,
            end_year=end_year,
            annual_growth_rate=annual_growth_rate,
            vendor_product_id=vendor_product_id,
        )

        db.session.add(line_item)
        db.session.commit()

        logger.info(f"Added line item '{name}' to cost model {cost_model_id}")
        return line_item

    def calculate_projections(self, cost_model_id: int) -> List[SolutionCostYearlyProjection]:
        """
        Calculate year-by-year projections from line items.

        Applies frequency multipliers, growth rates, and inflation
        to generate detailed yearly projections.

        Args:
            cost_model_id: ID of the cost model

        Returns:
            List of SolutionCostYearlyProjection instances
        """
        cost_model = SolutionCostModel.query.get(cost_model_id)
        if not cost_model:
            raise ValueError(f"Cost model {cost_model_id} not found")

        # Clear existing projections
        SolutionCostYearlyProjection.query.filter_by(cost_model_id=cost_model_id).delete()

        projections = []
        cumulative_total = Decimal("0")

        for year in range(1, cost_model.projection_years + 1):
            projection = SolutionCostYearlyProjection(cost_model_id=cost_model_id, year=year)

            # Initialize all fields to zero
            for field in [
                "capex_hardware",
                "capex_software",
                "capex_services",
                "capex_other",
                "opex_licensing",
                "opex_maintenance",
                "opex_support",
                "opex_infrastructure",
                "opex_personnel",
                "opex_other",
            ]:
                setattr(projection, field, Decimal("0"))

            # Process each line item
            for item in cost_model.line_items:
                # Check if item applies to this year
                if item.start_year > year:
                    continue
                if item.end_year and item.end_year < year:
                    continue

                # Calculate base annual cost
                base_cost = item.unit_cost * item.quantity

                if item.frequency == "monthly":
                    annual_cost = base_cost * 12
                elif item.frequency == "annual":
                    annual_cost = base_cost
                elif item.frequency == "one_time":
                    # One-time costs only apply in the start year
                    if year == item.start_year:
                        annual_cost = base_cost
                    else:
                        continue
                else:
                    annual_cost = base_cost

                # Apply growth rate for years after start
                years_after_start = year - item.start_year
                if years_after_start > 0 and item.annual_growth_rate > 0:
                    growth_multiplier = Decimal(
                        str((1 + item.annual_growth_rate) ** years_after_start)
                    )
                    annual_cost = annual_cost * growth_multiplier

                # Apply inflation
                if year > 1 and cost_model.inflation_rate > 0:
                    inflation_multiplier = Decimal(
                        str((1 + cost_model.inflation_rate) ** (year - 1))
                    )
                    annual_cost = annual_cost * inflation_multiplier

                # Add to appropriate category
                if item.cost_type == "capex":
                    field = self.CAPEX_CATEGORIES.get(item.category, "capex_other")
                    current = getattr(projection, field) or Decimal("0")
                    setattr(projection, field, current + annual_cost)
                else:  # opex
                    field = self.OPEX_CATEGORIES.get(item.category, "opex_other")
                    current = getattr(projection, field) or Decimal("0")
                    setattr(projection, field, current + annual_cost)

            # Calculate totals
            projection.capex_total = (
                (projection.capex_hardware or Decimal("0"))
                + (projection.capex_software or Decimal("0"))
                + (projection.capex_services or Decimal("0"))
                + (projection.capex_other or Decimal("0"))
            )

            projection.opex_total = (
                (projection.opex_licensing or Decimal("0"))
                + (projection.opex_maintenance or Decimal("0"))
                + (projection.opex_support or Decimal("0"))
                + (projection.opex_infrastructure or Decimal("0"))
                + (projection.opex_personnel or Decimal("0"))
                + (projection.opex_other or Decimal("0"))
            )

            projection.year_total = projection.capex_total + projection.opex_total
            cumulative_total += projection.year_total
            projection.cumulative_total = cumulative_total

            # Calculate discounted value (present value)
            if cost_model.discount_rate > 0:
                discount_factor = Decimal(str((1 + cost_model.discount_rate) ** (year - 1)))
                projection.discounted_value = projection.year_total / discount_factor
            else:
                projection.discounted_value = projection.year_total

            db.session.add(projection)
            projections.append(projection)

        db.session.commit()
        logger.info(
            f"Calculated {len(projections)} year projections for cost model {cost_model_id}"
        )
        return projections

    def calculate_tco(self, cost_model_id: int) -> Dict:
        """
        Calculate Total Cost of Ownership.

        Args:
            cost_model_id: ID of the cost model

        Returns:
            Dictionary with total_capex, total_opex, total_tco, yearly_breakdown
        """
        cost_model = SolutionCostModel.query.get(cost_model_id)
        if not cost_model:
            raise ValueError(f"Cost model {cost_model_id} not found")

        # Ensure projections are calculated
        projections = list(
            cost_model.yearly_projections.order_by(SolutionCostYearlyProjection.year)
        )

        if not projections:
            projections = self.calculate_projections(cost_model_id)

        total_capex = sum(p.capex_total or Decimal("0") for p in projections)
        total_opex = sum(p.opex_total or Decimal("0") for p in projections)
        total_tco = total_capex + total_opex

        # Update cost model totals
        cost_model.total_capex = total_capex
        cost_model.total_opex = total_opex
        cost_model.total_tco = total_tco
        db.session.commit()

        yearly_breakdown = [
            {
                "year": p.year,
                "capex": float(p.capex_total or 0),
                "opex": float(p.opex_total or 0),
                "total": float(p.year_total or 0),
                "cumulative": float(p.cumulative_total or 0),
            }
            for p in projections
        ]

        return {
            "total_capex": float(total_capex),
            "total_opex": float(total_opex),
            "total_tco": float(total_tco),
            "currency": cost_model.currency,
            "projection_years": cost_model.projection_years,
            "yearly_breakdown": yearly_breakdown,
        }

    def calculate_npv(self, cost_model_id: int) -> float:
        """
        Calculate Net Present Value.

        Args:
            cost_model_id: ID of the cost model

        Returns:
            NPV as float
        """
        cost_model = SolutionCostModel.query.get(cost_model_id)
        if not cost_model:
            raise ValueError(f"Cost model {cost_model_id} not found")

        projections = list(
            cost_model.yearly_projections.order_by(SolutionCostYearlyProjection.year)
        )

        if not projections:
            projections = self.calculate_projections(cost_model_id)

        npv = sum(p.discounted_value or Decimal("0") for p in projections)

        # Update cost model NPV
        cost_model.npv = npv
        db.session.commit()

        logger.info(f"Calculated NPV of {npv} for cost model {cost_model_id}")
        return float(npv)

    def compare_options(
        self,
        cost_model_ids: List[int],
        name: str = None,
        session_id: int = None,
        created_by_id: int = None,
    ) -> SolutionCostComparison:
        """
        Compare multiple cost models.

        Args:
            cost_model_ids: List of cost model IDs to compare
            name: Name for the comparison (optional)
            session_id: Optional session ID to link comparison
            created_by_id: ID of user creating the comparison

        Returns:
            SolutionCostComparison instance with analysis results
        """
        if len(cost_model_ids) < 2:
            raise ValueError("At least 2 cost models required for comparison")

        # Calculate TCO and NPV for each model
        models_data = []
        for model_id in cost_model_ids:
            tco_data = self.calculate_tco(model_id)
            npv = self.calculate_npv(model_id)
            cost_model = SolutionCostModel.query.get(model_id)

            models_data.append(
                {
                    "id": model_id,
                    "name": cost_model.name,
                    "tco": tco_data["total_tco"],
                    "npv": npv,
                    "capex": tco_data["total_capex"],
                    "opex": tco_data["total_opex"],
                    "years": tco_data["projection_years"],
                }
            )

        # Find lowest TCO and NPV
        lowest_tco = min(models_data, key=lambda x: x["tco"])
        lowest_npv = min(models_data, key=lambda x: x["npv"])

        # Generate recommendation
        if lowest_tco["id"] == lowest_npv["id"]:
            recommendation = (
                f"'{lowest_tco['name']}' offers both the lowest TCO "
                f"({lowest_tco['tco']:,.2f}) and lowest NPV ({lowest_npv['npv']:,.2f}), "
                f"making it the clear financial choice."
            )
        else:
            recommendation = (
                f"'{lowest_tco['name']}' has the lowest TCO ({lowest_tco['tco']:,.2f}), "
                f"while '{lowest_npv['name']}' has the lowest NPV ({lowest_npv['npv']:,.2f}). "
                f"Consider time value of money requirements when choosing."
            )

        # Create comparison record
        comparison = SolutionCostComparison(
            name=name or f"Comparison of {len(cost_model_ids)} options",
            session_id=session_id,
            compared_models=cost_model_ids,
            lowest_tco_model_id=lowest_tco["id"],
            lowest_npv_model_id=lowest_npv["id"],
            recommendation=recommendation,
            comparison_notes=str(
                {"models": models_data, "analysis_date": datetime.utcnow().isoformat()}
            ),
            created_by_id=created_by_id,
        )

        db.session.add(comparison)
        db.session.commit()

        logger.info(f"Created cost comparison with {len(cost_model_ids)} models")
        return comparison

    def generate_cost_report(self, cost_model_id: int) -> Dict:
        """
        Generate comprehensive cost report.

        Args:
            cost_model_id: ID of the cost model

        Returns:
            Dictionary with summary, yearly_projections, by_category, by_vendor, charts_data
        """
        cost_model = SolutionCostModel.query.get(cost_model_id)
        if not cost_model:
            raise ValueError(f"Cost model {cost_model_id} not found")

        # Calculate TCO and NPV
        tco_data = self.calculate_tco(cost_model_id)
        npv = self.calculate_npv(cost_model_id)

        # Get projections
        projections = list(
            cost_model.yearly_projections.order_by(SolutionCostYearlyProjection.year)
        )

        # Aggregate by category
        by_category = {
            "capex": {
                "hardware": Decimal("0"),
                "software": Decimal("0"),
                "services": Decimal("0"),
                "other": Decimal("0"),
            },
            "opex": {
                "licensing": Decimal("0"),
                "maintenance": Decimal("0"),
                "support": Decimal("0"),
                "infrastructure": Decimal("0"),
                "personnel": Decimal("0"),
                "other": Decimal("0"),
            },
        }

        for p in projections:
            by_category["capex"]["hardware"] += p.capex_hardware or Decimal("0")
            by_category["capex"]["software"] += p.capex_software or Decimal("0")
            by_category["capex"]["services"] += p.capex_services or Decimal("0")
            by_category["capex"]["other"] += p.capex_other or Decimal("0")
            by_category["opex"]["licensing"] += p.opex_licensing or Decimal("0")
            by_category["opex"]["maintenance"] += p.opex_maintenance or Decimal("0")
            by_category["opex"]["support"] += p.opex_support or Decimal("0")
            by_category["opex"]["infrastructure"] += p.opex_infrastructure or Decimal("0")
            by_category["opex"]["personnel"] += p.opex_personnel or Decimal("0")
            by_category["opex"]["other"] += p.opex_other or Decimal("0")

        # Aggregate by vendor
        by_vendor = {}
        for item in cost_model.line_items:
            vendor_name = "No Vendor"
            if item.vendor_product:
                vendor_name = (
                    item.vendor_product.vendor.name
                    if item.vendor_product.vendor
                    else "Unknown Vendor"
                )

            if vendor_name not in by_vendor:
                by_vendor[vendor_name] = {
                    "capex": Decimal("0"),
                    "opex": Decimal("0"),
                    "total": Decimal("0"),
                    "items": [],
                }

            # Calculate total for this item over projection period
            item_total = self._calculate_item_total(item, cost_model)
            if item.cost_type == "capex":
                by_vendor[vendor_name]["capex"] += item_total
            else:
                by_vendor[vendor_name]["opex"] += item_total
            by_vendor[vendor_name]["total"] += item_total
            by_vendor[vendor_name]["items"].append(
                {"name": item.name, "cost_type": item.cost_type, "total": float(item_total)}
            )

        # Prepare chart data
        charts_data = {
            "yearly_costs": {
                "labels": [f"Year {p.year}" for p in projections],
                "capex": [float(p.capex_total or 0) for p in projections],
                "opex": [float(p.opex_total or 0) for p in projections],
                "cumulative": [float(p.cumulative_total or 0) for p in projections],
            },
            "cost_breakdown": {
                "labels": ["CapEx", "OpEx"],
                "values": [tco_data["total_capex"], tco_data["total_opex"]],
            },
            "category_breakdown": {
                "capex_labels": list(by_category["capex"].keys()),
                "capex_values": [float(v) for v in by_category["capex"].values()],
                "opex_labels": list(by_category["opex"].keys()),
                "opex_values": [float(v) for v in by_category["opex"].values()],
            },
        }

        return {
            "summary": {
                "name": cost_model.name,
                "description": cost_model.description,
                "currency": cost_model.currency,
                "projection_years": cost_model.projection_years,
                "discount_rate": cost_model.discount_rate,
                "inflation_rate": cost_model.inflation_rate,
                "total_capex": tco_data["total_capex"],
                "total_opex": tco_data["total_opex"],
                "total_tco": tco_data["total_tco"],
                "npv": npv,
                "status": cost_model.status,
            },
            "yearly_projections": tco_data["yearly_breakdown"],
            "by_category": {
                category: {k: float(v) for k, v in items.items()}
                for category, items in by_category.items()
            },
            "by_vendor": {
                vendor: {
                    "capex": float(data["capex"]),
                    "opex": float(data["opex"]),
                    "total": float(data["total"]),
                    "items": data["items"],
                }
                for vendor, data in by_vendor.items()
            },
            "charts_data": charts_data,
        }

    def _calculate_item_total(
        self, item: SolutionCostLineItem, cost_model: SolutionCostModel
    ) -> Decimal:
        """Calculate total cost for a line item over the projection period."""
        total = Decimal("0")

        for year in range(1, cost_model.projection_years + 1):
            if item.start_year > year:
                continue
            if item.end_year and item.end_year < year:
                continue

            base_cost = item.unit_cost * item.quantity

            if item.frequency == "monthly":
                annual_cost = base_cost * 12
            elif item.frequency == "annual":
                annual_cost = base_cost
            elif item.frequency == "one_time":
                if year == item.start_year:
                    annual_cost = base_cost
                else:
                    continue
            else:
                annual_cost = base_cost

            # Apply growth rate
            years_after_start = year - item.start_year
            if years_after_start > 0 and item.annual_growth_rate > 0:
                growth_multiplier = Decimal(str((1 + item.annual_growth_rate) ** years_after_start))
                annual_cost = annual_cost * growth_multiplier

            # Apply inflation
            if year > 1 and cost_model.inflation_rate > 0:
                inflation_multiplier = Decimal(str((1 + cost_model.inflation_rate) ** (year - 1)))
                annual_cost = annual_cost * inflation_multiplier

            total += annual_cost

        return total

    def import_from_recommendation(
        self, solution_id: int, recommendation: Dict, name: str = None, created_by_id: int = None
    ) -> SolutionCostModel:
        """
        Create cost model from AI recommendation estimates.

        Args:
            solution_id: ID of the solution
            recommendation: Dictionary with cost estimates from AI
            name: Optional name for the cost model
            created_by_id: ID of user creating the model

        Returns:
            Created SolutionCostModel instance
        """
        # Create the cost model
        cost_model = self.create_cost_model(
            solution_id=solution_id,
            name=name or f"Cost Model from Recommendation",
            description="Generated from AI recommendation estimates",
            created_by_id=created_by_id,
        )

        # Parse and add line items from recommendation
        if "licensing" in recommendation:
            self.add_line_item(
                cost_model_id=cost_model.id,
                category="licensing",
                cost_type="opex",
                name="Software Licensing",
                unit_cost=recommendation["licensing"].get("annual_cost", 0),
                frequency="annual",
                description=recommendation["licensing"].get("description", ""),
            )

        if "implementation" in recommendation:
            self.add_line_item(
                cost_model_id=cost_model.id,
                category="services",
                cost_type="capex",
                name="Implementation Services",
                unit_cost=recommendation["implementation"].get("cost", 0),
                frequency="one_time",
                description=recommendation["implementation"].get("description", ""),
            )

        if "maintenance" in recommendation:
            self.add_line_item(
                cost_model_id=cost_model.id,
                category="maintenance",
                cost_type="opex",
                name="Annual Maintenance",
                unit_cost=recommendation["maintenance"].get("annual_cost", 0),
                frequency="annual",
                annual_growth_rate=recommendation["maintenance"].get("growth_rate", 0.03),
                description=recommendation["maintenance"].get("description", ""),
            )

        if "infrastructure" in recommendation:
            self.add_line_item(
                cost_model_id=cost_model.id,
                category="infrastructure",
                cost_type="opex",
                name="Infrastructure Costs",
                unit_cost=recommendation["infrastructure"].get("monthly_cost", 0),
                frequency="monthly",
                description=recommendation["infrastructure"].get("description", ""),
            )

        if "personnel" in recommendation:
            self.add_line_item(
                cost_model_id=cost_model.id,
                category="personnel",
                cost_type="opex",
                name="Personnel/Support",
                unit_cost=recommendation["personnel"].get("annual_cost", 0),
                frequency="annual",
                description=recommendation["personnel"].get("description", ""),
            )

        if "hardware" in recommendation:
            self.add_line_item(
                cost_model_id=cost_model.id,
                category="hardware",
                cost_type="capex",
                name="Hardware",
                unit_cost=recommendation["hardware"].get("cost", 0),
                frequency="one_time",
                start_year=recommendation["hardware"].get("year", 1),
                description=recommendation["hardware"].get("description", ""),
            )

        # Calculate projections
        self.calculate_projections(cost_model.id)

        logger.info(f"Created cost model {cost_model.id} from recommendation")
        return cost_model

    def record_actual_cost(
        self, cost_model_id: int, year: int, actual_total: float, explanation: str = None
    ) -> SolutionCostYearlyProjection:
        """
        Record actual costs for variance tracking.

        Args:
            cost_model_id: ID of the cost model
            year: Year to record actual for
            actual_total: Actual total cost
            explanation: Optional explanation for variance

        Returns:
            Updated SolutionCostYearlyProjection instance
        """
        projection = SolutionCostYearlyProjection.query.filter_by(
            cost_model_id=cost_model_id, year=year
        ).first()

        if not projection:
            raise ValueError(f"No projection found for year {year}")

        projection.actual_total = Decimal(str(actual_total))
        projection.variance = projection.actual_total - (projection.year_total or Decimal("0"))
        projection.variance_explanation = explanation

        db.session.commit()

        logger.info(
            f"Recorded actual cost of {actual_total} for year {year}, "
            f"variance: {projection.variance}"
        )
        return projection

    def get_variance_analysis(self, cost_model_id: int) -> Dict:
        """
        Analyze variance between projected and actual costs.

        Args:
            cost_model_id: ID of the cost model

        Returns:
            Dictionary with variance analysis
        """
        cost_model = SolutionCostModel.query.get(cost_model_id)
        if not cost_model:
            raise ValueError(f"Cost model {cost_model_id} not found")

        projections = list(
            cost_model.yearly_projections.order_by(SolutionCostYearlyProjection.year)
        )

        years_with_actuals = [p for p in projections if p.actual_total is not None]

        if not years_with_actuals:
            return {"has_actuals": False, "message": "No actual costs have been recorded yet"}

        total_projected = sum(p.year_total or Decimal("0") for p in years_with_actuals)
        total_actual = sum(p.actual_total or Decimal("0") for p in years_with_actuals)
        total_variance = total_actual - total_projected
        variance_percentage = (
            float(total_variance / total_projected * 100) if total_projected > 0 else 0
        )

        yearly_analysis = []
        for p in years_with_actuals:
            projected = p.year_total or Decimal("0")
            actual = p.actual_total or Decimal("0")
            variance = p.variance or (actual - projected)
            pct = float(variance / projected * 100) if projected > 0 else 0

            yearly_analysis.append(
                {
                    "year": p.year,
                    "projected": float(projected),
                    "actual": float(actual),
                    "variance": float(variance),
                    "variance_percentage": pct,
                    "explanation": p.variance_explanation,
                    "status": "over_budget"
                    if variance > 0
                    else "under_budget"
                    if variance < 0
                    else "on_budget",
                }
            )

        return {
            "has_actuals": True,
            "years_analyzed": len(years_with_actuals),
            "total_projected": float(total_projected),
            "total_actual": float(total_actual),
            "total_variance": float(total_variance),
            "variance_percentage": variance_percentage,
            "overall_status": "over_budget"
            if total_variance > 0
            else "under_budget"
            if total_variance < 0
            else "on_budget",
            "yearly_analysis": yearly_analysis,
        }
