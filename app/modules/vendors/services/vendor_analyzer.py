"""
-> app.modules.vendors.services.analysis_service

Vendor Analysis Service

Comprehensive vendor analysis including:
- Capability coverage analysis
- Process coverage metrics (APQC)
- Technology stack analysis
- Integration complexity scoring
- Recommendations and insights
"""

import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy import distinct, func

from app import db
from app.exceptions import DatabaseError, NotFoundError
from app.models.apqc_process import APQCProcess
from app.models.business_capabilities import BusinessCapability
from app.models.vendor.vendor_organization import (
    VendorOrganization,
    VendorProduct,
    VendorProductCapability,
)
from app.models.vendor_product_apqc_mapping import VendorProductAPQCMapping

logger = logging.getLogger(__name__)


class VendorAnalyzer:
    """
    Analyzes vendor capabilities, process coverage, and integration complexity.
    """

    def __init__(self):
        self.logger = logger

    def analyze_vendor(self, vendor_id: int) -> Dict:
        """
        Perform comprehensive vendor analysis.

        Args:
            vendor_id: ID of the vendor organization to analyze

        Returns:
            Dictionary containing analysis results with scores, metrics, and recommendations

        Raises:
            NotFoundError: If vendor not found
            DatabaseError: If database query fails
        """
        try:
            # Get vendor
            vendor = VendorOrganization.query.get(vendor_id)
            if not vendor:
                raise NotFoundError(
                    f"Vendor with ID {vendor_id} not found",
                    user_message="The requested vendor could not be found.",
                    recovery_action="Please check the vendor ID and try again.",
                )

            # Perform analysis
            capability_analysis = self._analyze_capability_coverage(vendor_id)
            process_analysis = self._analyze_process_coverage(vendor_id)
            tech_analysis = self._analyze_technology_stack(vendor_id)
            integration_score = self._calculate_integration_complexity(vendor_id)
            recommendations = self._generate_recommendations(
                vendor, capability_analysis, process_analysis, integration_score
            )

            return {
                "success": True,
                "vendor_id": vendor_id,
                "vendor_name": vendor.name,
                "capability_coverage": capability_analysis,
                "process_coverage": process_analysis,
                "technology_stack": tech_analysis,
                "integration_complexity": integration_score,
                "recommendations": recommendations,
                "overall_score": self._calculate_overall_score(
                    capability_analysis, process_analysis, integration_score
                ),
            }

        except NotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Error analyzing vendor {vendor_id}: {str(e)}", exc_info=True)
            raise DatabaseError(
                f"Failed to analyze vendor: {str(e)}",
                user_message="An error occurred while analyzing the vendor.",
                recovery_action="Please try again. If the problem persists, contact support.",
            )

    def _analyze_capability_coverage(self, vendor_id: int) -> Dict:
        """
        Analyze capability coverage for vendor products.

        Returns:
            Dict with coverage percentage, supported capabilities, and gap analysis
        """
        try:
            # Get all vendor products for this vendor
            vendor_products = VendorProduct.query.filter_by(vendor_organization_id=vendor_id).all()

            if not vendor_products:
                return {
                    "coverage_percentage": 0,
                    "total_capabilities": 0,
                    "covered_capabilities": 0,
                    "average_fit_score": 0,
                    "top_capabilities": [],
                    "gaps": [],
                }

            product_ids = [p.id for p in vendor_products]

            # Get total business capabilities
            total_capabilities = BusinessCapability.query.count()

            # Get covered capabilities with scores
            coverage_data = (
                db.session.query(
                    VendorProductCapability.business_capability_id,
                    func.max(VendorProductCapability.coverage_percentage).label("max_coverage"),
                    func.max(VendorProductCapability.fit_score).label("max_fit"),
                    BusinessCapability.name,
                )
                .join(
                    BusinessCapability,
                    VendorProductCapability.business_capability_id == BusinessCapability.id,
                )
                .filter(VendorProductCapability.vendor_product_id.in_(product_ids))
                .group_by(VendorProductCapability.business_capability_id, BusinessCapability.name)
                .all()
            )

            covered_capabilities = len(coverage_data)
            coverage_percentage = (
                (covered_capabilities / total_capabilities * 100) if total_capabilities > 0 else 0
            )

            # Calculate average fit score
            fit_scores = [row.max_fit for row in coverage_data if row.max_fit is not None]
            average_fit_score = sum(fit_scores) / len(fit_scores) if fit_scores else 0

            # Get top capabilities (sorted by coverage and fit)
            top_capabilities = [
                {
                    "capability_id": row.business_capability_id,
                    "name": row.name,
                    "coverage_percentage": float(row.max_coverage or 0),
                    "fit_score": float(row.max_fit or 0),
                }
                for row in sorted(
                    coverage_data,
                    key=lambda x: (x.max_coverage or 0) + (x.max_fit or 0),
                    reverse=True,
                )[:10]
            ]

            # Identify gaps (capabilities with low coverage)
            gaps = [
                {
                    "capability_id": row.business_capability_id,
                    "name": row.name,
                    "coverage_percentage": float(row.max_coverage or 0),
                    "fit_score": float(row.max_fit or 0),
                }
                for row in coverage_data
                if (row.max_coverage or 0) < 50
            ][:10]

            return {
                "coverage_percentage": round(coverage_percentage, 2),
                "total_capabilities": total_capabilities,
                "covered_capabilities": covered_capabilities,
                "average_fit_score": round(average_fit_score, 2),
                "top_capabilities": top_capabilities,
                "gaps": gaps,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing capability coverage: {str(e)}", exc_info=True)
            raise

    def _analyze_process_coverage(self, vendor_id: int) -> Dict:
        """
        Analyze APQC process coverage.

        Returns:
            Dict with process coverage metrics
        """
        try:
            # Get vendor products
            vendor_products = VendorProduct.query.filter_by(vendor_organization_id=vendor_id).all()

            if not vendor_products:
                return {
                    "coverage_percentage": 0,
                    "total_processes": 0,
                    "covered_processes": 0,
                    "supported_process_groups": [],
                }

            product_ids = [p.id for p in vendor_products]

            # Get total APQC processes
            total_processes = APQCProcess.query.count()

            # Get covered processes
            covered_process_ids = (
                db.session.query(distinct(VendorProductAPQCMapping.apqc_process_id))
                .filter(VendorProductAPQCMapping.vendor_product_id.in_(product_ids))
                .all()
            )
            covered_processes = len(covered_process_ids)

            coverage_percentage = (
                (covered_processes / total_processes * 100) if total_processes > 0 else 0
            )

            # Get process groups with coverage
            process_groups = (
                db.session.query(
                    APQCProcess.category_level_1,
                    func.count(distinct(APQCProcess.id)).label("process_count"),
                )
                .join(
                    VendorProductAPQCMapping,
                    APQCProcess.id == VendorProductAPQCMapping.apqc_process_id,
                )
                .filter(VendorProductAPQCMapping.vendor_product_id.in_(product_ids))
                .filter(APQCProcess.category_level_1.isnot(None))
                .group_by(APQCProcess.category_level_1)
                .all()
            )

            supported_process_groups = [
                {"name": group[0], "process_count": group[1]} for group in process_groups
            ]

            return {
                "coverage_percentage": round(coverage_percentage, 2),
                "total_processes": total_processes,
                "covered_processes": covered_processes,
                "supported_process_groups": supported_process_groups,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing process coverage: {str(e)}", exc_info=True)
            raise

    def _analyze_technology_stack(self, vendor_id: int) -> Dict:
        """
        Analyze technology stack and deployment models.

        Returns:
            Dict with technology components
        """
        try:
            vendor_products = VendorProduct.query.filter_by(vendor_organization_id=vendor_id).all()

            if not vendor_products:
                return {
                    "product_count": 0,
                    "deployment_models": [],
                    "licensing_models": [],
                    "technologies": [],
                    "api_enabled_count": 0,
                }

            # Aggregate deployment models
            deployment_models = {}
            licensing_models = {}
            technologies = {}
            api_enabled_count = 0

            for product in vendor_products:
                # Deployment models
                if product.deployment_model:
                    deployment_models[product.deployment_model] = (
                        deployment_models.get(product.deployment_model, 0) + 1
                    )

                # Licensing models
                if product.licensing_model:
                    licensing_models[product.licensing_model] = (
                        licensing_models.get(product.licensing_model, 0) + 1
                    )

                # Technologies
                if product.primary_technology:
                    technologies[product.primary_technology] = (
                        technologies.get(product.primary_technology, 0) + 1
                    )

                # API availability
                if product.api_availability:
                    api_enabled_count += 1

            return {
                "product_count": len(vendor_products),
                "deployment_models": [
                    {"model": k, "count": v} for k, v in deployment_models.items()
                ],
                "licensing_models": [{"model": k, "count": v} for k, v in licensing_models.items()],
                "technologies": [{"technology": k, "count": v} for k, v in technologies.items()],
                "api_enabled_count": api_enabled_count,
                "api_enabled_percentage": round((api_enabled_count / len(vendor_products) * 100), 2)
                if vendor_products
                else 0,
            }

        except Exception as e:
            self.logger.error(f"Error analyzing technology stack: {str(e)}", exc_info=True)
            raise

    def _calculate_integration_complexity(self, vendor_id: int) -> Dict:
        """
        Calculate integration complexity score.

        Returns:
            Dict with complexity score and factors
        """
        try:
            vendor_products = VendorProduct.query.filter_by(vendor_organization_id=vendor_id).all()

            if not vendor_products:
                return {
                    "score": 0,
                    "level": "unknown",
                    "factors": [],
                }

            # Calculate complexity factors
            total_complexity = 0
            factors = []

            # Factor 1: API availability (lower complexity if APIs available)
            api_enabled = sum(1 for p in vendor_products if p.api_availability)
            api_ratio = api_enabled / len(vendor_products) if vendor_products else 0
            api_score = 100 - (api_ratio * 30)  # Max -30 points for full API coverage
            total_complexity += api_score
            factors.append(
                {
                    "name": "API Availability",
                    "score": round(100 - api_score, 2),
                    "impact": "negative" if api_ratio < 0.5 else "positive",
                }
            )

            # Factor 2: Deployment model diversity (more models = higher complexity)
            deployment_models = set(
                p.deployment_model for p in vendor_products if p.deployment_model
            )
            deployment_score = len(deployment_models) * 15  # +15 per deployment model
            total_complexity += deployment_score
            factors.append(
                {
                    "name": "Deployment Model Diversity",
                    "score": len(deployment_models),
                    "impact": "negative" if len(deployment_models) > 2 else "neutral",
                }
            )

            # Factor 3: Technology diversity (more technologies = higher complexity)
            technologies = set(
                p.primary_technology for p in vendor_products if p.primary_technology
            )
            tech_score = len(technologies) * 10  # +10 per technology
            total_complexity += tech_score
            factors.append(
                {
                    "name": "Technology Stack Diversity",
                    "score": len(technologies),
                    "impact": "negative" if len(technologies) > 3 else "neutral",
                }
            )

            # Factor 4: Product count (more products = higher complexity)
            product_score = min(len(vendor_products) * 5, 50)  # Cap at 50
            total_complexity += product_score
            factors.append(
                {
                    "name": "Product Portfolio Size",
                    "score": len(vendor_products),
                    "impact": "neutral",
                }
            )

            # Normalize to 0 - 100 scale
            normalized_score = min(total_complexity, 100)

            # Determine complexity level
            if normalized_score < 30:
                level = "low"
            elif normalized_score < 60:
                level = "medium"
            else:
                level = "high"

            return {
                "score": round(normalized_score, 2),
                "level": level,
                "factors": factors,
            }

        except Exception as e:
            self.logger.error(f"Error calculating integration complexity: {str(e)}", exc_info=True)
            raise

    def _generate_recommendations(
        self,
        vendor: VendorOrganization,
        capability_analysis: Dict,
        process_analysis: Dict,
        integration_score: Dict,
    ) -> List[Dict]:
        """
        Generate actionable recommendations based on analysis.

        Returns:
            List of recommendation dictionaries
        """
        recommendations = []

        # Capability recommendations
        if capability_analysis["coverage_percentage"] < 50:
            recommendations.append(
                {
                    "type": "capability_gap",
                    "severity": "high",
                    "title": "Low Capability Coverage",
                    "description": f"Vendor covers only {capability_analysis['coverage_percentage']:.1f}% of business capabilities.",
                    "action": "Consider complementary vendors or custom development for capability gaps.",
                }
            )
        elif capability_analysis["coverage_percentage"] > 80:
            recommendations.append(
                {
                    "type": "capability_strength",
                    "severity": "info",
                    "title": "Strong Capability Coverage",
                    "description": f"Vendor covers {capability_analysis['coverage_percentage']:.1f}% of business capabilities.",
                    "action": "Good strategic fit. Focus on implementation and integration planning.",
                }
            )

        # Process recommendations
        if process_analysis["coverage_percentage"] < 40:
            recommendations.append(
                {
                    "type": "process_gap",
                    "severity": "medium",
                    "title": "Limited Process Coverage",
                    "description": f"Only {process_analysis['coverage_percentage']:.1f}% of APQC processes are covered.",
                    "action": "Review process requirements and consider additional vendor solutions.",
                }
            )

        # Integration recommendations
        if integration_score["level"] == "high":
            recommendations.append(
                {
                    "type": "integration_complexity",
                    "severity": "high",
                    "title": "High Integration Complexity",
                    "description": "Vendor portfolio has high integration complexity.",
                    "action": "Plan for dedicated integration resources and consider middleware/iPaaS solutions.",
                }
            )
        elif integration_score["level"] == "low":
            recommendations.append(
                {
                    "type": "integration_simplicity",
                    "severity": "info",
                    "title": "Low Integration Complexity",
                    "description": "Vendor portfolio is relatively easy to integrate.",
                    "action": "Leverage vendor's integration capabilities for streamlined implementation.",
                }
            )

        # Vendor-specific recommendations
        if vendor.strategic_tier == "tier_1_strategic":
            recommendations.append(
                {
                    "type": "strategic_vendor",
                    "severity": "info",
                    "title": "Strategic Tier 1 Vendor",
                    "description": f"{vendor.name} is a Tier 1 strategic vendor.",
                    "action": "Leverage strategic partnership for preferential terms and support.",
                }
            )

        # Fit score recommendations
        if capability_analysis.get("average_fit_score", 0) < 60:
            recommendations.append(
                {
                    "type": "fit_score",
                    "severity": "medium",
                    "title": "Moderate Fit Score",
                    "description": f"Average capability fit score is {capability_analysis.get('average_fit_score', 0):.1f}.",
                    "action": "Evaluate customization requirements and total cost of ownership carefully.",
                }
            )

        return recommendations

    def _calculate_overall_score(
        self, capability_analysis: Dict, process_analysis: Dict, integration_score: Dict
    ) -> Dict:
        """
        Calculate overall vendor score.

        Returns:
            Dict with overall score and rating
        """
        # Weighted scoring
        capability_weight = 0.4
        process_weight = 0.3
        integration_weight = 0.3

        capability_score = capability_analysis["coverage_percentage"]
        process_score = process_analysis["coverage_percentage"]
        # Convert integration complexity to score (lower complexity = higher score)
        integration_complexity = integration_score["score"]
        integration_adjusted_score = 100 - integration_complexity

        overall_score = (
            capability_score * capability_weight
            + process_score * process_weight
            + integration_adjusted_score * integration_weight
        )

        # Determine rating
        if overall_score >= 80:
            rating = "excellent"
        elif overall_score >= 65:
            rating = "good"
        elif overall_score >= 50:
            rating = "fair"
        else:
            rating = "poor"

        return {
            "score": round(overall_score, 2),
            "rating": rating,
            "breakdown": {
                "capability": round(capability_score, 2),
                "process": round(process_score, 2),
                "integration": round(integration_adjusted_score, 2),
            },
        }
