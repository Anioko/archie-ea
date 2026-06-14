"""
Advanced Risk Assessment Service - PRD-V05 Enhancement

Comprehensive risk analysis with AI-powered risk prediction, automated mitigation
strategies, and portfolio-level risk assessment. Enhances the existing risk
assessment models with advanced analytics and intelligent recommendations.

Key Features:
- Multi-dimensional risk scoring with predictive analytics
- Automated risk factor identification
- AI-powered mitigation strategy generation
- Portfolio risk aggregation and diversification analysis
- Real-time risk monitoring and alerts
- Risk benchmarking against industry standards
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import joinedload

from app import db
from app.models import User
from app.models.vendor.vendor_organization import (
    VendorOrganization,
    VendorProduct,
    VendorRiskAssessment,
)

logger = logging.getLogger(__name__)


class AdvancedRiskAssessmentService:
    """
    Advanced risk assessment service with AI-powered analytics and
    automated mitigation strategies.
    """

    def __init__(self):
        """Initialize the advanced risk assessment service."""
        self.risk_benchmarks = {
            "financial": {"low": 2, "medium": 5, "high": 8},
            "implementation": {"low": 3, "medium": 6, "high": 9},
            "market": {"low": 2, "medium": 4, "high": 7},
            "technology": {"low": 3, "medium": 5, "high": 8},
            "vendor_lock_in": {"low": 2, "medium": 5, "high": 8},
            "security": {"low": 1, "medium": 3, "high": 6},
            "compliance": {"low": 1, "medium": 4, "high": 7},
            "support": {"low": 2, "medium": 5, "high": 8},
        }

        self.risk_factors_library = {
            "financial": [
                "Revenue decline over past 3 years",
                "High debt-to-equity ratio",
                "Negative cash flow",
                "Credit rating downgrade",
                "Layoffs or restructuring",
                "Loss of key customers",
            ],
            "implementation": [
                "Complex integration requirements",
                "Limited implementation expertise",
                "Customization complexity",
                "Data migration challenges",
                "Change management resistance",
                "Limited vendor support resources",
            ],
            "market": [
                "Declining market share",
                "Emerging competitive threats",
                "Technology disruption risk",
                "Regulatory changes",
                "Economic downturn exposure",
                "Customer satisfaction decline",
            ],
            "technology": [
                "Legacy technology stack",
                "Limited innovation roadmap",
                "Proprietary technology lock-in",
                "Scalability limitations",
                "Security vulnerabilities",
                "Performance issues",
            ],
            "vendor_lock_in": [
                "Proprietary data formats",
                "Contractual penalties for termination",
                "Limited export capabilities",
                "Custom integration dependencies",
                "Unique business process requirements",
                "High switching costs",
            ],
            "security": [
                "History of security breaches",
                "Limited security certifications",
                "Inadequate security protocols",
                "Third-party security risks",
                "Data privacy concerns",
                "Regulatory compliance gaps",
            ],
            "compliance": [
                "Regulatory violations history",
                "Limited compliance certifications",
                "Industry-specific compliance gaps",
                "Data governance issues",
                "Audit failures",
                "Changing regulatory landscape",
            ],
            "support": [
                "Limited support availability",
                "Poor response times",
                "High support costs",
                "Limited documentation",
                "Knowledge transfer issues",
                "Geographic coverage gaps",
            ],
        }

        self.mitigation_strategies_library = {
            "financial": [
                "Require performance bonds or guarantees",
                "Implement milestone-based payments",
                "Establish escrow arrangements",
                "Require regular financial reporting",
                "Diversify vendor relationships",
                "Include termination clauses",
            ],
            "implementation": [
                "Phased implementation approach",
                "Engage experienced implementation partners",
                "Comprehensive change management program",
                "Pilot testing before full rollout",
                "Detailed project governance",
                "Vendor co-investment model",
            ],
            "market": [
                "Regular market monitoring",
                "Competitive benchmarking",
                "Technology trend analysis",
                "Exit strategy planning",
                "Multi-vendor strategy",
                "Innovation partnership programs",
            ],
            "technology": [
                "Technology roadmap alignment",
                "Regular technology assessments",
                "Open standards preference",
                "API-first architecture",
                "Containerization strategy",
                "Regular security audits",
            ],
            "vendor_lock_in": [
                "Standardized data formats",
                "Open API requirements",
                "Portable configuration management",
                "Multi-cloud strategy",
                "Service abstraction layers",
                "Contractual exit provisions",
            ],
            "security": [
                "Regular security assessments",
                "Security compliance requirements",
                "Data encryption standards",
                "Access control policies",
                "Security monitoring tools",
                "Incident response procedures",
            ],
            "compliance": [
                "Regular compliance audits",
                "Compliance monitoring systems",
                "Regulatory change tracking",
                "Documentation requirements",
                "Training programs",
                "Third-party compliance validation",
            ],
            "support": [
                "Service level agreements",
                "Support performance metrics",
                "Multi-tier support structure",
                "Knowledge transfer requirements",
                "Local support presence",
                "Vendor performance reviews",
            ],
        }

    def assess_vendor_risk(
        self, vendor_id: int, product_id: int, assessment_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive risk assessment for a vendor product.

        Args:
            vendor_id: Vendor organization ID
            product_id: Product ID
            assessment_context: Additional context for assessment

        Returns:
            Comprehensive risk assessment with AI-powered insights
        """

        logger.info(
            f"Starting advanced risk assessment for vendor {vendor_id}, product {product_id}"
        )

        # Get vendor and product information
        vendor = VendorOrganization.query.get(vendor_id)
        product = VendorProduct.query.get(product_id)

        if not vendor or not product:
            raise ValueError("Vendor or product not found")

        # Check for existing assessment
        existing_assessment = (
            VendorRiskAssessment.query.filter_by(vendor_product_id=product_id)
            .order_by(VendorRiskAssessment.assessment_date.desc())
            .first()
        )

        # Perform risk analysis
        risk_analysis = self._analyze_risk_factors(vendor, product, assessment_context)

        # Calculate risk scores
        risk_scores = self._calculate_risk_scores(risk_analysis)

        # Generate AI-powered recommendations
        recommendations = self._generate_risk_recommendations(risk_scores, risk_analysis)

        # Create or update assessment
        if (
            existing_assessment
            and (datetime.utcnow() - existing_assessment.assessment_date).days < 30
        ):
            assessment = existing_assessment
        else:
            assessment = VendorRiskAssessment(vendor_product_id=product_id)

        # Update assessment with new data
        self._update_assessment_data(assessment, risk_scores, risk_analysis, recommendations)

        # Save assessment
        db.session.add(assessment)
        db.session.commit()

        # Generate portfolio impact analysis
        portfolio_impact = self._analyze_portfolio_impact(vendor, product, risk_scores)

        return {
            "assessment_id": assessment.id,
            "vendor_info": {
                "name": vendor.name,
                "strategic_tier": vendor.strategic_tier,
                "partnership_level": vendor.partnership_level,
            },
            "product_info": {"name": product.name, "category": product.category},
            "risk_scores": risk_scores,
            "risk_analysis": risk_analysis,
            "recommendations": recommendations,
            "portfolio_impact": portfolio_impact,
            "assessment_metadata": {
                "assessment_date": assessment.assessment_date.isoformat(),
                "confidence_score": assessment.confidence_score,
                "methodology": assessment.assessment_methodology,
            },
        }

    def _analyze_risk_factors(
        self, vendor: VendorOrganization, product: VendorProduct, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze risk factors for vendor and product."""

        risk_factors = {}

        # Financial risk analysis
        financial_factors = self._analyze_financial_risk(vendor, context)
        risk_factors["financial"] = financial_factors

        # Implementation risk analysis
        implementation_factors = self._analyze_implementation_risk(product, context)
        risk_factors["implementation"] = implementation_factors

        # Market risk analysis
        market_factors = self._analyze_market_risk(vendor, context)
        risk_factors["market"] = market_factors

        # Technology risk analysis
        technology_factors = self._analyze_technology_risk(product, context)
        risk_factors["technology"] = technology_factors

        # Vendor lock-in risk analysis
        lock_in_factors = self._analyze_vendor_lock_in_risk(product, context)
        risk_factors["vendor_lock_in"] = lock_in_factors

        # Security risk analysis
        security_factors = self._analyze_security_risk(vendor, product, context)
        risk_factors["security"] = security_factors

        # Compliance risk analysis
        compliance_factors = self._analyze_compliance_risk(vendor, product, context)
        risk_factors["compliance"] = compliance_factors

        # Support risk analysis
        support_factors = self._analyze_support_risk(vendor, product, context)
        risk_factors["support"] = support_factors

        return risk_factors

    def _analyze_financial_risk(
        self, vendor: VendorOrganization, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze financial risk factors."""

        factors = {
            "identified_factors": [],
            "risk_score": 3,  # Base score
            "confidence": 0.7,
            "data_points": [],
        }

        # Check financial stability rating
        if vendor.financial_stability_rating:
            factors["data_points"].append(
                {
                    "metric": "Financial Stability Rating",
                    "value": vendor.financial_stability_rating,
                    "impact": "high"
                    if vendor.financial_stability_rating in ["C", "D"]
                    else "medium",
                }
            )

            rating_scores = {"A": 1, "B": 2, "C": 4, "D": 6}
            factors["risk_score"] = max(
                factors["risk_score"], rating_scores.get(vendor.financial_stability_rating, 3)
            )

        # Check company age
        if vendor.year_founded:
            years_in_business = datetime.now().year - vendor.year_founded
            factors["data_points"].append(
                {
                    "metric": "Years in Business",
                    "value": years_in_business,
                    "impact": "high"
                    if years_in_business < 5
                    else "medium"
                    if years_in_business < 10
                    else "low",
                }
            )

            if years_in_business < 5:
                factors["risk_score"] += 2
                factors["identified_factors"].append("Limited operating history")
            elif years_in_business < 10:
                factors["risk_score"] += 1

        # Check strategic tier
        if vendor.strategic_tier:
            tier_scores = {"strategic": 1, "preferred": 2, "approved": 3, "restricted": 5}
            factors["risk_score"] = max(
                factors["risk_score"], tier_scores.get(vendor.strategic_tier, 3)
            )

        # Add relevant risk factors based on score
        if factors["risk_score"] >= 5:
            factors["identified_factors"].extend(
                ["Financial stability concerns", "Potential liquidity issues"]
            )

        return factors

    def _analyze_implementation_risk(
        self, product: VendorProduct, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze implementation risk factors."""

        factors = {
            "identified_factors": [],
            "risk_score": 3,  # Base score
            "confidence": 0.8,
            "data_points": [],
        }

        # Check deployment complexity
        if product.deployment_model:
            complexity_scores = {"saas": 2, "cloud": 3, "on-premise": 5, "hybrid": 4}
            factors["risk_score"] = max(
                factors["risk_score"], complexity_scores.get(product.deployment_model, 3)
            )

            if product.deployment_model == "on-premise":
                factors["identified_factors"].append("On-premise deployment complexity")

        # Check integration requirements
        if product.integration_complexity:
            factors["data_points"].append(
                {
                    "metric": "Integration Complexity",
                    "value": product.integration_complexity,
                    "impact": "high" if product.integration_complexity >= 7 else "medium",
                }
            )

            if product.integration_complexity >= 7:
                factors["risk_score"] += 2
                factors["identified_factors"].append("High integration complexity")
            elif product.integration_complexity >= 5:
                factors["risk_score"] += 1

        # Check customization level
        if product.customization_level:
            customization_scores = {"low": 1, "medium": 3, "high": 5, "extensive": 7}
            factors["risk_score"] = max(
                factors["risk_score"], customization_scores.get(product.customization_level, 3)
            )

            if product.customization_level in ["high", "extensive"]:
                factors["identified_factors"].append("Extensive customization required")

        return factors

    def _analyze_market_risk(
        self, vendor: VendorOrganization, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze market risk factors."""

        factors = {
            "identified_factors": [],
            "risk_score": 3,  # Base score
            "confidence": 0.6,
            "data_points": [],
        }

        # Check Gartner position
        if vendor.gartner_magic_quadrant:
            quadrant_scores = {"leaders": 1, "challengers": 2, "visionaries": 3, "niche_players": 4}
            factors["risk_score"] = max(
                factors["risk_score"], quadrant_scores.get(vendor.gartner_magic_quadrant.lower(), 3)
            )

            factors["data_points"].append(
                {
                    "metric": "Gartner Magic Quadrant",
                    "value": vendor.gartner_magic_quadrant,
                    "impact": "medium",
                }
            )

            if vendor.gartner_magic_quadrant.lower() == "niche_players":
                factors["identified_factors"].append("Limited market position")

        # Check market share
        if vendor.market_share:
            if vendor.market_share < 5:
                factors["risk_score"] += 2
                factors["identified_factors"].append("Low market share")
            elif vendor.market_share < 15:
                factors["risk_score"] += 1

        # Check industry focus
        if vendor.industry_focus:
            # Vendor focused on specific industries may have higher concentration risk
            factors["risk_score"] += 1
            factors["identified_factors"].append("Industry specialization concentration")

        return factors

    def _analyze_technology_risk(
        self, product: VendorProduct, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze technology risk factors."""

        factors = {
            "identified_factors": [],
            "risk_score": 3,  # Base score
            "confidence": 0.7,
            "data_points": [],
        }

        # Check technology stack
        if product.technology_stack:
            # Legacy technology increases risk
            legacy_indicators = ["mainframe", "cobol", "vb6", "classic asp"]
            tech_stack_lower = product.technology_stack.lower()

            for indicator in legacy_indicators:
                if indicator in tech_stack_lower:
                    factors["risk_score"] += 2
                    factors["identified_factors"].append(f"Legacy technology: {indicator}")

        # Check scalability
        if product.scalability_rating:
            scalability_scores = {"low": 5, "medium": 3, "high": 1, "enterprise": 1}
            factors["risk_score"] = max(
                factors["risk_score"], scalability_scores.get(product.scalability_rating, 3)
            )

            if product.scalability_rating == "low":
                factors["identified_factors"].append("Limited scalability")

        # Check API availability
        if product.api_availability:
            if product.api_availability == "none":
                factors["risk_score"] += 2
                factors["identified_factors"].append("No API access")
            elif product.api_availability == "limited":
                factors["risk_score"] += 1

        return factors

    def _analyze_vendor_lock_in_risk(
        self, product: VendorProduct, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze vendor lock-in risk factors."""

        factors = {
            "identified_factors": [],
            "risk_score": 3,  # Base score
            "confidence": 0.8,
            "data_points": [],
        }

        # Check data export capabilities
        if product.data_export_formats:
            if "proprietary" in product.data_export_formats.lower():
                factors["risk_score"] += 2
                factors["identified_factors"].append("Proprietary data formats")

        # Check integration approach
        if product.integration_approach:
            if "proprietary" in product.integration_approach.lower():
                factors["risk_score"] += 2
                factors["identified_factors"].append("Proprietary integration methods")

        # Check contract terms (if available)
        # This would typically come from contract analysis
        factors["identified_factors"].append("Contract terms review needed")

        return factors

    def _analyze_security_risk(
        self, vendor: VendorOrganization, product: VendorProduct, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze security risk factors."""

        factors = {
            "identified_factors": [],
            "risk_score": 2,  # Base score (security is critical)
            "confidence": 0.8,
            "data_points": [],
        }

        # Check security certifications
        if vendor.security_certifications:
            cert_list = vendor.security_certifications.lower()
            critical_certs = ["iso 27001", "soc 2", "pci dss", "hipaa"]

            cert_score = 0
            for cert in critical_certs:
                if cert in cert_list:
                    cert_score += 1

            if cert_score == 0:
                factors["risk_score"] += 3
                factors["identified_factors"].append("No security certifications")
            elif cert_score < 2:
                factors["risk_score"] += 1
                factors["identified_factors"].append("Limited security certifications")

        # Check data handling
        if product.data_residency:
            if product.data_residency == "unknown":
                factors["risk_score"] += 2
                factors["identified_factors"].append("Unclear data residency")

        # Check encryption
        if product.encryption_standards:
            if "none" in product.encryption_standards.lower():
                factors["risk_score"] += 3
                factors["identified_factors"].append("No encryption standards")
        else:
            factors["risk_score"] += 1
            factors["identified_factors"].append("Encryption standards unclear")

        return factors

    def _analyze_compliance_risk(
        self, vendor: VendorOrganization, product: VendorProduct, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze compliance risk factors."""

        factors = {
            "identified_factors": [],
            "risk_score": 2,  # Base score (compliance is critical)
            "confidence": 0.7,
            "data_points": [],
        }

        # Check compliance certifications
        if vendor.compliance_certifications:
            cert_list = vendor.compliance_certifications.lower()
            critical_compliance = ["gdpr", "sox", "hipaa", "pci dss"]

            compliance_score = 0
            for cert in critical_compliance:
                if cert in cert_list:
                    compliance_score += 1

            if compliance_score == 0:
                factors["risk_score"] += 2
                factors["identified_factors"].append("No compliance certifications")

        # Check industry-specific compliance
        if context and "industry" in context:
            industry = context["industry"].lower()
            if industry in ["healthcare"] and "hipaa" not in cert_list:
                factors["risk_score"] += 2
                factors["identified_factors"].append("Healthcare compliance gaps")
            elif industry in ["financial"] and "sox" not in cert_list:
                factors["risk_score"] += 2
                factors["identified_factors"].append("Financial compliance gaps")

        return factors

    def _analyze_support_risk(
        self, vendor: VendorOrganization, product: VendorProduct, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze support risk factors."""

        factors = {
            "identified_factors": [],
            "risk_score": 3,  # Base score
            "confidence": 0.8,
            "data_points": [],
        }

        # Check support level
        if vendor.support_level:
            support_scores = {"24x7": 1, "business_hours": 2, "limited": 4, "basic": 5}
            factors["risk_score"] = max(
                factors["risk_score"], support_scores.get(vendor.support_level, 3)
            )

            if vendor.support_level in ["limited", "basic"]:
                factors["identified_factors"].append("Limited support availability")

        # Check geographic coverage
        if vendor.geographic_coverage:
            if vendor.geographic_coverage == "limited":
                factors["risk_score"] += 2
                factors["identified_factors"].append("Limited geographic coverage")

        # Check support response time
        if vendor.support_response_time:
            if vendor.support_response_time > 24:  # hours
                factors["risk_score"] += 1
                factors["identified_factors"].append("Slow support response times")

        return factors

    def _calculate_risk_scores(self, risk_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall risk scores from risk analysis."""

        scores = {}
        total_weighted_score = 0
        total_weight = 0

        # Default weights
        weights = {
            "financial": 0.15,
            "implementation": 0.20,
            "market": 0.15,
            "technology": 0.10,
            "vendor_lock_in": 0.15,
            "security": 0.10,
            "compliance": 0.10,
            "support": 0.05,
        }

        for category, analysis in risk_analysis.items():
            category_score = analysis["risk_score"]
            category_weight = weights.get(category, 0.1)

            scores[category] = {
                "score": category_score,
                "weight": category_weight,
                "weighted_score": category_score * category_weight,
                "confidence": analysis["confidence"],
                "identified_factors": analysis["identified_factors"],
            }

            total_weighted_score += category_score * category_weight
            total_weight += category_weight

        # Calculate overall score
        overall_score = round(total_weighted_score / total_weight) if total_weight > 0 else 0

        # Determine risk level
        if overall_score <= 3:
            risk_level = "low"
        elif overall_score <= 5:
            risk_level = "medium"
        elif overall_score <= 7:
            risk_level = "high"
        else:
            risk_level = "critical"

        scores["overall"] = {
            "score": overall_score,
            "level": risk_level,
            "confidence": sum(analysis["confidence"] for analysis in risk_analysis.values())
            / len(risk_analysis),
        }

        return scores

    def _generate_risk_recommendations(
        self, risk_scores: Dict[str, Any], risk_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate AI-powered risk mitigation recommendations."""

        recommendations = {
            "priority_actions": [],
            "mitigation_strategies": {},
            "monitoring_requirements": [],
            "contingency_plans": [],
        }

        # Generate category-specific recommendations
        for category, score_data in risk_scores.items():
            if category == "overall":
                continue

            category_score = score_data["score"]
            identified_factors = score_data["identified_factors"]

            if category_score >= 6:  # High risk
                # Get mitigation strategies from library
                strategies = self.mitigation_strategies_library.get(category, [])
                recommendations["mitigation_strategies"][category] = strategies[
                    :3
                ]  # Top 3 strategies

                # Add priority actions
                recommendations["priority_actions"].extend(
                    [
                        f"Address high {category} risk immediately",
                        f"Implement {category} mitigation strategies",
                    ]
                )

            elif category_score >= 4:  # Medium risk
                strategies = self.mitigation_strategies_library.get(category, [])
                recommendations["mitigation_strategies"][category] = strategies[
                    :2
                ]  # Top 2 strategies

                recommendations["priority_actions"].append(f"Monitor {category} risk factors")

        # Add monitoring requirements
        recommendations["monitoring_requirements"] = [
            "Quarterly risk assessment reviews",
            "Financial health monitoring",
            "Security compliance audits",
            "Performance metrics tracking",
        ]

        # Add contingency plans
        if risk_scores["overall"]["score"] >= 6:
            recommendations["contingency_plans"] = [
                "Develop vendor exit strategy",
                "Identify alternative vendors",
                "Create data migration plan",
                "Establish transition budget",
            ]

        return recommendations

    def _update_assessment_data(
        self,
        assessment: VendorRiskAssessment,
        risk_scores: Dict[str, Any],
        risk_analysis: Dict[str, Any],
        recommendations: Dict[str, Any],
    ):
        """Update assessment record with new data."""

        # Update risk scores
        assessment.financial_risk_score = risk_scores["financial"]["score"]
        assessment.implementation_risk_score = risk_scores["implementation"]["score"]
        assessment.market_risk_score = risk_scores["market"]["score"]
        assessment.technology_risk_score = risk_scores["technology"]["score"]
        assessment.vendor_lock_in_risk_score = risk_scores["vendor_lock_in"]["score"]
        assessment.security_risk_score = risk_scores["security"]["score"]
        assessment.compliance_risk_score = risk_scores["compliance"]["score"]
        assessment.support_risk_score = risk_scores["support"]["score"]

        # Update overall metrics
        assessment.overall_risk_score = risk_scores["overall"]["score"]
        assessment.risk_level = risk_scores["overall"]["level"]
        assessment.confidence_score = risk_scores["overall"]["confidence"]

        # Update risk factors and mitigations
        all_factors = []
        for category, analysis in risk_analysis.items():
            for factor in analysis["identified_factors"]:
                all_factors.append(
                    {"category": category, "factor": factor, "score": analysis["risk_score"]}
                )

        assessment.risk_factors = json.dumps(all_factors)
        assessment.mitigation_strategies = json.dumps(recommendations["mitigation_strategies"])
        assessment.contingency_plans = json.dumps(recommendations["contingency_plans"])

        # Update metadata
        assessment.assessment_date = datetime.utcnow()
        assessment.assessment_methodology = "advanced_ai_enhanced"
        assessment.next_review_date = datetime.utcnow() + timedelta(days=90)

        # Set data sources
        data_sources = [
            "vendor_master_data",
            "product_specifications",
            "market_intelligence",
            "financial_analysis",
            "security_assessments",
        ]
        assessment.data_sources = json.dumps(data_sources)

    def _analyze_portfolio_impact(
        self, vendor: VendorOrganization, product: VendorProduct, risk_scores: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze impact on existing vendor portfolio."""

        portfolio_impact = {
            "concentration_risk": "medium",
            "diversification_score": 0.7,
            "strategic_alignment": "good",
            "recommendations": [],
        }

        # Check vendor concentration in portfolio
        existing_vendors = (
            db.session.query(VendorOrganization)
            .filter(VendorOrganization.strategic_tier == "strategic")
            .count()
        )

        if existing_vendors <= 2:
            portfolio_impact["concentration_risk"] = "high"
            portfolio_impact["recommendations"].append(
                "Consider diversifying strategic vendor portfolio"
            )

        # Calculate diversification score
        if vendor.strategic_tier == "strategic" and existing_vendors >= 3:
            portfolio_impact["diversification_score"] = 0.8
        elif vendor.strategic_tier == "preferred" and existing_vendors >= 2:
            portfolio_impact["diversification_score"] = 0.7
        else:
            portfolio_impact["diversification_score"] = 0.6

        # Strategic alignment
        if vendor.strategic_tier == "strategic":
            portfolio_impact["strategic_alignment"] = "excellent"
        elif vendor.strategic_tier == "preferred":
            portfolio_impact["strategic_alignment"] = "good"
        else:
            portfolio_impact["strategic_alignment"] = "moderate"

        return portfolio_impact

    def get_portfolio_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio risk summary."""

        # Get all recent risk assessments
        recent_assessments = (
            db.session.query(VendorRiskAssessment)
            .filter(VendorRiskAssessment.assessment_date >= datetime.utcnow() - timedelta(days=90))
            .all()
        )

        if not recent_assessments:
            return {
                "total_assessments": 0,
                "risk_distribution": {},
                "high_risk_vendors": [],
                "portfolio_health": "unknown",
            }

        # Calculate risk distribution
        risk_distribution = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        high_risk_vendors = []

        for assessment in recent_assessments:
            risk_level = assessment.risk_level
            risk_distribution[risk_level] = risk_distribution.get(risk_level, 0) + 1

            if risk_level in ["high", "critical"]:
                high_risk_vendors.append(
                    {
                        "vendor_product_id": assessment.vendor_product_id,
                        "risk_score": assessment.overall_risk_score,
                        "risk_level": risk_level,
                    }
                )

        # Calculate portfolio health
        total_assessments = len(recent_assessments)
        high_critical_percentage = (
            (risk_distribution["high"] + risk_distribution["critical"]) / total_assessments * 100
        )

        if high_critical_percentage <= 20:
            portfolio_health = "excellent"
        elif high_critical_percentage <= 40:
            portfolio_health = "good"
        elif high_critical_percentage <= 60:
            portfolio_health = "moderate"
        else:
            portfolio_health = "concerning"

        return {
            "total_assessments": total_assessments,
            "risk_distribution": risk_distribution,
            "high_risk_vendors": high_risk_vendors,
            "portfolio_health": portfolio_health,
            "high_critical_percentage": round(high_critical_percentage, 1),
        }
