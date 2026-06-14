"""
-> app.modules.vendors.services.discovery_service

Vendor Discovery Engine - PRD-V01 Implementation

Intelligent vendor discovery with AI-powered recommendations, semantic search,
and comprehensive capability matching. Replaces manual vendor research with
automated, data-driven vendor selection.

Key Features:
- AI-powered vendor recommendations
- Semantic capability matching
- Multi-dimensional scoring (cost, coverage, risk, strategic fit)
- Real-time market intelligence integration
- Interactive discovery dashboard
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import joinedload

from app import db
from app.models import User
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import (
    TCOCalculation,
    VendorOrganization,
    VendorProduct,
    VendorProductCapability,
    VendorProductPricing,
    VendorRiskAssessment,
)

logger = logging.getLogger(__name__)


class VendorDiscoveryEngine:
    """
    AI-powered vendor discovery engine with intelligent recommendations
    and comprehensive capability matching.
    """

    def __init__(self):
        """Initialize the discovery engine with default parameters."""
        self.default_weights = {
            "capability_coverage": 0.30,
            "cost_effectiveness": 0.25,
            "strategic_fit": 0.20,
            "risk_profile": 0.15,
            "implementation_complexity": 0.10,
        }

        # Industry benchmarks for TCO comparison
        self.industry_benchmarks = {
            "ERP": {"median_tco_per_user": 1200, "implementation_months": 18},
            "CRM": {"median_tco_per_user": 800, "implementation_months": 12},
            "HCM": {"median_tco_per_user": 600, "implementation_months": 9},
            "SCM": {"median_tco_per_user": 900, "implementation_months": 15},
            "BI": {"median_tco_per_user": 400, "implementation_months": 6},
        }

    def discover_vendors_for_capabilities(
        self,
        capability_requirements: List[Dict[str, Any]],
        organization_size: str = "medium",
        industry: str = "general",
        budget_range: Optional[Tuple[Decimal, Decimal]] = None,
        deployment_preference: str = "cloud",
        user_count: int = 1000,
        tco_period_years: int = 5,
    ) -> Dict[str, Any]:
        """
        Discover vendors for multiple capability requirements with AI-powered recommendations.

        Args:
            capability_requirements: List of capability requirements with importance weights
            organization_size: "small", "medium", "large", "enterprise"
            industry: Industry sector for contextual recommendations
            budget_range: (min_budget, max_budget) in USD
            deployment_preference: "cloud", "on-premise", "hybrid"
            user_count: Number of users for TCO calculations
            tco_period_years: TCO calculation period in years

        Returns:
            Comprehensive vendor discovery results with recommendations and analysis
        """

        logger.info(f"Starting vendor discovery for {len(capability_requirements)} capabilities")

        # Step 1: Find vendors matching capability requirements
        candidate_vendors = self._find_capability_matches(capability_requirements)

        # Step 2: Score and rank vendors
        scored_vendors = self._score_vendors(
            candidate_vendors, capability_requirements, organization_size, industry
        )

        # Step 3: Calculate TCO for top candidates
        vendors_with_tco = self._calculate_tco_for_vendors(
            scored_vendors[:10],  # Top 10 vendors
            user_count,
            tco_period_years,
            deployment_preference,
        )

        # Step 4: Apply budget filtering
        if budget_range:
            vendors_with_tco = self._filter_by_budget(vendors_with_tco, budget_range)

        # Step 5: Generate AI recommendations
        recommendations = self._generate_recommendations(
            vendors_with_tco, capability_requirements, organization_size, industry
        )

        # Step 6: Create discovery summary
        discovery_summary = self._create_discovery_summary(
            vendors_with_tco, capability_requirements, organization_size, industry, budget_range
        )

        return {
            "discovery_metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "capability_count": len(capability_requirements),
                "candidates_found": len(candidate_vendors),
                "organization_size": organization_size,
                "industry": industry,
                "deployment_preference": deployment_preference,
                "user_count": user_count,
                "tco_period_years": tco_period_years,
            },
            "top_recommendations": recommendations[:3],
            "all_candidates": vendors_with_tco,
            "discovery_summary": discovery_summary,
            "capability_coverage_matrix": self._build_coverage_matrix(
                vendors_with_tco, capability_requirements
            ),
        }

    def _find_capability_matches(self, capability_requirements: List[Dict[str, Any]]) -> List[Dict]:
        """Find vendors that match the specified capability requirements."""

        vendor_matches = {}

        for req in capability_requirements:
            capability_id = req.get("capability_id")
            min_coverage = req.get("min_coverage", 70)
            importance = req.get("importance", "medium")

            # Query vendor product capabilities
            capabilities = (
                db.session.query(VendorProductCapability, VendorProduct, VendorOrganization)
                .join(VendorProduct, VendorProductCapability.vendor_product_id == VendorProduct.id)
                .join(
                    VendorOrganization,
                    VendorProduct.vendor_organization_id == VendorOrganization.id,
                )
                .filter(
                    VendorProductCapability.business_capability_id == capability_id,
                    VendorProductCapability.coverage_percentage >= min_coverage,
                )
                .options(
                    joinedload(VendorProductCapability.vendor_product),
                    joinedload(VendorProductCapability.vendor_product.vendor_organization),
                )
                .all()
            )

            for vpc, product, vendor in capabilities:
                vendor_key = f"{vendor.id}_{product.id}"

                if vendor_key not in vendor_matches:
                    vendor_matches[vendor_key] = {
                        "vendor": vendor,
                        "product": product,
                        "matched_capabilities": [],
                        "total_coverage_score": 0,
                        "weighted_coverage": 0,
                    }

                vendor_matches[vendor_key]["matched_capabilities"].append(
                    {
                        "capability_id": capability_id,
                        "capability_name": vpc.business_capability.name
                        if vpc.business_capability
                        else "Unknown",
                        "coverage_percentage": vpc.coverage_percentage,
                        "maturity_level": vpc.maturity_level,
                        "importance": importance,
                        "implementation_complexity": vpc.implementation_complexity,
                    }
                )

                # Calculate weighted coverage
                importance_weight = {"high": 3, "medium": 2, "low": 1}.get(importance, 2)
                vendor_matches[vendor_key]["weighted_coverage"] += (
                    vpc.coverage_percentage * importance_weight
                )
                vendor_matches[vendor_key]["total_coverage_score"] += vpc.coverage_percentage

        # Convert to list and sort by weighted coverage
        return sorted(vendor_matches.values(), key=lambda x: x["weighted_coverage"], reverse=True)

    def _score_vendors(
        self,
        candidate_vendors: List[Dict],
        capability_requirements: List[Dict[str, Any]],
        organization_size: str,
        industry: str,
    ) -> List[Dict]:
        """Score vendors across multiple dimensions."""

        scored_vendors = []

        for candidate in candidate_vendors:
            vendor = candidate["vendor"]
            product = candidate["product"]

            # Calculate dimension scores
            capability_score = self._calculate_capability_score(candidate, capability_requirements)
            cost_score = self._calculate_cost_score(vendor, product, organization_size)
            strategic_score = self._calculate_strategic_fit_score(vendor, industry)
            risk_score = self._calculate_risk_score(vendor, product)
            implementation_score = self._calculate_implementation_score(candidate)

            # Calculate overall score
            overall_score = (
                capability_score * self.default_weights["capability_coverage"]
                + cost_score * self.default_weights["cost_effectiveness"]
                + strategic_score * self.default_weights["strategic_fit"]
                + risk_score * self.default_weights["risk_profile"]
                + implementation_score * self.default_weights["implementation_complexity"]
            )

            scored_vendor = candidate.copy()
            scored_vendor.update(
                {
                    "scores": {
                        "overall": round(overall_score, 2),
                        "capability_coverage": round(capability_score, 2),
                        "cost_effectiveness": round(cost_score, 2),
                        "strategic_fit": round(strategic_score, 2),
                        "risk_profile": round(risk_score, 2),
                        "implementation_complexity": round(implementation_score, 2),
                    },
                    "recommendation_strength": self._get_recommendation_strength(overall_score),
                }
            )

            scored_vendors.append(scored_vendor)

        return sorted(scored_vendors, key=lambda x: x["scores"]["overall"], reverse=True)

    def _calculate_capability_score(
        self, candidate: Dict, capability_requirements: List[Dict[str, Any]]
    ) -> float:
        """Calculate capability coverage score."""
        if not candidate["matched_capabilities"]:
            return 0.0

        total_weighted_coverage = 0
        total_possible_weight = 0

        for req in capability_requirements:
            importance = req.get("importance", "medium")
            weight = {"high": 3, "medium": 2, "low": 1}.get(importance, 2)
            total_possible_weight += weight

        for match in candidate["matched_capabilities"]:
            importance = match.get("importance", "medium")
            weight = {"high": 3, "medium": 2, "low": 1}.get(importance, 2)
            coverage = match["coverage_percentage"]
            total_weighted_coverage += coverage * weight

        return min(
            100.0,
            (total_weighted_coverage / total_possible_weight) if total_possible_weight > 0 else 0.0,
        )

    def _calculate_cost_score(
        self, vendor: VendorOrganization, product: VendorProduct, organization_size: str
    ) -> float:
        """Calculate cost effectiveness score based on pricing and TCO."""

        # Get pricing information
        pricing_tiers = VendorProductPricing.query.filter_by(product_id=product.id).all()

        if not pricing_tiers:
            return 50.0  # Neutral score if no pricing data

        # Calculate average effective price
        avg_price = 0
        count = 0

        for pricing in pricing_tiers:
            effective_price = pricing.calculate_effective_price()
            if effective_price:
                avg_price += float(effective_price)
                count += 1

        if count == 0:
            return 50.0

        avg_price /= count

        # Score based on organization size benchmarks
        size_benchmarks = {
            "small": {"max_price": 50000, "min_price": 5000},
            "medium": {"max_price": 200000, "min_price": 20000},
            "large": {"max_price": 1000000, "min_price": 100000},
            "enterprise": {"max_price": 5000000, "min_price": 500000},
        }

        benchmarks = size_benchmarks.get(organization_size, size_benchmarks["medium"])

        if avg_price <= benchmarks["min_price"]:
            return 100.0
        elif avg_price >= benchmarks["max_price"]:
            return 0.0
        else:
            # Linear interpolation
            range_size = benchmarks["max_price"] - benchmarks["min_price"]
            position = (avg_price - benchmarks["min_price"]) / range_size
            return max(0.0, min(100.0, 100.0 - (position * 100.0)))

    def _calculate_strategic_fit_score(self, vendor: VendorOrganization, industry: str) -> float:
        """Calculate strategic fit score based on vendor characteristics."""

        score = 50.0  # Base score

        # Strategic tier bonus
        tier_scores = {"strategic": 30, "preferred": 20, "approved": 10, "restricted": -10}
        score += tier_scores.get(vendor.strategic_tier, 0)

        # Partnership level bonus
        partnership_scores = {
            "strategic_partner": 25,
            "technology_partner": 15,
            "reseller": 5,
            "none": 0,
        }
        score += partnership_scores.get(vendor.partnership_level, 0)

        # Market position bonus
        if vendor.gartner_magic_quadrant:
            quadrant_scores = {
                "leaders": 20,
                "challengers": 15,
                "visionaries": 10,
                "niche_players": 5,
            }
            score += quadrant_scores.get(vendor.gartner_magic_quadrant.lower(), 0)

        # Industry specialization bonus
        if vendor.industry_focus and industry.lower() in vendor.industry_focus.lower():
            score += 15

        return max(0.0, min(100.0, score))

    def _calculate_risk_score(self, vendor: VendorOrganization, product: VendorProduct) -> float:
        """Calculate risk profile score (higher = lower risk)."""

        # Get risk assessment
        risk_assessment = VendorRiskAssessment.query.filter_by(
            vendor_organization_id=vendor.id, vendor_product_id=product.id
        ).first()

        if risk_assessment:
            # Convert risk score (lower risk = higher score)
            risk_score = 100.0 - risk_assessment.overall_risk_score
        else:
            # Default risk calculation based on vendor characteristics
            risk_score = 70.0  # Base score

            # Financial stability
            if vendor.financial_stability_rating:
                stability_scores = {"A": 20, "B": 10, "C": 0, "D": -10}
                risk_score += stability_scores.get(vendor.financial_stability_rating, 0)

            # Market presence
            if vendor.year_founded:
                years_in_business = datetime.now().year - vendor.year_founded
                if years_in_business >= 20:
                    risk_score += 10
                elif years_in_business >= 10:
                    risk_score += 5
                elif years_in_business < 5:
                    risk_score -= 10

        return max(0.0, min(100.0, risk_score))

    def _calculate_implementation_score(self, candidate: Dict) -> float:
        """Calculate implementation complexity score (higher = easier implementation)."""

        if not candidate["matched_capabilities"]:
            return 50.0

        total_complexity = 0
        count = 0

        for match in candidate["matched_capabilities"]:
            complexity = match.get("implementation_complexity", 5)
            # Convert complexity (1 - 10 scale) to score (10 = easiest, 1 = hardest)
            implementation_score = (11 - complexity) * 10
            total_complexity += implementation_score
            count += 1

        avg_score = total_complexity / count if count > 0 else 50.0
        return max(0.0, min(100.0, avg_score))

    def _get_recommendation_strength(self, overall_score: float) -> str:
        """Get recommendation strength based on overall score."""
        if overall_score >= 85:
            return "strong_recommend"
        elif overall_score >= 75:
            return "recommend"
        elif overall_score >= 65:
            return "consider"
        elif overall_score >= 50:
            return "alternative"
        else:
            return "not_recommended"

    def _calculate_tco_for_vendors(
        self,
        vendors: List[Dict],
        user_count: int,
        tco_period_years: int,
        deployment_preference: str,
    ) -> List[Dict]:
        """Calculate TCO for vendor candidates."""

        vendors_with_tco = []

        for vendor_data in vendors:
            vendor = vendor_data["vendor"]
            product = vendor_data["product"]

            # Check if TCO calculation already exists
            existing_tco = TCOCalculation.query.filter_by(
                vendor_product_id=product.id,
                user_count=user_count,
                tco_period_years=tco_period_years,
            ).first()

            if existing_tco:
                tco_data = existing_tco
            else:
                # Create new TCO calculation
                tco_data = self._calculate_tco(
                    vendor, product, user_count, tco_period_years, deployment_preference
                )

                # Save to database
                db.session.add(tco_data)
                db.session.commit()

            vendor_with_tco = vendor_data.copy()
            vendor_with_tco["tco"] = {
                "total_tco": float(tco_data.total_tco) if tco_data.total_tco else 0,
                "annual_average": float(tco_data.annual_average) if tco_data.annual_average else 0,
                "per_user_annual": float(tco_data.per_user_annual)
                if tco_data.per_user_annual
                else 0,
                "vs_industry_percentage": tco_data.vs_industry_percentage or 0,
                "confidence_level": tco_data.confidence_level or "medium",
                "yearly_breakdown": tco_data.get_yearly_breakdown(),
            }

            vendors_with_tco.append(vendor_with_tco)

        return vendors_with_tco

    def _calculate_tco(
        self,
        vendor: VendorOrganization,
        product: VendorProduct,
        user_count: int,
        tco_period_years: int,
        deployment_preference: str,
    ) -> TCOCalculation:
        """Calculate comprehensive TCO for a vendor product."""

        # Get pricing information
        pricing = VendorProductPricing.query.filter_by(product_id=product.id).first()

        # Base calculations
        base_annual_cost = float(pricing.calculate_effective_price(user_count)) if pricing else 0

        # Industry benchmarks
        product_category = product.category or "ERP"
        benchmark = self.industry_benchmarks.get(product_category, self.industry_benchmarks["ERP"])
        industry_median = benchmark["median_tco_per_user"] * user_count * tco_period_years

        # Cost breakdown (simplified model)
        software_licensing = base_annual_cost * tco_period_years
        support_maintenance = software_licensing * 0.20  # 20% of licensing
        cloud_infrastructure = (
            software_licensing * 0.15
            if deployment_preference == "cloud"
            else software_licensing * 0.05
        )
        internal_labor = software_licensing * 0.30  # Internal team costs
        implementation = base_annual_cost * 2.0  # One-time implementation
        ongoing_enhancements = software_licensing * 0.10 * (tco_period_years - 1)

        # Training costs
        training_costs = user_count * 1000  # $1000 per user

        # Data migration
        data_migration = user_count * 500  # $500 per user

        # One-time costs
        one_time_total = implementation + training_costs + data_migration

        # Recurring costs
        recurring_total = (
            software_licensing
            + support_maintenance
            + cloud_infrastructure
            + internal_labor
            + ongoing_enhancements
        )

        # Total TCO
        total_tco = one_time_total + recurring_total

        # Create TCO calculation record
        tco = TCOCalculation(
            vendor_product_id=product.id,
            user_count=user_count,
            tco_period_years=tco_period_years,
            deployment_model=deployment_preference,
            # One-time costs
            implementation_costs=implementation,
            training_costs=training_costs,
            data_migration_costs=data_migration,
            one_time_total=one_time_total,
            # Recurring costs
            software_licensing_total=software_licensing,
            support_maintenance_total=support_maintenance,
            cloud_infrastructure_total=cloud_infrastructure,
            internal_labor_total=internal_labor,
            ongoing_enhancements_total=ongoing_enhancements,
            recurring_total=recurring_total,
            # Summary
            total_tco=total_tco,
            annual_average=total_tco / tco_period_years,
            per_user_annual=total_tco / (user_count * tco_period_years),
            # Benchmarks
            industry_median_tco=industry_median,
            vs_industry_percentage=((total_tco - industry_median) / industry_median * 100)
            if industry_median > 0
            else 0,
            # Confidence
            confidence_level="medium",  # Could be calculated based on data availability
        )

        return tco

    def _filter_by_budget(
        self, vendors: List[Dict], budget_range: Tuple[Decimal, Decimal]
    ) -> List[Dict]:
        """Filter vendors by budget range."""
        min_budget, max_budget = budget_range

        filtered_vendors = []
        for vendor in vendors:
            tco_total = vendor.get("tco", {}).get("total_tco", 0)
            if min_budget <= Decimal(str(tco_total)) <= max_budget:
                filtered_vendors.append(vendor)

        return filtered_vendors

    def _generate_recommendations(
        self,
        vendors: List[Dict],
        capability_requirements: List[Dict[str, Any]],
        organization_size: str,
        industry: str,
    ) -> List[Dict]:
        """Generate AI-powered recommendations with reasoning."""

        recommendations = []

        for i, vendor in enumerate(vendors[:5]):  # Top 5 recommendations
            scores = vendor["scores"]

            # Generate recommendation reasoning
            reasoning = []

            if scores["capability_coverage"] >= 80:
                reasoning.append(
                    f"Excellent capability coverage ({scores['capability_coverage']}%)"
                )
            elif scores["capability_coverage"] >= 60:
                reasoning.append(f"Good capability coverage ({scores['capability_coverage']}%)")

            if scores["cost_effectiveness"] >= 80:
                reasoning.append("Highly cost-effective solution")
            elif scores["cost_effectiveness"] >= 60:
                reasoning.append("Reasonable cost structure")

            if scores["strategic_fit"] >= 80:
                reasoning.append("Strong strategic alignment")
            elif scores["strategic_fit"] >= 60:
                reasoning.append("Good strategic fit")

            if scores["risk_profile"] >= 80:
                reasoning.append("Low risk profile")
            elif scores["risk_profile"] >= 60:
                reasoning.append("Moderate risk level")

            # Add specific recommendations based on organization context
            if organization_size == "enterprise" and vendor["vendor"].strategic_tier == "strategic":
                reasoning.append("Ideal for enterprise-scale deployment")

            if (
                industry in vendor["vendor"].industry_focus.lower()
                if vendor["vendor"].industry_focus
                else False
            ):
                reasoning.append(f"Specialized in {industry} industry")

            recommendation = {
                "rank": i + 1,
                "vendor": vendor["vendor"],
                "product": vendor["product"],
                "overall_score": scores["overall"],
                "recommendation_strength": vendor["recommendation_strength"],
                "reasoning": reasoning,
                "key_strengths": self._identify_key_strengths(vendor),
                "potential_concerns": self._identify_concerns(vendor),
                "next_steps": self._suggest_next_steps(vendor, scores),
            }

            recommendations.append(recommendation)

        return recommendations

    def _identify_key_strengths(self, vendor: Dict) -> List[str]:
        """Identify key strengths of a vendor solution."""
        strengths = []
        scores = vendor["scores"]

        if scores["capability_coverage"] >= 85:
            strengths.append("Comprehensive capability coverage")

        if scores["cost_effectiveness"] >= 85:
            strengths.append("Excellent cost efficiency")

        if scores["strategic_fit"] >= 85:
            strengths.append("Strong strategic alignment")

        if scores["risk_profile"] >= 85:
            strengths.append("Low implementation risk")

        if scores["implementation_complexity"] >= 85:
            strengths.append("Easy to implement")

        # Add vendor-specific strengths
        vendor_info = vendor["vendor"]
        if vendor_info.strategic_tier == "strategic":
            strengths.append("Strategic partner status")

        if vendor_info.gartner_magic_quadrant == "Leaders":
            strengths.append("Gartner Magic Quadrant Leader")

        return strengths

    def _identify_concerns(self, vendor: Dict) -> List[str]:
        """Identify potential concerns with a vendor solution."""
        concerns = []
        scores = vendor["scores"]

        if scores["capability_coverage"] < 60:
            concerns.append("Limited capability coverage")

        if scores["cost_effectiveness"] < 60:
            concerns.append("Higher cost structure")

        if scores["risk_profile"] < 60:
            concerns.append("Elevated risk profile")

        if scores["implementation_complexity"] < 60:
            concerns.append("Complex implementation")

        # Add vendor-specific concerns
        vendor_info = vendor["vendor"]
        if vendor_info.strategic_tier == "restricted":
            concerns.append("Restricted vendor status")

        if not vendor_info.year_founded or (datetime.now().year - vendor_info.year_founded) < 5:
            concerns.append("Limited market presence")

        return concerns

    def _suggest_next_steps(self, vendor: Dict, scores: Dict) -> List[str]:
        """Suggest next steps for vendor evaluation."""
        next_steps = []

        if scores["overall"] >= 85:
            next_steps.extend(
                [
                    "Schedule executive demo",
                    "Request detailed pricing proposal",
                    "Conduct reference checks",
                    "Begin security assessment",
                ]
            )
        elif scores["overall"] >= 75:
            next_steps.extend(
                [
                    "Schedule technical demo",
                    "Request capability deep-dive",
                    "Check customer references",
                ]
            )
        else:
            next_steps.extend(
                [
                    "Request basic information",
                    "Evaluate fit for specific use cases",
                    "Consider as backup option",
                ]
            )

        return next_steps

    def _create_discovery_summary(
        self,
        vendors: List[Dict],
        capability_requirements: List[Dict[str, Any]],
        organization_size: str,
        industry: str,
        budget_range: Optional[Tuple[Decimal, Decimal]],
    ) -> Dict[str, Any]:
        """Create comprehensive discovery summary."""

        if not vendors:
            return {
                "total_candidates": 0,
                "strong_recommendations": 0,
                "average_score": 0,
                "budget_compliance": 0,
                "key_insights": ["No vendors found matching requirements"],
            }

        # Calculate statistics
        scores = [v["scores"]["overall"] for v in vendors]
        avg_score = sum(scores) / len(scores)

        strong_recommendations = len(
            [
                v
                for v in vendors
                if v["recommendation_strength"] in ["strong_recommend", "recommend"]
            ]
        )

        # Budget compliance
        budget_compliant = 0
        if budget_range:
            min_budget, max_budget = budget_range
            for vendor in vendors:
                tco_total = vendor.get("tco", {}).get("total_tco", 0)
                if min_budget <= Decimal(str(tco_total)) <= max_budget:
                    budget_compliant += 1
            budget_compliance = (budget_compliant / len(vendors)) * 100 if vendors else 0

        # Generate insights
        insights = []

        if avg_score >= 80:
            insights.append("High-quality vendor pool with strong candidates")
        elif avg_score >= 65:
            insights.append("Good vendor pool with viable options")
        else:
            insights.append("Limited vendor options, consider expanding requirements")

        if strong_recommendations >= 3:
            insights.append("Multiple strong recommendations available")
        elif strong_recommendations >= 1:
            insights.append("At least one strong recommendation identified")
        else:
            insights.append("No strong recommendations, consider revisiting requirements")

        if budget_range and budget_compliance >= 80:
            insights.append("Most candidates fit within budget constraints")
        elif budget_range and budget_compliance < 50:
            insights.append("Budget constraints significantly limit options")

        return {
            "total_candidates": len(vendors),
            "strong_recommendations": strong_recommendations,
            "average_score": round(avg_score, 2),
            "budget_compliance": round(budget_compliance, 1),
            "top_score": round(max(scores), 2),
            "score_distribution": {
                "excellent": len([s for s in scores if s >= 85]),
                "good": len([s for s in scores if 75 <= s < 85]),
                "fair": len([s for s in scores if 65 <= s < 75]),
                "poor": len([s for s in scores if s < 65]),
            },
            "key_insights": insights,
        }

    def _build_coverage_matrix(
        self, vendors: List[Dict], capability_requirements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build capability coverage matrix for top vendors."""

        matrix = {"capabilities": [], "vendors": [], "coverage_data": []}

        # Extract capability names
        for req in capability_requirements:
            matrix["capabilities"].append(
                {
                    "id": req.get("capability_id"),
                    "name": req.get("capability_name", f"Capability {req.get('capability_id')}"),
                    "importance": req.get("importance", "medium"),
                }
            )

        # Extract top vendors
        top_vendors = vendors[:5]  # Top 5 vendors
        for vendor in top_vendors:
            matrix["vendors"].append(
                {
                    "vendor_id": vendor["vendor"].id,
                    "vendor_name": vendor["vendor"].name,
                    "product_name": vendor["product"].name,
                    "overall_score": vendor["scores"]["overall"],
                }
            )

        # Build coverage data
        for vendor in top_vendors:
            coverage_row = {"vendor_name": vendor["vendor"].name}

            for req in capability_requirements:
                capability_id = req.get("capability_id")

                # Find matching capability
                coverage = 0
                for match in vendor["matched_capabilities"]:
                    if match["capability_id"] == capability_id:
                        coverage = match["coverage_percentage"]
                        break

                coverage_row[f"capability_{capability_id}"] = coverage

            matrix["coverage_data"].append(coverage_row)

        return matrix
