"""
Compliance Tracking Service

Tracks regulatory compliance across business capabilities and applications:
- Regulatory requirement mapping
- Compliance status monitoring
- Audit trail management
- Risk assessment and mitigation
- Compliance reporting and dashboards
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db
from app.services.decorators import transactional


class ComplianceTrackingService:
    """
    Service for comprehensive compliance tracking and management.

    Provides compliance analysis across:
    - Regulatory requirements mapping
    - Compliance status monitoring
    - Audit trail maintenance
    - Risk assessment and mitigation
    - Compliance reporting and visualization
    """

    def __init__(self):
        pass

    @transactional
    def analyze_compliance_portfolio(self, include_risk_assessment: bool = True) -> Dict:
        """
        Comprehensive compliance analysis across the entire portfolio.

        Args:
            include_risk_assessment: Include risk assessment in compliance analysis

        Returns:
            Dict with compliance tracking results and recommendations
        """
        # Get all business capabilities
        capabilities = self._get_all_capabilities()

        # Analyze compliance for each capability
        capability_compliance = []
        for capability in capabilities:
            compliance_data = self._analyze_capability_compliance(
                capability, include_risk_assessment
            )
            capability_compliance.append(compliance_data)

        # Sort by compliance risk (highest first, use risk_score or overall_compliance_score)
        capability_compliance.sort(
            key=lambda x: x.get("risk_score") or x.get("overall_compliance_score") or 0,
            reverse=True,
        )

        # Categorize by compliance levels
        critical_compliance = [
            c for c in capability_compliance if c["compliance_level"] == "CRITICAL"
        ]
        high_compliance = [c for c in capability_compliance if c["compliance_level"] == "HIGH"]
        medium_compliance = [c for c in capability_compliance if c["compliance_level"] == "MEDIUM"]
        low_compliance = [c for c in capability_compliance if c["compliance_level"] == "LOW"]

        # Calculate portfolio metrics
        portfolio_metrics = self._calculate_portfolio_compliance_metrics(capability_compliance)

        # Generate compliance recommendations
        recommendations = self._generate_compliance_recommendations(capability_compliance)

        return {
            "total_capabilities": len(capabilities),
            "capability_compliance": capability_compliance,
            "critical_compliance": critical_compliance,
            "high_compliance": high_compliance,
            "medium_compliance": medium_compliance,
            "low_compliance": low_compliance,
            "portfolio_metrics": portfolio_metrics,
            "recommendations": recommendations,
            "assessment_date": datetime.utcnow().isoformat(),
        }

    def _analyze_capability_compliance(self, capability, include_risk: bool) -> Dict:
        """Analyze compliance for a single capability."""

        # Get application coverage
        app_mappings = self._get_capability_applications(capability["id"])

        # Calculate different compliance factors
        regulatory_score = self._calculate_regulatory_score(capability)
        application_score = self._calculate_application_compliance_score(app_mappings)
        audit_score = self._calculate_audit_score(capability, app_mappings)
        risk_score = 0
        if include_risk:
            risk_score = self._calculate_compliance_risk_score(capability, app_mappings)

        # Calculate overall compliance score (0 - 100)
        overall_compliance_score = regulatory_score + application_score + audit_score + risk_score

        # Determine compliance level
        if overall_compliance_score >= 80:
            compliance_level = "COMPLIANT"
        elif overall_compliance_score >= 60:
            compliance_level = "PARTIALLY_COMPLIANT"
        elif overall_compliance_score >= 40:
            compliance_level = "NON_COMPLIANT"
        else:
            compliance_level = "CRITICAL_VIOLATION"

        # Identify specific compliance factors
        compliance_factors = []
        if regulatory_score < 20:
            compliance_factors.append("REGULATORY_GAP")
        if application_score < 20:
            compliance_factors.append("APPLICATION_COMPLIANCE")
        if audit_score < 15:
            compliance_factors.append("AUDIT_DEFICIENCY")
        if risk_score >= 15:
            compliance_factors.append("COMPLIANCE_RISK")

        # Estimate compliance improvement needs
        compliance_needs = self._estimate_compliance_needs(capability, overall_compliance_score)

        return {
            "capability_id": capability["id"],
            "capability_name": capability["name"],
            "capability_domain": capability["domain"],
            "strategic_importance": capability.get("strategic_importance"),
            "coverage_count": len(app_mappings),
            "regulatory_score": regulatory_score,
            "application_score": application_score,
            "audit_score": audit_score,
            "risk_score": risk_score,
            "overall_compliance_score": overall_compliance_score,
            "compliance_level": compliance_level,
            "compliance_factors": compliance_factors,
            "compliance_needs": compliance_needs,
            "mitigation_priority": self._calculate_mitigation_priority(
                capability, overall_compliance_score
            ),
            "compliance_assessment": self._generate_compliance_assessment(
                capability, compliance_factors, overall_compliance_score
            ),
        }

    def _calculate_regulatory_score(self, capability: Dict) -> int:
        """Calculate regulatory compliance score (0 - 25 points)."""
        regulatory_score = 0

        # Check for regulatory requirements
        if capability.get("regulatory_requirements"):
            req_count = len(capability["regulatory_requirements"])
            regulatory_score += min(req_count * 5, 20)
        else:
            regulatory_score -= 10  # No regulatory requirements identified

        # Check for regulated data handling
        if capability.get("handles_pii"):
            regulatory_score += 5
        if capability.get("handles_financial_data"):
            regulatory_score += 5
        if capability.get("handles_health_data"):
            regulatory_score += 5
        if capability.get("handles_personal_data"):
            regulatory_score += 5

        return min(regulatory_score, 25)

    def _calculate_application_compliance_score(self, app_mappings: List) -> int:
        """Calculate application compliance score (0 - 25 points)."""
        if not app_mappings:
            return 0

        compliance_score = 0

        # Check application compliance status
        compliant_apps = [
            m
            for m in app_mappings
            if hasattr(m, "compliance_status") and m.compliance_status == "compliant"
        ]
        if compliant_apps:
            compliance_score += len(compliant_apps) * 5

        # Check for non-compliant applications
        non_compliant_apps = [
            m
            for m in app_mappings
            if hasattr(m, "compliance_status") and m.compliance_status == "non_compliant"
        ]
        if non_compliant_apps:
            compliance_score -= len(non_compliant_apps) * 3

        # Check for compliance certification
        certified_apps = [
            m
            for m in app_mappings
            if hasattr(m, "compliance_certification") and m.compliance_certification
        ]
        if certified_apps:
            compliance_score += len(certified_apps) * 2

        return max(0, min(compliance_score, 25))

    def _calculate_audit_score(self, capability: Dict, app_mappings: List) -> int:
        """Calculate audit trail score (0 - 25 points)."""
        audit_score = 0

        # Check for audit documentation
        if capability.get("has_audit_trail"):
            audit_score += 10
        else:
            audit_score -= 10

        # Check for last audit date
        if capability.get("last_audit_date"):
            days_since_audit = (datetime.utcnow().date() - capability["last_audit_date"]).days
            if days_since_audit > 365:
                audit_score -= 5
            elif days_since_audit > 180:
                audit_score -= 2
        else:
            audit_score -= 15

        # Check for audit findings
        if capability.get("open_audit_findings"):
            findings_count = len(capability["open_audit_findings"])
            audit_score -= min(findings_count * 2, 10)

        return max(0, min(audit_score, 25))

    def _calculate_compliance_risk_score(self, capability: Dict, app_mappings: List) -> int:
        """Calculate compliance risk score (0 - 25 points)."""
        risk_score = 0

        # Check for high-risk regulatory areas
        if capability.get("handles_pii") and not capability.get("privacy_controls"):
            risk_score += 10
        if capability.get("handles_financial_data") and not capability.get("sox_controls"):
            risk_score += 10
        if capability.get("handles_health_data") and not capability.get("hipaa_controls"):
            risk_score += 10

        # Check for compliance violations
        if capability.get("compliance_violations"):
            violation_count = len(capability["compliance_violations"])
            risk_score += min(violation_count * 3, 15)

        # Check for single point of compliance failure
        if len(app_mappings) == 1 and (capability.get("strategic_importance") or "").lower() in [
            "critical",
            "high",
        ]:
            risk_score += 10

        return min(risk_score, 25)

    def _calculate_mitigation_priority(self, capability: Dict, compliance_score: int) -> str:
        """Calculate mitigation priority based on compliance score and strategic importance."""
        importance = (capability.get("strategic_importance") or "").lower()

        if importance == "critical" and compliance_score < 60:
            return "IMMEDIATE"
        elif importance == "critical" and compliance_score < 80:
            return "HIGH"
        elif importance == "high" and compliance_score < 40:
            return "HIGH"
        elif compliance_score < 40:
            return "HIGH"
        elif compliance_score < 60:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_compliance_assessment(self, capability: Dict, factors: List, score: int) -> str:
        """Generate compliance assessment description."""

        if score >= 80:
            return f"COMPLIANT: {capability['name']} meets all regulatory requirements with strong controls"
        elif score >= 60:
            return f"PARTIALLY_COMPLIANT: {capability['name']} has minor compliance gaps that should be addressed"
        elif score >= 40:
            return f"NON_COMPLIANT: {capability['name']} has significant compliance gaps requiring attention"
        else:
            return f"CRITICAL_VIOLATION: {capability['name']} has critical compliance violations requiring immediate action"

    def _estimate_compliance_needs(self, capability: Dict, compliance_score: int) -> Dict:
        """Estimate compliance improvement needs."""

        # Base compliance improvement estimation
        if compliance_score < 40:
            base_cost = 300000  # $300k for critical violations
            complexity_multiplier = 1.5
        elif compliance_score < 60:
            base_cost = 150000  # $150k for significant gaps
            complexity_multiplier = 1.2
        elif compliance_score < 80:
            base_cost = 75000  # $75k for minor gaps
            complexity_multiplier = 1.0
        else:
            base_cost = 25000  # $25k for maintenance
            complexity_multiplier = 0.8

        # Adjust for regulatory complexity
        if capability.get("regulatory_complexity") == "HIGH":
            complexity_multiplier *= 1.3
        elif capability.get("regulatory_complexity") == "LOW":
            complexity_multiplier *= 0.8

        estimated_cost = base_cost * complexity_multiplier

        # Timeframe estimation
        if compliance_score < 40:
            timeframe = "6 - 12 months"
        elif compliance_score < 60:
            timeframe = "3 - 6 months"
        elif compliance_score < 80:
            timeframe = "1 - 3 months"
        else:
            timeframe = "Ongoing"

        return {
            "estimated_cost": estimated_cost,
            "currency": "USD",
            "timeframe": timeframe,
            "compliance_type": "IMPROVEMENT" if compliance_score < 80 else "MAINTENANCE",
            "complexity": "HIGH"
            if complexity_multiplier > 1.2
            else "MEDIUM"
            if complexity_multiplier > 1.0
            else "LOW",
        }

    def _get_all_capabilities(self) -> List[Dict]:
        """Get all business capabilities from the database."""
        # This would be adapted to work with your current capability model
        try:
            from app.models.business_capability import BusinessCapability

            capabilities = BusinessCapability.query.all()

            return [
                {
                    "id": cap.id,
                    "name": cap.name,
                    "domain": cap.business_domain or "Unknown",
                    "strategic_importance": cap.strategic_importance,
                    "description": cap.description,
                    "regulatory_requirements": getattr(cap, "regulatory_requirements", []),
                    "handles_pii": getattr(cap, "handles_pii", False),
                    "handles_financial_data": getattr(cap, "handles_financial_data", False),
                    "handles_health_data": getattr(cap, "handles_health_data", False),
                    "handles_personal_data": getattr(cap, "handles_personal_data", False),
                    "privacy_controls": getattr(cap, "privacy_controls", False),
                    "sox_controls": getattr(cap, "sox_controls", False),
                    "hipaa_controls": getattr(cap, "hipaa_controls", False),
                    "has_audit_trail": getattr(cap, "has_audit_trail", False),
                    "last_audit_date": getattr(cap, "last_audit_date", None),
                    "open_audit_findings": getattr(cap, "open_audit_findings", []),
                    "compliance_violations": getattr(cap, "compliance_violations", []),
                    "regulatory_complexity": getattr(cap, "regulatory_complexity", "MEDIUM"),
                }
                for cap in capabilities
            ]
        except Exception as e:
            print(f"Error getting capabilities: {e}")
            return []

    def _get_capability_applications(self, capability_id: int) -> List:
        """Get applications supporting a capability."""
        try:
            from app.models.application_portfolio import ApplicationCapabilityMapping

            mappings = ApplicationCapabilityMapping.query.filter_by(
                business_capability_id=capability_id
            ).all()
            return mappings
        except Exception as e:
            print(f"Error getting capability applications: {e}")
            return []

    def _calculate_portfolio_compliance_metrics(self, capability_compliance: List[Dict]) -> Dict:
        """Calculate portfolio-level compliance metrics."""

        total_capabilities = len(capability_compliance)
        compliant_count = len(
            [c for c in capability_compliance if c["compliance_level"] == "COMPLIANT"]
        )
        non_compliant_count = len(
            [
                c
                for c in capability_compliance
                if c["compliance_level"] in ["NON_COMPLIANT", "CRITICAL_VIOLATION"]
            ]
        )

        # Compliance factor distribution
        regulatory_count = len(
            [c for c in capability_compliance if "REGULATORY_GAP" in c["compliance_factors"]]
        )
        application_count = len(
            [
                c
                for c in capability_compliance
                if "APPLICATION_COMPLIANCE" in c["compliance_factors"]
            ]
        )
        audit_count = len(
            [c for c in capability_compliance if "AUDIT_DEFICIENCY" in c["compliance_factors"]]
        )

        # Average scores
        avg_regulatory_score = (
            sum(c["regulatory_score"] for c in capability_compliance) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_application_score = (
            sum(c["application_score"] for c in capability_compliance) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_audit_score = (
            sum(c["audit_score"] for c in capability_compliance) / total_capabilities
            if total_capabilities > 0
            else 0
        )
        avg_risk_score = (
            sum(c["risk_score"] for c in capability_compliance) / total_capabilities
            if total_capabilities > 0
            else 0
        )

        return {
            "total_capabilities": total_capabilities,
            "compliant_capabilities": compliant_count,
            "non_compliant_capabilities": non_compliant_count,
            "regulatory_gaps": regulatory_count,
            "application_compliance_issues": application_count,
            "audit_deficiencies": audit_count,
            "average_regulatory_score": round(avg_regulatory_score, 1),
            "average_application_score": round(avg_application_score, 1),
            "average_audit_score": round(avg_audit_score, 1),
            "average_risk_score": round(avg_risk_score, 1),
            "portfolio_compliance_level": "HIGH"
            if total_capabilities > 0 and compliant_count / total_capabilities < 0.8
            else "MEDIUM"
            if total_capabilities > 0 and compliant_count / total_capabilities < 0.6
            else "LOW",
        }

    def _generate_compliance_recommendations(self, capability_compliance: List[Dict]) -> List[Dict]:
        """Generate compliance mitigation recommendations."""

        recommendations = []

        # Critical compliance violations requiring immediate action
        critical_compliance = [
            c for c in capability_compliance if c["compliance_level"] == "CRITICAL_VIOLATION"
        ][:5]

        for capability in critical_compliance:
            recommendations.append(
                {
                    "type": "IMMEDIATE_COMPLIANCE",
                    "priority": "CRITICAL",
                    "capability": capability["capability_name"],
                    "compliance_level": capability["compliance_level"],
                    "compliance_factors": capability["compliance_factors"],
                    "recommendation": self._get_compliance_mitigation_recommendation(capability),
                    "timeframe": capability["compliance_needs"]["timeframe"],
                    "estimated_cost": capability["compliance_needs"]["estimated_cost"],
                    "regulatory_risk": "HIGH",
                }
            )

        # Non-compliant capabilities
        non_compliant_caps = [
            c
            for c in capability_compliance
            if c["compliance_level"] in ["NON_COMPLIANT", "CRITICAL_VIOLATION"]
        ]
        if non_compliant_caps:
            recommendations.append(
                {
                    "type": "COMPLIANCE_IMPROVEMENT",
                    "priority": "HIGH",
                    "capability": f"{len(non_compliant_caps)} capabilities",
                    "compliance_level": "NON_COMPLIANT",
                    "compliance_factors": ["REGULATORY_GAP", "APPLICATION_COMPLIANCE"],
                    "recommendation": "Address compliance gaps to meet regulatory requirements",
                    "timeframe": "3 - 6 months",
                    "estimated_cost": sum(
                        c["compliance_needs"]["estimated_cost"] for c in non_compliant_caps
                    ),
                    "regulatory_risk": "HIGH",
                }
            )

        # Audit deficiencies
        audit_deficient_caps = [
            c for c in capability_compliance if "AUDIT_DEFICIENCY" in c["compliance_factors"]
        ]
        if audit_deficient_caps:
            recommendations.append(
                {
                    "type": "AUDIT_IMPROVEMENT",
                    "priority": "MEDIUM",
                    "capability": f"{len(audit_deficient_caps)} capabilities",
                    "compliance_level": "PARTIALLY_COMPLIANT",
                    "compliance_factors": ["AUDIT_DEFICIENCY"],
                    "recommendation": "Improve audit trails and documentation for compliance verification",
                    "timeframe": "1 - 3 months",
                    "estimated_cost": sum(
                        c["compliance_needs"]["estimated_cost"] for c in audit_deficient_caps
                    ),
                    "regulatory_risk": "MEDIUM",
                }
            )

        return recommendations

    def _get_compliance_mitigation_recommendation(self, capability: Dict) -> str:
        """Get specific compliance mitigation recommendation for a capability."""

        factors = capability["compliance_factors"]

        if "REGULATORY_GAP" in factors:
            return f"Establish regulatory compliance framework for {capability['capability_name']} - missing regulatory requirements identified"
        elif "APPLICATION_COMPLIANCE" in factors:
            return f"Ensure application compliance for {capability['capability_name']} - non-compliant applications identified"
        elif "AUDIT_DEFICIENCY" in factors:
            return f"Improve audit trail for {capability['capability_name']} - audit documentation gaps identified"
        elif "COMPLIANCE_RISK" in factors:
            return f"Mitigate compliance risks for {capability['capability_name']} - high regulatory risk factors identified"
        else:
            return f"Monitor and maintain compliance for {capability['capability_name']} - continuous compliance management"
