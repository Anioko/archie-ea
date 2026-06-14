"""
Risk Assessment Service

Identifies and assesses risks across business capabilities and applications:
- Single points of failure
- Technology debt and aging systems
- Compliance and regulatory risks
- Skill gaps and resource risks
- Integration and dependency risks
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db
from app.models.application_portfolio import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.unified_application_capability_mapping import UnifiedApplicationCapabilityMapping
from .decorators import transactional


class RiskAssessmentService:
    """
    Service for comprehensive risk assessment across the enterprise architecture.

    Identifies and categorizes risks:
    - Single points of failure (SPOF)
    - Technology debt and obsolescence
    - Compliance and regulatory risks
    - Skill and resource gaps
    - Integration and dependency risks
    """

    def __init__(self):
        pass

    @transactional
    def analyze_portfolio_risks(self, include_technology_debt: bool = True) -> Dict:
        """
        Comprehensive risk assessment across the entire portfolio.

        Args:
            include_technology_debt: Include technology debt analysis

        Returns:
            Dict with risk assessment results and recommendations
        """
        # Get all business capabilities
        capabilities = BusinessCapability.query.all()

        # Analyze risks for each capability
        capability_risks = []
        for capability in capabilities:
            risk_data = self._analyze_capability_risks(capability, include_technology_debt)
            capability_risks.append(risk_data)

        # Sort by overall risk score (highest first, treat None as 0)
        capability_risks.sort(key=lambda x: x.get("overall_risk_score") or 0, reverse=True)

        # Categorize by risk levels
        critical_risks = [c for c in capability_risks if c["risk_level"] == "CRITICAL"]
        high_risks = [c for c in capability_risks if c["risk_level"] == "HIGH"]
        medium_risks = [c for c in capability_risks if c["risk_level"] == "MEDIUM"]
        low_risks = [c for c in capability_risks if c["risk_level"] == "LOW"]

        # Calculate portfolio risk metrics
        portfolio_metrics = self._calculate_portfolio_risk_metrics(capability_risks)

        # Generate risk mitigation recommendations
        recommendations = self._generate_risk_recommendations(capability_risks)

        return {
            "total_capabilities": len(capabilities),
            "capability_risks": capability_risks,
            "critical_risks": critical_risks,
            "high_risks": high_risks,
            "medium_risks": medium_risks,
            "low_risks": low_risks,
            "portfolio_metrics": portfolio_metrics,
            "recommendations": recommendations,
            "assessment_date": datetime.utcnow().isoformat(),
        }

    def _analyze_capability_risks(
        self, capability: BusinessCapability, include_tech_debt: bool
    ) -> Dict:
        """Analyze risks for a single capability."""

        # Get application coverage
        app_mappings = UnifiedApplicationCapabilityMapping.query.filter_by(
            unified_capability_id=capability.id
        ).all()

        # Calculate different risk factors
        spof_risk = self._calculate_spof_risk(capability, app_mappings)
        technology_risk = self._calculate_technology_risk(app_mappings) if include_tech_debt else 0
        compliance_risk = self._calculate_compliance_risk(capability, app_mappings)
        dependency_risk = self._calculate_dependency_risk(app_mappings)
        skill_risk = self._calculate_skill_risk(app_mappings)

        # Calculate overall risk score (0 - 100) with None safety
        overall_risk_score = (
            (spof_risk or 0)
            + (technology_risk or 0)
            + (compliance_risk or 0)
            + (dependency_risk or 0)
            + (skill_risk or 0)
        )

        # Determine risk level
        if overall_risk_score >= 80:
            risk_level = "CRITICAL"
        elif overall_risk_score >= 60:
            risk_level = "HIGH"
        elif overall_risk_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Identify specific risk factors
        risk_factors = []
        if spof_risk >= 30:
            risk_factors.append("SINGLE_POINT_OF_FAILURE")
        if technology_risk >= 20:
            risk_factors.append("TECHNOLOGY_DEBT")
        if compliance_risk >= 20:
            risk_factors.append("COMPLIANCE_RISK")
        if dependency_risk >= 15:
            risk_factors.append("DEPENDENCY_RISK")
        if skill_risk >= 15:
            risk_factors.append("SKILL_GAP")

        return {
            "capability_id": capability.id,
            "capability_name": capability.name,
            "capability_domain": capability.business_domain or "Unknown",
            "strategic_importance": capability.strategic_importance,
            "coverage_count": len(app_mappings),
            "spof_risk": spof_risk,
            "technology_risk": technology_risk,
            "compliance_risk": compliance_risk,
            "dependency_risk": dependency_risk,
            "skill_risk": skill_risk,
            "overall_risk_score": overall_risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "mitigation_priority": self._calculate_mitigation_priority(
                capability, overall_risk_score
            ),
            "risk_assessment": self._generate_risk_assessment(
                capability, risk_factors, overall_risk_score
            ),
        }

    def _calculate_spof_risk(self, capability: BusinessCapability, app_mappings: List) -> int:
        """Calculate single point of failure risk (0 - 30 points)."""
        coverage_count = len(app_mappings)
        importance = (capability.strategic_importance or "").lower()

        # Critical capabilities with no or single coverage have highest SPOF risk
        if coverage_count == 0:
            if importance == "critical":
                return 30  # Critical capability with no support
            elif importance == "high":
                return 25
            elif importance == "medium":
                return 20
            else:
                return 15
        elif coverage_count == 1:
            if importance == "critical":
                return 25  # Critical capability with single point of failure
            elif importance == "high":
                return 20
            elif importance == "medium":
                return 15
            else:
                return 10
        elif coverage_count == 2:
            if importance == "critical":
                return 15  # Minimal redundancy for critical capability
            else:
                return 5
        else:
            return 0  # Adequate coverage

    def _calculate_technology_risk(self, app_mappings: List) -> int:
        """Calculate technology debt and obsolescence risk (0 - 25 points)."""
        if not app_mappings:
            return 0

        tech_risk = 0

        # Check for high technology debt
        high_debt_apps = [
            m
            for m in app_mappings
            if hasattr(m, "technical_debt_score") and (m.technical_debt_score or 0) > 70
        ]
        if high_debt_apps:
            tech_risk += len(high_debt_apps) * 5

        # Check for aging applications
        aging_apps = [
            m for m in app_mappings if hasattr(m, "age_years") and (m.age_years or 0) > 10
        ]
        if aging_apps:
            tech_risk += len(aging_apps) * 3

        # Check for unsupported platforms
        unsupported_apps = [
            m
            for m in app_mappings
            if hasattr(m, "platform_status") and m.platform_status == "unsupported"
        ]
        if unsupported_apps:
            tech_risk += len(unsupported_apps) * 5

        return min(tech_risk, 25)

    def _calculate_compliance_risk(self, capability: BusinessCapability, app_mappings: List) -> int:
        """Calculate compliance and regulatory risk (0 - 25 points)."""
        compliance_risk = 0

        # Check if capability handles regulated data
        if hasattr(capability, "handles_pii") and capability.handles_pii:
            compliance_risk += 10

        # Check for compliance requirements
        if hasattr(capability, "compliance_requirements") and capability.compliance_requirements:
            compliance_risk += 10

        # Check application compliance status
        non_compliant_apps = [
            m
            for m in app_mappings
            if hasattr(m, "compliance_status") and m.compliance_status != "compliant"
        ]
        if non_compliant_apps:
            compliance_risk += len(non_compliant_apps) * 5

        return min(compliance_risk, 25)

    def _calculate_dependency_risk(self, app_mappings: List) -> int:
        """Calculate dependency and integration risk (0 - 20 points)."""
        if not app_mappings:
            return 0

        dependency_risk = 0

        # Check for high dependency count
        high_dep_apps = [
            m
            for m in app_mappings
            if hasattr(m, "dependency_count") and (m.dependency_count or 0) > 10
        ]
        if high_dep_apps:
            dependency_risk += len(high_dep_apps) * 3

        # Check for critical dependencies
        critical_deps = [
            m
            for m in app_mappings
            if hasattr(m, "critical_dependencies") and (m.critical_dependencies or 0) > 0
        ]
        if critical_deps:
            dependency_risk += len(critical_deps) * 4

        return min(dependency_risk, 20)

    def _calculate_skill_risk(self, app_mappings: List) -> int:
        """Calculate skill gap and resource risk (0 - 20 points)."""
        if not app_mappings:
            return 0

        skill_risk = 0

        # Check for skill gaps
        skill_gap_apps = [
            m for m in app_mappings if hasattr(m, "skill_gap_risk") and m.skill_gap_risk
        ]
        if skill_gap_apps:
            skill_risk += len(skill_gap_apps) * 3

        # Check for vendor lock-in
        vendor_locked = [
            m for m in app_mappings if hasattr(m, "vendor_lock_in") and m.vendor_lock_in
        ]
        if vendor_locked:
            skill_risk += len(vendor_locked) * 2

        return min(skill_risk, 20)

    def _calculate_mitigation_priority(
        self, capability: BusinessCapability, risk_score: int
    ) -> str:
        """Calculate mitigation priority based on risk and strategic importance."""
        importance = (capability.strategic_importance or "").lower()
        risk_score = risk_score or 0  # Safety check for None

        if importance == "critical" and risk_score >= 70:
            return "IMMEDIATE"
        elif importance == "critical" and risk_score >= 50:
            return "HIGH"
        elif importance == "high" and risk_score >= 60:
            return "HIGH"
        elif risk_score >= 70:
            return "HIGH"
        elif risk_score >= 50:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_risk_assessment(
        self, capability: BusinessCapability, risk_factors: List, risk_score: int
    ) -> str:
        """Generate risk assessment description."""
        risk_score = risk_score or 0  # Safety check for None

        if risk_score >= 80:
            return f"CRITICAL: {capability.name} has multiple high-risk factors requiring immediate attention"
        elif risk_score >= 60:
            return f"HIGH: {capability.name} has significant risks that need mitigation"
        elif risk_score >= 40:
            return f"MEDIUM: {capability.name} has moderate risks that should be monitored"
        else:
            return f"LOW: {capability.name} has minimal risks with adequate controls"

    def _calculate_portfolio_risk_metrics(self, capability_risks: List[Dict]) -> Dict:
        """Calculate portfolio-level risk metrics."""

        total_capabilities = len(capability_risks)
        critical_risk_count = len([c for c in capability_risks if c["risk_level"] == "CRITICAL"])
        high_risk_count = len([c for c in capability_risks if c["risk_level"] == "HIGH"])

        # Risk distribution
        spof_count = len(
            [c for c in capability_risks if "SINGLE_POINT_OF_FAILURE" in c["risk_factors"]]
        )
        tech_debt_count = len(
            [c for c in capability_risks if "TECHNOLOGY_DEBT" in c["risk_factors"]]
        )
        compliance_count = len(
            [c for c in capability_risks if "COMPLIANCE_RISK" in c["risk_factors"]]
        )
        dependency_count = len(
            [c for c in capability_risks if "DEPENDENCY_RISK" in c["risk_factors"]]
        )
        skill_gap_count = len([c for c in capability_risks if "SKILL_GAP" in c["risk_factors"]])

        # Average risk scores
        avg_spof_risk = (
            sum(c["spof_risk"] for c in capability_risks) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_tech_risk = (
            sum(c["technology_risk"] for c in capability_risks) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_compliance_risk = (
            sum(c["compliance_risk"] for c in capability_risks) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_dependency_risk = (
            sum(c["dependency_risk"] for c in capability_risks) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_skill_risk = (
            sum(c["skill_risk"] for c in capability_risks) / total_capabilities
            if total_capabilities > 0
            else 0
        )

        return {
            "total_capabilities": total_capabilities,
            "critical_risks": critical_risk_count,
            "high_risks": high_risk_count,
            "single_point_failures": spof_count,
            "technology_debt_risks": tech_debt_count,
            "compliance_risks": compliance_count,
            "average_spof_risk": round(avg_spof_risk, 1),
            "average_technology_risk": round(avg_tech_risk, 1),
            "average_compliance_risk": round(avg_compliance_risk, 1),
            "average_dependency_risk": round(avg_dependency_risk, 1),
            "average_skill_risk": round(avg_skill_risk, 1),
            "portfolio_risk_level": "HIGH"
            if critical_risk_count > 5
            else "MEDIUM"
            if high_risk_count > 10
            else "LOW",
        }

    def _generate_risk_recommendations(self, capability_risks: List[Dict]) -> List[Dict]:
        """Generate risk mitigation recommendations."""

        recommendations = []

        # Critical risks requiring immediate action
        critical_caps = [c for c in capability_risks if c["risk_level"] == "CRITICAL"][:5]

        for cap in critical_caps:
            recommendations.append(
                {
                    "type": "IMMEDIATE_MITIGATION",
                    "priority": "CRITICAL",
                    "capability": cap["capability_name"],
                    "risk_level": cap["risk_level"],
                    "risk_factors": cap["risk_factors"],
                    "recommendation": self._get_mitigation_recommendation(cap),
                    "timeframe": "1 - 3 months",
                    "estimated_cost": "HIGH"
                    if (cap.get("overall_risk_score") or 0) >= 85
                    else "MEDIUM",
                }
            )

        # Single point of failures
        spf_caps = [c for c in capability_risks if "SINGLE_POINT_OF_FAILURE" in c["risk_factors"]]
        if spf_caps:
            recommendations.append(
                {
                    "type": "REDUNDANCY_PLANNING",
                    "priority": "HIGH",
                    "capability": f"{len(spf_caps)} capabilities",
                    "risk_level": "HIGH",
                    "risk_factors": ["SINGLE_POINT_OF_FAILURE"],
                    "recommendation": "Implement redundancy for critical capabilities with single application support",
                    "timeframe": "3 - 6 months",
                    "estimated_cost": "HIGH",
                }
            )

        # Technology debt
        tech_debt_caps = [c for c in capability_risks if "TECHNOLOGY_DEBT" in c["risk_factors"]]
        if tech_debt_caps:
            recommendations.append(
                {
                    "type": "TECHNOLOGY_MODERNIZATION",
                    "priority": "MEDIUM",
                    "capability": f"{len(tech_debt_caps)} capabilities",
                    "risk_level": "MEDIUM",
                    "risk_factors": ["TECHNOLOGY_DEBT"],
                    "recommendation": "Modernize aging applications and reduce technology debt",
                    "timeframe": "6 - 12 months",
                    "estimated_cost": "MEDIUM",
                }
            )

        return recommendations

    def _get_mitigation_recommendation(self, capability_risk: Dict) -> str:
        """Get specific mitigation recommendation for a capability."""

        risk_factors = capability_risk["risk_factors"]

        if "SINGLE_POINT_OF_FAILURE" in risk_factors:
            return f"Implement redundancy for {capability_risk['capability_name']} - currently supported by {capability_risk['coverage_count']} application(s)"
        elif "TECHNOLOGY_DEBT" in risk_factors:
            return f"Modernize technology stack for {capability_risk['capability_name']} - high technology debt detected"
        elif "COMPLIANCE_RISK" in risk_factors:
            return f"Address compliance issues for {capability_risk['capability_name']} - regulatory compliance gaps identified"
        elif "DEPENDENCY_RISK" in risk_factors:
            return f"Reduce dependency complexity for {capability_risk['capability_name']} - high integration complexity"
        elif "SKILL_GAP" in risk_factors:
            return f"Address skill gaps for {capability_risk['capability_name']} - resource constraints identified"
        else:
            return f"Monitor and mitigate risks for {capability_risk['capability_name']} - multiple risk factors identified"
