"""
Investment Prioritization Service

Analyzes and prioritizes investments in business capabilities based on:
- Strategic importance and business value
- Current coverage and maturity gaps
- Risk assessment and single points of failure
- ROI and cost-benefit analysis
- Technology debt and modernization needs
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db
from app.models.application_capability import ApplicationCapabilityMapping
from app.models.application_portfolio import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.services.decorators import transactional

logger = logging.getLogger(__name__)


class InvestmentPrioritizationService:
    """
    Service for prioritizing investments in business capabilities.

    Provides data-driven investment recommendations based on multiple factors:
    - Strategic alignment and business criticality
    - Current capability coverage and maturity
    - Risk factors and dependencies
    - Technology health and modernization needs
    """

    def __init__(self):
        pass

    @transactional
    def analyze_investment_priorities(self, include_risk_analysis: bool = True) -> Dict:
        """
        Comprehensive investment prioritization analysis.

        Args:
            include_risk_analysis: Include risk assessment in prioritization

        Returns:
            Dict with prioritized investment recommendations
        """
        # Get all business capabilities
        capabilities = BusinessCapability.query.all()

        # Batch-load all capability mappings to avoid N+1 queries
        mappings_by_cap = {}
        try:
            all_mappings = ApplicationCapabilityMapping.query.all()
            for m in all_mappings:
                mappings_by_cap.setdefault(m.business_capability_id, []).append(m)
        except Exception:
            logger.debug("Could not batch-load capability mappings", exc_info=True)

        # Analyze each capability for investment priority
        capability_scores = []
        for capability in capabilities:
            score_data = self._calculate_capability_score(
                capability, include_risk_analysis, mappings_by_cap
            )
            capability_scores.append(score_data)

        # Sort by investment priority (highest first)
        capability_scores.sort(key=lambda x: x["investment_priority_score"], reverse=True)

        # Categorize by priority levels
        critical_investments = [c for c in capability_scores if c["priority_level"] == "CRITICAL"]
        high_investments = [c for c in capability_scores if c["priority_level"] == "HIGH"]
        medium_investments = [c for c in capability_scores if c["priority_level"] == "MEDIUM"]
        low_investments = [c for c in capability_scores if c["priority_level"] == "LOW"]

        # Calculate portfolio metrics
        portfolio_metrics = self._calculate_portfolio_metrics(capability_scores)

        # Generate investment recommendations
        recommendations = self._generate_investment_recommendations(capability_scores)

        return {
            "total_capabilities": len(capabilities),
            "capability_scores": capability_scores,
            "critical_investments": critical_investments,
            "high_investments": high_investments,
            "medium_investments": medium_investments,
            "low_investments": low_investments,
            "portfolio_metrics": portfolio_metrics,
            "recommendations": recommendations,
            "analysis_date": datetime.utcnow().isoformat(),
        }

    def _calculate_capability_score(
        self, capability: BusinessCapability, include_risk: bool,
        mappings_by_cap: Dict = None,
    ) -> Dict:
        """Calculate investment priority score for a single capability."""

        # Use pre-loaded mappings dict (batch) instead of per-capability query
        app_mappings = (mappings_by_cap or {}).get(capability.id, [])

        coverage_count = len(app_mappings)

        # Strategic importance score (0 - 25 points)
        strategic_score = self._calculate_strategic_score(capability)

        # Coverage gap score (0 - 25 points)
        coverage_score = self._calculate_coverage_score(coverage_count, capability)

        # Maturity gap score (0 - 25 points)
        maturity_score = self._calculate_maturity_score(capability)

        # Risk score (0 - 25 points)
        risk_score = 0
        if include_risk:
            risk_score = self._calculate_risk_score(capability, app_mappings)

        # Total investment priority score (0 - 100)
        total_score = strategic_score + coverage_score + maturity_score + risk_score

        # Determine priority level
        if total_score >= 80:
            priority_level = "CRITICAL"
        elif total_score >= 60:
            priority_level = "HIGH"
        elif total_score >= 40:
            priority_level = "MEDIUM"
        else:
            priority_level = "LOW"

        # Calculate estimated investment need
        investment_need = self._estimate_investment_need(capability, total_score, app_mappings)

        return {
            "capability_id": capability.id,
            "capability_name": capability.name,
            "capability_domain": capability.business_domain or "Unknown",
            "strategic_importance": capability.strategic_importance,
            "coverage_count": coverage_count,
            "strategic_score": strategic_score,
            "coverage_score": coverage_score,
            "maturity_score": maturity_score,
            "risk_score": risk_score,
            "investment_priority_score": total_score,
            "priority_level": priority_level,
            "investment_need": investment_need,
            "recommendation": self._get_capability_recommendation(
                capability, total_score, coverage_count
            ),
        }

    def _calculate_strategic_score(self, capability: BusinessCapability) -> int:
        """Calculate strategic importance score (0 - 25 points)."""
        importance = (capability.strategic_importance or "").lower()

        if importance == "critical":
            return 25
        elif importance == "high":
            return 20
        elif importance == "medium":
            return 15
        elif importance == "low":
            return 10
        else:
            return 5

    def _calculate_coverage_score(self, coverage_count: int, capability: BusinessCapability) -> int:
        """Calculate coverage gap score (0 - 25 points)."""
        importance = (capability.strategic_importance or "").lower()

        # Critical capabilities need more coverage
        if importance == "critical":
            if coverage_count == 0:
                return 25  # No coverage - highest priority
            elif coverage_count == 1:
                return 20  # Single point of failure
            elif coverage_count == 2:
                return 10  # Minimal coverage
            else:
                return 5  # Adequate coverage
        elif importance == "high":
            if coverage_count == 0:
                return 20
            elif coverage_count == 1:
                return 15
            elif coverage_count == 2:
                return 5
            else:
                return 0
        else:
            if coverage_count == 0:
                return 15
            elif coverage_count == 1:
                return 5
            else:
                return 0

    def _calculate_maturity_score(self, capability: BusinessCapability) -> int:
        """Calculate maturity gap score (0 - 25 points)."""
        current_maturity = capability.current_maturity_level or 1
        target_maturity = capability.target_maturity_level or 3

        maturity_gap = target_maturity - current_maturity

        if maturity_gap >= 3:
            return 25  # Large maturity gap
        elif maturity_gap >= 2:
            return 20
        elif maturity_gap >= 1:
            return 15
        else:
            return 5  # Small or no gap

    def _calculate_risk_score(self, capability: BusinessCapability, app_mappings: List) -> int:
        """Calculate risk score (0 - 25 points)."""
        risk_score = 0

        # Single point of failure risk
        if len(app_mappings) == 1 and (capability.strategic_importance or "").lower() in [
            "critical",
            "high",
        ]:
            risk_score += 15

        # Technology debt risk
        high_debt_apps = [
            m
            for m in app_mappings
            if hasattr(m, "technical_debt_score") and m.technical_debt_score > 70
        ]
        if high_debt_apps:
            risk_score += 10

        # Compliance risk
        if hasattr(capability, "compliance_requirements") and capability.compliance_requirements:
            risk_score += 5

        return min(risk_score, 25)

    def _estimate_investment_need(
        self, capability: BusinessCapability, score: int, app_mappings: List = None
    ) -> Dict:
        """Estimate investment need for the capability."""
        if app_mappings is None:
            app_mappings = []

        # Base investment estimation
        if score >= 80:
            # High priority investment
            base_cost = 500000  # $500k for high priority
            complexity_multiplier = (
                1.5 if (capability.strategic_importance or "").lower() == "critical" else 1.0
            )
        elif len(app_mappings) == 1:
            # Single point of failure - need redundancy
            base_cost = 200000  # $200k for redundancy
            complexity_multiplier = 1.2
        else:
            # Modernization or improvement
            base_cost = 100000  # $100k for modernization
            complexity_multiplier = 1.0

        estimated_cost = base_cost * complexity_multiplier

        # Timeframe estimation
        if len(app_mappings) == 0:
            timeframe = "12 - 18 months"
        elif len(app_mappings) == 1:
            timeframe = "6 - 12 months"
        else:
            timeframe = "3 - 6 months"

        return {
            "estimated_cost": estimated_cost,
            "currency": "USD",
            "timeframe": timeframe,
            "investment_type": "NEW" if len(app_mappings) == 0 else "IMPROVEMENT",
            "complexity": "HIGH"
            if complexity_multiplier > 1.2
            else "MEDIUM"
            if complexity_multiplier > 1.0
            else "LOW",
        }

    def _get_capability_recommendation(
        self, capability: BusinessCapability, score: int, coverage_count: int
    ) -> str:
        """Generate specific recommendation for the capability."""

        if coverage_count == 0:
            return (
                f"INVEST: Establish {capability.name} capability - no current application support"
            )
        elif coverage_count == 1 and (capability.strategic_importance or "").lower() in [
            "critical",
            "high",
        ]:
            return f"INVEST: Add redundancy for {capability.name} - single point of failure risk"
        elif score >= 70:
            return f"INVEST: High priority investment in {capability.name} - strategic importance with gaps"
        elif score >= 50:
            return f"CONSIDER: Moderate investment in {capability.name} - improvement opportunities"
        else:
            return f"MONITOR: {capability.name} - adequate coverage, monitor for changes"

    def _calculate_portfolio_metrics(self, capability_scores: List[Dict]) -> Dict:
        """Calculate portfolio-level investment metrics."""

        total_capabilities = len(capability_scores)
        critical_count = len([c for c in capability_scores if c["priority_level"] == "CRITICAL"])
        high_count = len([c for c in capability_scores if c["priority_level"] == "HIGH"])

        # Total estimated investment need
        total_investment = sum(c["investment_need"]["estimated_cost"] for c in capability_scores)

        # Investment by priority
        critical_investment = sum(
            c["investment_need"]["estimated_cost"]
            for c in capability_scores
            if c["priority_level"] == "CRITICAL"
        )
        high_investment = sum(
            c["investment_need"]["estimated_cost"]
            for c in capability_scores
            if c["priority_level"] == "HIGH"
        )

        # Average scores
        avg_strategic_score = (
            sum(c["strategic_score"] for c in capability_scores) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_coverage_score = (
            sum(c["coverage_score"] for c in capability_scores) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_maturity_score = (
            sum(c["maturity_score"] for c in capability_scores) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_risk_score = (
            sum(c["risk_score"] for c in capability_scores) / total_capabilities
            if total_capabilities > 0
            else 0
        )

        return {
            "total_capabilities": total_capabilities,
            "critical_priorities": critical_count,
            "high_priorities": high_count,
            "total_estimated_investment": total_investment,
            "critical_investment": critical_investment,
            "high_investment": high_investment,
            "average_strategic_score": round(avg_strategic_score, 1),
            "average_coverage_score": round(avg_coverage_score, 1),
            "average_maturity_score": round(avg_maturity_score, 1),
            "average_risk_score": round(avg_risk_score, 1),
            "investment_currency": "USD",
        }

    def _generate_investment_recommendations(self, capability_scores: List[Dict]) -> List[Dict]:
        """Generate strategic investment recommendations."""

        recommendations = []

        # Top 5 critical investments
        critical_caps = [c for c in capability_scores if c["priority_level"] == "CRITICAL"][:5]

        for cap in critical_caps:
            recommendations.append(
                {
                    "type": "IMMEDIATE_INVESTMENT",
                    "priority": "CRITICAL",
                    "capability": cap["capability_name"],
                    "justification": f"Strategic {cap['strategic_importance']} capability with {cap['coverage_count']} applications",
                    "estimated_cost": cap["investment_need"]["estimated_cost"],
                    "timeframe": cap["investment_need"]["timeframe"],
                    "expected_roi": "HIGH"
                    if cap["strategic_importance"] == "critical"
                    else "MEDIUM",
                }
            )

        # Consolidation opportunities
        over_served = [c for c in capability_scores if c["coverage_count"] >= 5]
        if over_served:
            recommendations.append(
                {
                    "type": "CONSOLIDATION_OPPORTUNITY",
                    "priority": "HIGH",
                    "capability": f"{len(over_served)} capabilities",
                    "justification": "Multiple applications supporting same capabilities - consolidation opportunity",
                    "estimated_cost": "SAVINGS",
                    "timeframe": "6 - 12 months",
                    "expected_roi": "HIGH",
                }
            )

        # Single point of failures
        spf_caps = [
            c
            for c in capability_scores
            if c["coverage_count"] == 1 and c["strategic_importance"] in ["critical", "high"]
        ]
        if spf_caps:
            recommendations.append(
                {
                    "type": "RISK_MITIGATION",
                    "priority": "HIGH",
                    "capability": f"{len(spf_caps)} capabilities",
                    "justification": "Single point of failure risks for critical capabilities",
                    "estimated_cost": sum(c["investment_need"]["estimated_cost"] for c in spf_caps),
                    "timeframe": "6 - 12 months",
                    "expected_roi": "HIGH",
                }
            )

        return recommendations
