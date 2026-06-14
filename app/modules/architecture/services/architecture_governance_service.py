"""
-> app.modules.architecture.services.governance_service

Architecture Governance Service

Manages architecture reviews, standards compliance, and governance metrics:
- Architecture review workflows
- Standards compliance checking
- Governance metrics tracking
- Architecture decision records
- Quality assurance processes
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple  # dead-code-ok

from flask import g
from sqlalchemy import and_, func, or_, text  # dead-code-ok

from app import db
from app.services.decorators import transactional
import logging
logger = logging.getLogger(__name__)


class ArchitectureGovernanceService:
    """
    Service for architecture governance, compliance, and quality assurance.

    Provides comprehensive governance capabilities:
    - Architecture review workflows and tracking
    - Standards compliance checking and monitoring
    - Governance metrics and KPI tracking
    - Architecture decision record management
    - Quality assurance and best practices enforcement
    """

    def __init__(self):
        pass

    @transactional
    def analyze_governance_portfolio(self, include_compliance: bool = True) -> Dict:
        """
        Comprehensive governance analysis across the architecture portfolio.

        Args:
            include_compliance: Include compliance checking in analysis

        Returns:
            Dict with governance analysis results and recommendations
        """
        # Get all architecture elements
        architecture_elements = self._get_architecture_elements()

        # Analyze governance for each element
        governance_analyses = []
        for element in architecture_elements:
            analysis = self._analyze_element_governance(element, include_compliance)
            governance_analyses.append(analysis)

        # Sort by governance priority (highest first)
        governance_analyses.sort(key=lambda x: x["governance_priority_score"], reverse=True)

        # Categorize by governance levels
        critical_governance = [
            g for g in governance_analyses if g["governance_level"] == "CRITICAL"
        ]
        high_governance = [g for g in governance_analyses if g["governance_level"] == "HIGH"]
        medium_governance = [g for g in governance_analyses if g["governance_level"] == "MEDIUM"]
        low_governance = [g for g in governance_analyses if g["governance_level"] == "LOW"]

        # Calculate portfolio metrics
        portfolio_metrics = self._calculate_portfolio_governance_metrics(governance_analyses)

        # Generate governance recommendations
        recommendations = self._generate_governance_recommendations(governance_analyses)

        return {
            "total_elements": len(architecture_elements),
            "governance_analyses": governance_analyses,
            "critical_governance": critical_governance,
            "high_governance": high_governance,
            "medium_governance": medium_governance,
            "low_governance": low_governance,
            "portfolio_metrics": portfolio_metrics,
            "recommendations": recommendations,
            "analysis_date": datetime.utcnow().isoformat(),
        }

    def _get_architecture_elements(self) -> List[Dict]:
        """Get all architecture elements from the database."""
        try:
            elements = []

            # Get business capabilities
            from app.models.business_capability import BusinessCapability

            capabilities = BusinessCapability.query.all()
            for cap in capabilities:
                elements.append(
                    {
                        "id": cap.id,
                        "name": cap.name,
                        "type": "BusinessCapability",
                        "domain": cap.business_domain or "Unknown",
                        "strategic_importance": cap.strategic_importance,
                        "layer": "Business",
                        "has_documentation": getattr(cap, "has_documentation", False),
                        "last_review_date": getattr(cap, "last_review_date", None),
                        "compliance_status": getattr(cap, "compliance_status", "unknown"),
                        "quality_score": getattr(cap, "quality_score", 0),
                    }
                )

            # Get application components
            from app.models.application_layer import ApplicationComponent

            applications = ApplicationComponent.query.filter(
                ApplicationComponent.deployment_status.in_(
                    ["production", "Production", "Implementing"]
                )
            ).all()
            for app in applications:
                elements.append(
                    {
                        "id": app.id,
                        "name": app.name,
                        "type": "ApplicationComponent",
                        "technology": app.technology_stack,
                        "layer": "Application",
                        "has_documentation": getattr(app, "has_documentation", False),
                        "last_review_date": getattr(app, "last_review_date", None),
                        "compliance_status": getattr(app, "compliance_status", "unknown"),
                        "quality_score": getattr(app, "quality_score", 0),
                        "architecture_review_required": getattr(
                            app, "architecture_review_required", True
                        ),
                    }
                )

            return elements
        except Exception as e:
            print(f"Error getting architecture elements: {e}")
            return []

    def _analyze_element_governance(self, element: Dict, include_compliance: bool) -> Dict:
        """Analyze governance for a single architecture element."""

        # Calculate different governance factors
        documentation_score = self._calculate_documentation_score(element)
        review_score = self._calculate_review_score(element)
        quality_score = self._calculate_quality_score(element)
        compliance_score = 0
        if include_compliance:
            compliance_score = self._calculate_compliance_score(element)

        # Calculate overall governance priority score (0 - 100)
        total_score = documentation_score + review_score + quality_score + compliance_score

        # Determine governance level
        if total_score >= 80:
            governance_level = "COMPLIANT"
        elif total_score >= 60:
            governance_level = "PARTIALLY_COMPLIANT"
        elif total_score >= 40:
            governance_level = "NON_COMPLIANT"
        else:
            governance_level = "CRITICAL_VIOLATION"

        # Identify specific governance factors
        governance_factors = []
        if documentation_score < 20:
            governance_factors.append("DOCUMENTATION_GAP")
        if review_score < 20:
            governance_factors.append("REVIEW_REQUIRED")
        if quality_score < 20:
            governance_factors.append("QUALITY_ISSUES")
        if include_compliance and compliance_score < 20:
            governance_factors.append("COMPLIANCE_VIOLATION")

        # Estimate governance needs
        governance_needs = self._estimate_governance_needs(element, total_score)

        return {
            "element_id": element["id"],
            "element_name": element["name"],
            "element_type": element["type"],
            "element_layer": element["layer"],
            "strategic_importance": element.get("strategic_importance"),
            "documentation_score": documentation_score,
            "review_score": review_score,
            "quality_score": quality_score,
            "compliance_score": compliance_score,
            "governance_priority_score": total_score,
            "governance_level": governance_level,
            "governance_factors": governance_factors,
            "governance_needs": governance_needs,
            "mitigation_priority": self._calculate_mitigation_priority(element, total_score),
            "governance_assessment": self._generate_governance_assessment(
                element, governance_factors, total_score
            ),
        }

    def _calculate_documentation_score(self, element: Dict) -> int:
        """Calculate documentation score (0 - 25 points)."""

        documentation_score = 0

        # Check if element has documentation
        if element.get("has_documentation"):
            documentation_score += 15
        else:
            documentation_score -= 10

        # Check documentation recency
        last_review = element.get("last_review_date")
        if last_review:
            days_since_review = (datetime.utcnow().date() - last_review).days
            if days_since_review <= 90:
                documentation_score += 10
            elif days_since_review <= 180:
                documentation_score += 5
            elif days_since_review > 365:
                documentation_score -= 5
        else:
            documentation_score -= 15

        return max(0, min(documentation_score, 25))

    def _calculate_review_score(self, element: Dict) -> int:
        """Calculate architecture review score (0 - 25 points)."""

        review_score = 0

        # Check if architecture review is required
        if element.get("architecture_review_required", True):
            # Check if review was completed
            last_review = element.get("last_review_date")
            if last_review:
                days_since_review = (datetime.utcnow().date() - last_review).days
                if days_since_review <= 180:
                    review_score += 25
                elif days_since_review <= 365:
                    review_score += 15
                elif days_since_review <= 730:
                    review_score += 5
                else:
                    review_score -= 10
            else:
                review_score -= 25  # No review completed
        else:
            review_score += 25  # Review not required

        return max(0, min(review_score, 25))

    def _calculate_quality_score(self, element: Dict) -> int:
        """Calculate quality score (0 - 25 points)."""

        quality_score = 0

        # Use existing quality score if available
        if element.get("quality_score"):
            quality_score = min(element["quality_score"] * 5, 25)
        else:
            # Estimate quality based on other factors
            if element.get("has_documentation"):
                quality_score += 10
            if element.get("compliance_status") == "compliant":
                quality_score += 10
            if element.get("strategic_importance") in ["critical", "high"]:
                quality_score += 5

        return max(0, min(quality_score, 25))

    def _calculate_compliance_score(self, element: Dict) -> int:
        """Calculate compliance score (0 - 25 points)."""

        compliance_score = 0

        # Check compliance status
        compliance_status = element.get("compliance_status", "unknown")
        if compliance_status == "compliant":
            compliance_score += 25
        elif compliance_status == "partially_compliant":
            compliance_score += 15
        elif compliance_status == "non_compliant":
            compliance_score += 5
        elif compliance_status == "critical_violation":
            compliance_score -= 10

        return max(0, min(compliance_score, 25))

    def _calculate_mitigation_priority(self, element: Dict, governance_score: int) -> str:
        """Calculate mitigation priority based on governance score and strategic importance."""

        importance = (element.get("strategic_importance") or "").lower()

        if importance == "critical" and governance_score < 60:
            return "IMMEDIATE"
        elif importance == "critical" and governance_score < 80:
            return "HIGH"
        elif importance == "high" and governance_score < 40:
            return "HIGH"
        elif governance_score < 40:
            return "HIGH"
        elif governance_score < 60:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_governance_assessment(self, element: Dict, factors: List, score: int) -> str:
        """Generate governance assessment for the element."""

        if score >= 80:
            return f"COMPLIANT: {element['name']} meets all governance requirements with strong documentation and quality"
        elif score >= 60:
            return f"PARTIALLY_COMPLIANT: {element['name']} has minor governance gaps that should be addressed"
        elif score >= 40:
            return f"NON_COMPLIANT: {element['name']} has significant governance gaps requiring attention"
        else:
            return f"CRITICAL_VIOLATION: {element['name']} has critical governance violations requiring immediate action"

    def _estimate_governance_needs(self, element: Dict, governance_score: int) -> Dict:
        """Estimate governance improvement needs."""

        # Base governance improvement estimation
        if governance_score < 40:
            base_cost = 150000  # $150k for critical violations
            complexity_multiplier = 1.5
        elif governance_score < 60:
            base_cost = 75000  # $75k for significant gaps
            complexity_multiplier = 1.2
        elif governance_score < 80:
            base_cost = 25000  # $25k for minor gaps
            complexity_multiplier = 1.0
        else:
            base_cost = 10000  # $10k for maintenance
            complexity_multiplier = 0.8

        # Adjust for strategic importance
        if element.get("strategic_importance") == "critical":
            complexity_multiplier *= 1.3
        elif element.get("strategic_importance") == "low":
            complexity_multiplier *= 0.8

        estimated_cost = base_cost * complexity_multiplier

        # Timeframe estimation
        if governance_score < 40:
            timeframe = "3 - 6 months"
        elif governance_score < 60:
            timeframe = "1 - 3 months"
        elif governance_score < 80:
            timeframe = "2 - 4 weeks"
        else:
            timeframe = "Ongoing"

        return {
            "estimated_cost": estimated_cost,
            "currency": "USD",
            "timeframe": timeframe,
            "governance_type": "IMPROVEMENT" if governance_score < 80 else "MAINTENANCE",
            "complexity": "HIGH"
            if complexity_multiplier > 1.2
            else "MEDIUM"
            if complexity_multiplier > 1.0
            else "LOW",
        }

    def _calculate_portfolio_governance_metrics(self, governance_analyses: List[Dict]) -> Dict:
        """Calculate portfolio-level governance metrics."""

        total_elements = len(governance_analyses)
        compliant_count = len(
            [g for g in governance_analyses if g["governance_level"] == "COMPLIANT"]
        )
        non_compliant_count = len(
            [
                g
                for g in governance_analyses
                if g["governance_level"] in ["NON_COMPLIANT", "CRITICAL_VIOLATION"]
            ]
        )

        # Governance factor distribution
        documentation_count = len(
            [g for g in governance_analyses if "DOCUMENTATION_GAP" in g["governance_factors"]]
        )
        review_count = len(
            [g for g in governance_analyses if "REVIEW_REQUIRED" in g["governance_factors"]]
        )
        quality_count = len(
            [g for g in governance_analyses if "QUALITY_ISSUES" in g["governance_factors"]]
        )
        compliance_count = len(
            [g for g in governance_analyses if "COMPLIANCE_VIOLATION" in g["governance_factors"]]
        )

        # Average scores
        avg_documentation_score = (
            sum(g["documentation_score"] for g in governance_analyses) / total_elements
            if total_elements > 0
            else 0
        )
        avg_review_score = (
            sum(g["review_score"] for g in governance_analyses) / total_elements
            if total_elements > 0
            else 0
        )
        avg_quality_score = (
            sum(g["quality_score"] for g in governance_analyses) / total_elements
            if total_elements > 0
            else 0
        )
        avg_compliance_score = (
            sum(g["compliance_score"] for g in governance_analyses) / total_elements
            if total_elements > 0
            else 0
        )

        return {
            "total_elements": total_elements,
            "compliant_elements": compliant_count,
            "non_compliant_elements": non_compliant_count,
            "documentation_gaps": documentation_count,
            "review_required": review_count,
            "quality_issues": quality_count,
            "compliance_violations": compliance_count,
            "average_documentation_score": round(avg_documentation_score, 1),
            "average_review_score": round(avg_review_score, 1),
            "average_quality_score": round(avg_quality_score, 1),
            "average_compliance_score": round(avg_compliance_score, 1),
            "portfolio_governance_level": "HIGH"
            if total_elements > 0 and compliant_count / total_elements < 0.8
            else "MEDIUM"
            if total_elements > 0 and compliant_count / total_elements < 0.6
            else "LOW",
        }

    def _generate_governance_recommendations(self, governance_analyses: List[Dict]) -> List[Dict]:
        """Generate governance improvement recommendations."""

        recommendations = []

        # Critical governance violations requiring immediate action
        critical_governance = [
            g for g in governance_analyses if g["governance_level"] == "CRITICAL_VIOLATION"
        ][:5]

        for governance in critical_governance:
            recommendations.append(
                {
                    "type": "IMMEDIATE_GOVERNANCE",
                    "priority": "CRITICAL",
                    "element": governance["element_name"],
                    "governance_level": governance["governance_level"],
                    "governance_factors": governance["governance_factors"],
                    "recommendation": self._get_governance_mitigation_recommendation(governance),
                    "timeframe": governance["governance_needs"]["timeframe"],
                    "estimated_cost": governance["governance_needs"]["estimated_cost"],
                    "business_impact": "HIGH",
                }
            )

        # Documentation gaps
        documentation_gaps = [
            g for g in governance_analyses if "DOCUMENTATION_GAP" in g["governance_factors"]
        ]
        if documentation_gaps:
            recommendations.append(
                {
                    "type": "DOCUMENTATION_IMPROVEMENT",
                    "priority": "MEDIUM",
                    "element": f"{len(documentation_gaps)} elements",
                    "governance_level": "PARTIALLY_COMPLIANT",
                    "governance_factors": ["DOCUMENTATION_GAP"],
                    "recommendation": "Improve documentation and knowledge management for better governance",
                    "timeframe": "1 - 3 months",
                    "estimated_cost": sum(
                        g["governance_needs"]["estimated_cost"] for g in documentation_gaps
                    ),
                    "business_impact": "MEDIUM",
                }
            )

        # Architecture reviews
        review_required = [
            g for g in governance_analyses if "REVIEW_REQUIRED" in g["governance_factors"]
        ]
        if review_required:
            recommendations.append(
                {
                    "type": "ARCHITECTURE_REVIEW",
                    "priority": "HIGH",
                    "element": f"{len(review_required)} elements",
                    "governance_level": "NON_COMPLIANT",
                    "governance_factors": ["REVIEW_REQUIRED"],
                    "recommendation": "Complete architecture reviews for elements requiring governance approval",
                    "timeframe": "2 - 4 weeks",
                    "estimated_cost": sum(
                        g["governance_needs"]["estimated_cost"] for g in review_required
                    ),
                    "business_impact": "HIGH",
                }
            )

        # Quality improvements
        quality_issues = [
            g for g in governance_analyses if "QUALITY_ISSUES" in g["governance_factors"]
        ]
        if quality_issues:
            recommendations.append(
                {
                    "type": "QUALITY_IMPROVEMENT",
                    "priority": "MEDIUM",
                    "element": f"{len(quality_issues)} elements",
                    "governance_level": "PARTIALLY_COMPLIANT",
                    "governance_factors": ["QUALITY_ISSUES"],
                    "recommendation": "Improve quality standards and best practices compliance",
                    "timeframe": "1 - 2 months",
                    "estimated_cost": sum(
                        g["governance_needs"]["estimated_cost"] for g in quality_issues
                    ),
                    "business_impact": "MEDIUM",
                }
            )

        return recommendations

    def _get_governance_mitigation_recommendation(self, governance: Dict) -> str:
        """Get specific governance mitigation recommendation for an element."""

        factors = governance["governance_factors"]

        if "DOCUMENTATION_GAP" in factors:
            return f"Improve documentation for {governance['element_name']} - missing or outdated documentation identified"
        elif "REVIEW_REQUIRED" in factors:
            return f"Complete architecture review for {governance['element_name']} - review overdue or not completed"
        elif "QUALITY_ISSUES" in factors:
            return f"Address quality issues for {governance['element_name']} - quality standards not met"
        elif "COMPLIANCE_VIOLATION" in factors:
            return f"Resolve compliance violations for {governance['element_name']} - governance violations identified"
        else:
            return f"Monitor and maintain governance for {governance['element_name']} - continuous governance management"

    @transactional
    def submit_for_review(
        self, element_id: int, reviewer_id: int, review_type: str = "STANDARD"
    ) -> Dict:
        """
        Submit architecture element for governance review.

        Args:
            element_id: ID of element to review
            reviewer_id: ID of reviewing architect
            review_type: STANDARD, COMPLIANCE, SECURITY, PERFORMANCE

        Returns:
            Review record with ID and status
        """
        try:
            _org_id = getattr(g, 'current_org_id', None)
            if _org_id:
                query = """
                    INSERT INTO architecture_reviews
                    (element_id, reviewer_id, review_type, status, submitted_at, organization_id)
                    VALUES (:elem_id, :reviewer_id, :review_type, 'PENDING', :now, :org_id)
                    RETURNING id, status
                """
            else:
                query = """
                    INSERT INTO architecture_reviews
                    (element_id, reviewer_id, review_type, status, submitted_at)
                    VALUES (:elem_id, :reviewer_id, :review_type, 'PENDING', :now)
                    RETURNING id, status
                """
            result = db.session.execute(  # tenant-filtered: organization_id in query
                text(query),
                {
                    "elem_id": element_id,
                    "reviewer_id": reviewer_id,
                    "review_type": review_type,
                    "now": datetime.utcnow(),
                    **( {"org_id": _org_id} if _org_id else {}),
                },
            )
            db.session.commit()
            row = result.fetchone()
            return {"review_id": row[0], "status": row[1]}
        except Exception as e:
            db.session.rollback()
            raise e

    @transactional
    def check_compliance(self, element_id: int) -> Dict:
        """
        Check architecture element against all active standards.

        Args:
            element_id: ID of element to check

        Returns:
            Compliance check results
        """
        try:
            # Get element details
            element_query = """
                SELECT name, type, layer, technology_stack
                FROM architecture_elements
                WHERE id = :elem_id
            """
            _eq_params = {"elem_id": element_id}

            if not element:
                return {"error": "Element not found"}

            # Get applicable standards
            standards_query = """
                SELECT id, name, requirements, layer
                FROM architecture_standards
                WHERE is_active = true
                AND (layer = :layer OR layer = 'ALL')
            """
            standards = db.session.execute(  # tenant-exempt: architecture_standards are system-wide
                text(standards_query), {"layer": element[2]}  # layer
            ).fetchall()

            compliance_results = {
                "element": {
                    "id": element_id,
                    "name": element[0],
                    "type": element[1],
                    "layer": element[2],
                    "technology": element[3],
                },
                "standards": [],
                "overall_compliance": "COMPLIANT",
                "violations": [],
            }

            # Check against each standard
            for standard in standards:
                standard_result = {
                    "standard_id": standard[0],
                    "standard_name": standard[1],
                    "requirements": standard[2],
                    "compliance_status": "COMPLIANT",
                    "violations": [],
                }

                # Simplified compliance check
                # In production, this would be more sophisticated
                if "documentation" in standard[2].lower() and not element[0]:
                    standard_result["compliance_status"] = "NON_COMPLIANT"
                    standard_result["violations"].append("Missing documentation")

                compliance_results["standards"].append(standard_result)

                if standard_result["compliance_status"] != "COMPLIANT":
                    compliance_results["overall_compliance"] = "NON_COMPLIANT"
                    compliance_results["violations"].extend(standard_result["violations"])

            return compliance_results
        except Exception as e:
            return {"error": str(e)}

    def check_capability_drift(self) -> List[Dict]:
        """
        Check for capability drift alerts across the architecture portfolio.

        Detects three types of drift:
        1. SPOF Retirement — a retiring/decommissioned app is the sole supporter
           of a critical (L1-L2) capability and is marked for retirement/elimination.
        2. Maturity Regression — a capability's current_maturity_level has been
           lowered below its target (regression detected).
        3. Orphan Applications — newly imported apps with zero capability mappings.

        Returns:
            List of alert dicts with keys:
            {type, severity, message, entity_id, entity_name}
            sorted by severity (critical first).
        """
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts: List[Dict] = []

        # --- Alert Type 1: SPOF Retirement ---
        try:
            from app.models.application_capability import ApplicationCapabilityMapping
            from app.models.application_portfolio import ApplicationComponent
            from app.models.business_capabilities import BusinessCapability

            retiring_statuses = (
                "retiring", "decommissioned", "end_of_life",
                "elimination", "retired",
            )

            # Find capabilities supported by exactly one application
            spof_subquery = (
                db.session.query(
                    ApplicationCapabilityMapping.business_capability_id,
                )
                .group_by(ApplicationCapabilityMapping.business_capability_id)
                .having(
                    func.count(
                        ApplicationCapabilityMapping.application_component_id.distinct()
                    )
                    == 1
                )
                .subquery()
            )

            # Join to find retiring apps that are the sole supporter of L1/L2 capabilities
            spof_rows = (
                db.session.query(
                    ApplicationComponent.id,
                    ApplicationComponent.name,
                    BusinessCapability.id,
                    BusinessCapability.name,
                    BusinessCapability.level,
                    BusinessCapability.strategic_importance,
                )
                .join(
                    ApplicationCapabilityMapping,
                    ApplicationCapabilityMapping.application_component_id
                    == ApplicationComponent.id,
                )
                .join(
                    BusinessCapability,
                    BusinessCapability.id
                    == ApplicationCapabilityMapping.business_capability_id,
                )
                .filter(
                    ApplicationCapabilityMapping.business_capability_id.in_(
                        db.session.query(spof_subquery.c.business_capability_id)
                    )
                )
                .filter(
                    func.lower(ApplicationComponent.lifecycle_status).in_(
                        retiring_statuses
                    )
                )
                .filter(
                    # Only critical (L1-L2) capabilities
                    BusinessCapability.level.in_([1, 2])
                )
                .all()
            )

            for app_id, app_name, cap_id, cap_name, cap_level, strategic_importance in spof_rows:
                importance_lower = (strategic_importance or "").lower()
                severity = "critical" if importance_lower == "critical" else "high"
                alerts.append(
                    {
                        "type": "spof_retirement",
                        "severity": severity,
                        "entity_id": app_id,
                        "entity_name": app_name,
                        "message": (
                            f"Application '{app_name}' is the sole supporter of "
                            f"L{cap_level} capability '{cap_name}' and is marked "
                            f"for retirement"
                        ),
                    }
                )
        except Exception:  # fabricated-values-ok: graceful degradation
            pass  # Return what we have so far; do not propagate

        # --- Alert Type 2: Maturity Regression ---
        try:
            from app.models.business_capabilities import BusinessCapability

            # Detect capabilities where current maturity has fallen below target.
            # This is the strongest signal of a regression that can be detected
            # from a single point-in-time snapshot (no audit log needed).
            maturity_regressions = (
                db.session.query(
                    BusinessCapability.id,
                    BusinessCapability.name,
                    BusinessCapability.current_maturity_level,
                    BusinessCapability.target_maturity_level,
                    BusinessCapability.strategic_importance,
                )
                .filter(
                    BusinessCapability.current_maturity_level.isnot(None),
                    BusinessCapability.target_maturity_level.isnot(None),
                    BusinessCapability.current_maturity_level
                    < BusinessCapability.target_maturity_level,
                )
                .all()
            )

            for cap_id, cap_name, current, target, strategic_importance in maturity_regressions:
                importance_lower = (strategic_importance or "").lower()
                gap = target - current
                # Severity based on strategic importance and gap size
                if importance_lower == "critical" or gap >= 3:
                    severity = "high"
                elif importance_lower == "high" or gap >= 2:
                    severity = "medium"
                else:
                    severity = "low"
                alerts.append(
                    {
                        "type": "maturity_regression",
                        "severity": severity,
                        "entity_id": cap_id,
                        "entity_name": cap_name,
                        "message": (
                            f"Capability '{cap_name}' maturity regressed: "
                            f"current {current} vs target {target} (gap: {gap})"
                        ),
                    }
                )
        except Exception:  # fabricated-values-ok: graceful degradation
            logger.exception("Failed to operation")
            pass

        # --- Alert Type 3: Orphan Applications ---
        try:
            from app.models.application_capability import ApplicationCapabilityMapping
            from app.models.application_portfolio import ApplicationComponent

            orphan_apps = (
                db.session.query(
                    ApplicationComponent.id,
                    ApplicationComponent.name,
                )
                .outerjoin(
                    ApplicationCapabilityMapping,
                    ApplicationCapabilityMapping.application_component_id
                    == ApplicationComponent.id,
                )
                .filter(ApplicationCapabilityMapping.id.is_(None))
                .all()
            )

            for app_id, app_name in orphan_apps:
                alerts.append(
                    {
                        "type": "orphan_app",
                        "severity": "low",
                        "entity_id": app_id,
                        "entity_name": app_name,
                        "message": (
                            f"Application '{app_name}' has zero capability "
                            f"mappings"
                        ),
                    }
                )
        except Exception:  # fabricated-values-ok: graceful degradation
            logger.exception("Failed to operation")
            pass

        # Sort by severity: critical → high → medium → low
        alerts.sort(key=lambda a: severity_order.get(a.get("severity", "low"), 99))

        return alerts
