"""
Risk Assessment Agent

Identifies implementation risks and mitigation strategies
with technology risk evaluation and business impact analysis.
"""

import logging
from typing import Any, Dict, List, Optional  # dead-code-ok

logger = logging.getLogger(__name__)


class RiskAssessmentAgent:
    """
    Agent for assessing risks in solution implementation.

    Identifies technical, business, and operational risks with
    mitigation strategies and impact analysis.
    """

    # Risk categories and types
    RISK_CATEGORIES = {
        "technical": {
            "description": "Technical implementation risks",
            "weight": 0.3,
            "types": {
                "complexity": "Solution complexity may exceed team capabilities",
                "integration": "Integration with existing systems may fail",
                "performance": "Performance requirements may not be met",
                "scalability": "Solution may not scale as expected",
                "security": "Security vulnerabilities may be introduced",
                "technology": "Chosen technology may not be suitable",
                "data_migration": "Data migration may fail or corrupt data",
                "testing": "Insufficient testing may lead to production issues",
            },
        },
        "business": {
            "description": "Business and organizational risks",
            "weight": 0.25,
            "types": {
                "budget_overrun": "Project may exceed allocated budget",
                "timeline_delay": "Project may miss critical deadlines",
                "adoption": "Users may resist adopting the solution",
                "requirements_change": "Requirements may change during development",
                "stakeholder_alignment": "Stakeholders may not align on objectives",
                "business_disruption": "Implementation may disrupt business operations",
                "roi": "Expected ROI may not be achieved",
                "compliance": "Solution may not meet compliance requirements",
            },
        },
        "operational": {
            "description": "Operational and maintenance risks",
            "weight": 0.2,
            "types": {
                "maintenance": "Solution may be difficult to maintain",
                "monitoring": "Insufficient monitoring may hide issues",
                "backup_recovery": "Backup and recovery may be inadequate",
                "documentation": "Poor documentation may hinder operations",
                "training": "Staff may lack required skills",
                "support": "Support processes may be inadequate",
                "capacity": "Operational capacity may be insufficient",
                "vendor_dependency": "Vendor dependency may create issues",
            },
        },
        "strategic": {
            "description": "Strategic and architectural risks",
            "weight": 0.25,
            "types": {
                "architecture_lockin": "Architecture may lock into specific patterns",
                "technology_obsolescence": "Chosen technology may become obsolete",
                "vendor_lockin": "Vendor lock-in may limit future options",
                "strategic_misalignment": "Solution may not align with strategy",
                "competitive_disadvantage": "Solution may create competitive disadvantage",
                "innovation_limitation": "Solution may limit future innovation",
                "scalability_mismatch": "Architecture may not match growth strategy",
                "compliance_evolution": "Solution may not adapt to evolving compliance",
            },
        },
    }

    # Risk levels and thresholds
    RISK_LEVELS = {
        "critical": {"threshold": 0.8, "color": "red", "action": "immediate"},
        "high": {"threshold": 0.6, "color": "orange", "action": "soon"},
        "medium": {"threshold": 0.4, "color": "yellow", "action": "planned"},
        "low": {"threshold": 0.2, "color": "green", "action": "monitor"},
    }

    # Mitigation strategies
    MITIGATION_STRATEGIES = {
        "technical": {
            "proof_of_concept": "Build proof of concept to validate technical approach",
            "incremental_development": "Develop incrementally to reduce complexity",
            "expert_consultation": "Consult technical experts for complex areas",
            "pilot_testing": "Run pilot tests before full deployment",
            "code_review": "Implement thorough code review process",
            "automated_testing": "Use automated testing to catch issues early",
            "performance_testing": "Conduct performance testing early and often",
            "security_audit": "Perform regular security audits",
        },
        "business": {
            "stakeholder_engagement": "Engage stakeholders regularly",
            "change_management": "Implement proper change management",
            "training_program": "Develop comprehensive training program",
            "phased_rollout": "Roll out solution in phases",
            "feedback_mechanisms": "Establish feedback mechanisms",
            "contingency_planning": "Create contingency plans for key risks",
            "regular_reporting": "Provide regular progress reports",
            "executive_sponsorship": "Secure executive sponsorship",
        },
        "operational": {
            "documentation": "Create comprehensive documentation",
            "monitoring_systems": "Implement robust monitoring systems",
            "backup_procedures": "Establish backup and recovery procedures",
            "support_team": "Build dedicated support team",
            "knowledge_transfer": "Plan knowledge transfer processes",
            "runbooks": "Create operational runbooks",
            "capacity_planning": "Plan for operational capacity",
            "service_level_agreements": "Define clear SLAs",
        },
        "strategic": {
            "architecture_review": "Regular architecture reviews",
            "technology_watch": "Monitor technology trends",
            "vendor_management": "Manage vendor relationships",
            "strategic_planning": "Include in strategic planning",
            "flexibility_design": "Design for flexibility",
            "alternative_options": "Maintain alternative options",
            "compliance_monitoring": "Monitor compliance changes",
            "innovation_program": "Establish innovation program",
        },
    }

    async def assess_risks(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess risks for the given solution context.

        Args:
            context: Solution context including requirements and constraints

        Returns:
            Dictionary with risk assessment results and mitigation strategies
        """
        try:
            solution_description = context.get("solution_description", "")
            solution_type = context.get("solution_type", "")
            business_domain = context.get("business_domain", "")
            constraints = context.get("constraints", [])
            compliance_requirements = context.get("compliance_requirements", [])
            organization_size = context.get("organization_size", "midmarket")
            budget_range = context.get("budget_range", {})
            timeline_months = context.get("timeline_months", 12)
            user_count = context.get("user_count", 100)
            is_critical = context.get("is_critical", False)

            # Identify risks
            identified_risks = self._identify_risks(context)

            # Calculate risk scores
            risk_scores = self._calculate_risk_scores(identified_risks, context)

            # Generate mitigation strategies
            mitigation_strategies = self._generate_mitigation_strategies(identified_risks, context)

            # Create risk matrix
            risk_matrix = self._create_risk_matrix(identified_risks, risk_scores)

            # Calculate overall risk profile
            overall_risk_profile = self._calculate_overall_risk_profile(risk_scores)

            # Generate risk dashboard
            risk_dashboard = self._create_risk_dashboard(identified_risks, risk_scores, context)

            # Risk monitoring recommendations
            monitoring_recommendations = self._generate_monitoring_recommendations(
                identified_risks, context
            )

            result = {
                "success": True,
                "risks_identified": len(identified_risks),
                "risks": identified_risks,
                "risk_scores": risk_scores,
                "mitigation_strategies": mitigation_strategies,
                "risk_matrix": risk_matrix,
                "overall_risk_profile": overall_risk_profile,
                "risk_dashboard": risk_dashboard,
                "monitoring_recommendations": monitoring_recommendations,
                "key_risk_factors": self._identify_key_risk_factors(context),
                "risk_tolerance": self._determine_risk_tolerance(context),
            }

            logger.info(f"Risk assessment completed: {len(identified_risks)} risks identified")
            return result

        except Exception as e:
            logger.error(f"Error in risk assessment: {e}")
            return {
                "success": False,
                "error": str(e),
                "risks_identified": 0,
            }

    def _identify_risks(self, context: Dict) -> List[Dict]:
        """Identify specific risks based on context."""
        risks = []
        description = context.get("solution_description", "").lower()
        solution_type = context.get("solution_type", "").lower()
        constraints = [c.lower() for c in context.get("constraints", [])]
        compliance_requirements = context.get("compliance_requirements", [])
        user_count = context.get("user_count", 0)
        timeline_months = context.get("timeline_months", 12)
        is_critical = context.get("is_critical", False)

        # Technical risks
        if "complex" in description or "integration" in description:
            risks.append(
                {
                    "category": "technical",
                    "type": "complexity",
                    "description": "Solution complexity may exceed team capabilities",
                    "probability": 0.7,
                    "impact": 0.8,
                    "factors": ["complex description", "integration requirements"],
                }
            )

        if "performance" in description or user_count > 1000:
            risks.append(
                {
                    "category": "technical",
                    "type": "performance",
                    "description": "Performance requirements may not be met",
                    "probability": 0.6,
                    "impact": 0.9,
                    "factors": ["performance requirements", "large user base"],
                }
            )

        if "security" in description or compliance_requirements:
            risks.append(
                {
                    "category": "technical",
                    "type": "security",
                    "description": "Security vulnerabilities may be introduced",
                    "probability": 0.5,
                    "impact": 0.9,
                    "factors": ["security requirements", "compliance needs"],
                }
            )

        # Business risks
        if timeline_months < 6:
            risks.append(
                {
                    "category": "business",
                    "type": "timeline_delay",
                    "description": "Project may miss critical deadlines",
                    "probability": 0.8,
                    "impact": 0.8,
                    "factors": ["tight timeline"],
                }
            )

        if is_critical:
            risks.append(
                {
                    "category": "business",
                    "type": "business_disruption",
                    "description": "Implementation may disrupt business operations",
                    "probability": 0.6,
                    "impact": 0.9,
                    "factors": ["business criticality"],
                }
            )

        # Operational risks
        if "new" in description or "novel" in description:
            risks.append(
                {
                    "category": "operational",
                    "type": "training",
                    "description": "Staff may lack required skills",
                    "probability": 0.7,
                    "impact": 0.6,
                    "factors": ["novel solution approach"],
                }
            )

        # Strategic risks
        if "proprietary" in description or "custom" in description:
            risks.append(
                {
                    "category": "strategic",
                    "type": "vendor_lockin",
                    "description": "Vendor lock-in may limit future options",
                    "probability": 0.5,
                    "impact": 0.7,
                    "factors": ["proprietary/custom solution"],
                }
            )

        # Add some default risks for completeness
        if len(risks) < 3:
            risks.extend(
                [
                    {
                        "category": "technical",
                        "type": "integration",
                        "description": "Integration with existing systems may fail",
                        "probability": 0.4,
                        "impact": 0.7,
                        "factors": ["standard integration risk"],
                    },
                    {
                        "category": "business",
                        "type": "requirements_change",
                        "description": "Requirements may change during development",
                        "probability": 0.6,
                        "impact": 0.6,
                        "factors": ["standard requirements volatility"],
                    },
                ]
            )

        return risks

    def _calculate_risk_scores(self, risks: List[Dict], context: Dict) -> Dict[str, Any]:
        """Calculate risk scores for each identified risk."""
        risk_scores = {}

        for risk in risks:
            # Base risk score is probability * impact
            base_score = risk["probability"] * risk["impact"]

            # Adjust based on context factors
            context_multiplier = 1.0

            # Critical systems increase risk scores
            if context.get("is_critical", False):
                context_multiplier *= 1.2

            # Tight timelines increase risk scores
            if context.get("timeline_months", 12) < 6:
                context_multiplier *= 1.1

            # Large user base increases technical risk scores
            if context.get("user_count", 0) > 1000 and risk["category"] == "technical":
                context_multiplier *= 1.1

            # Compliance requirements increase all risk scores
            if context.get("compliance_requirements"):
                context_multiplier *= 1.05

            # Organization size affects risk scores
            org_size = context.get("organization_size", "midmarket")
            if org_size == "smb" and risk["category"] == "technical":
                context_multiplier *= 1.1  # SMBs have less technical capacity
            elif org_size == "enterprise" and risk["category"] == "business":
                context_multiplier *= 1.05  # Enterprises have more business complexity

            final_score = min(base_score * context_multiplier, 1.0)

            # Determine risk level
            risk_level = "low"
            for level, config in self.RISK_LEVELS.items():
                if final_score >= config["threshold"]:
                    risk_level = level
                    break

            risk_scores[risk["type"]] = {
                "score": round(final_score, 3),
                "level": risk_level,
                "color": self.RISK_LEVELS[risk_level]["color"],
                "action": self.RISK_LEVELS[risk_level]["action"],
                "category": risk["category"],
                "probability": risk["probability"],
                "impact": risk["impact"],
            }

        return risk_scores

    def _generate_mitigation_strategies(
        self, risks: List[Dict], context: Dict
    ) -> Dict[str, List[Dict]]:
        """Generate mitigation strategies for identified risks."""
        mitigation_strategies = {}

        for risk in risks:
            risk_type = risk["type"]
            risk_category = risk["category"]

            # Get available strategies for this category
            strategies = self.MITIGATION_STRATEGIES.get(risk_category, {})

            # Select most relevant strategies
            relevant_strategies = []

            if risk_type == "complexity":
                relevant_strategies.extend(
                    [
                        {
                            "strategy": "proof_of_concept",
                            "description": "Build proof of concept to validate technical approach",
                        },
                        {
                            "strategy": "incremental_development",
                            "description": "Develop incrementally to reduce complexity",
                        },
                        {
                            "strategy": "expert_consultation",
                            "description": "Consult technical experts for complex areas",
                        },
                    ]
                )

            elif risk_type == "performance":
                relevant_strategies.extend(
                    [
                        {
                            "strategy": "performance_testing",
                            "description": "Conduct performance testing early and often",
                        },
                        {
                            "strategy": "pilot_testing",
                            "description": "Run pilot tests before full deployment",
                        },
                        {
                            "strategy": "automated_testing",
                            "description": "Use automated testing to catch issues early",
                        },
                    ]
                )

            elif risk_type == "security":
                relevant_strategies.extend(
                    [
                        {
                            "strategy": "security_audit",
                            "description": "Perform regular security audits",
                        },
                        {
                            "strategy": "automated_testing",
                            "description": "Use automated testing to catch issues early",
                        },
                        {
                            "strategy": "expert_consultation",
                            "description": "Consult technical experts for complex areas",
                        },
                    ]
                )

            elif risk_type == "timeline_delay":
                relevant_strategies.extend(
                    [
                        {
                            "strategy": "stakeholder_engagement",
                            "description": "Engage stakeholders regularly",
                        },
                        {
                            "strategy": "phased_rollout",
                            "description": "Roll out solution in phases",
                        },
                        {
                            "strategy": "regular_reporting",
                            "description": "Provide regular progress reports",
                        },
                    ]
                )

            elif risk_type == "business_disruption":
                relevant_strategies.extend(
                    [
                        {
                            "strategy": "phased_rollout",
                            "description": "Roll out solution in phases",
                        },
                        {
                            "strategy": "contingency_planning",
                            "description": "Create contingency plans for key risks",
                        },
                        {
                            "strategy": "change_management",
                            "description": "Implement proper change management",
                        },
                    ]
                )

            elif risk_type == "training":
                relevant_strategies.extend(
                    [
                        {
                            "strategy": "training_program",
                            "description": "Develop comprehensive training program",
                        },
                        {
                            "strategy": "knowledge_transfer",
                            "description": "Plan knowledge transfer processes",
                        },
                        {
                            "strategy": "documentation",
                            "description": "Create comprehensive documentation",
                        },
                    ]
                )

            elif risk_type == "vendor_lockin":
                relevant_strategies.extend(
                    [
                        {"strategy": "flexibility_design", "description": "Design for flexibility"},
                        {
                            "strategy": "alternative_options",
                            "description": "Maintain alternative options",
                        },
                        {
                            "strategy": "vendor_management",
                            "description": "Manage vendor relationships",
                        },
                    ]
                )

            # Add default strategies if none found
            if not relevant_strategies:
                default_strategies = list(strategies.items())[:3]
                relevant_strategies = [
                    {"strategy": key, "description": f"Use {key} to mitigate risk"}
                    for key, _ in default_strategies
                ]

            mitigation_strategies[risk_type] = relevant_strategies[:3]  # Top 3 strategies

        return mitigation_strategies

    def _create_risk_matrix(self, risks: List[Dict], risk_scores: Dict) -> Dict[str, Any]:
        """Create a risk matrix for visualization."""
        matrix = {
            "categories": {},
            "levels": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "heatmap": [],
        }

        # Count risks by category and level
        for risk in risks:
            category = risk["category"]
            risk_type = risk["type"]
            score_info = risk_scores.get(risk_type, {})

            if category not in matrix["categories"]:
                matrix["categories"][category] = {
                    "count": 0,
                    "risks": [],
                    "average_score": 0.0,
                }

            matrix["categories"][category]["count"] += 1
            matrix["categories"][category]["risks"].append(
                {
                    "type": risk_type,
                    "description": risk["description"],
                    "score": score_info.get("score", 0),
                    "level": score_info.get("level", "low"),
                }
            )

            # Count by level
            level = score_info.get("level", "low")
            matrix["levels"][level] += 1

        # Calculate average scores by category
        for category, info in matrix["categories"].items():
            scores = [risk["score"] for risk in info["risks"]]
            info["average_score"] = round(sum(scores) / len(scores), 3) if scores else 0.0

        # Create heatmap data
        for category, info in matrix["categories"].items():
            for risk in info["risks"]:
                matrix["heatmap"].append(
                    {
                        "category": category,
                        "type": risk["type"],
                        "score": risk["score"],
                        "level": risk["level"],
                        "description": risk["description"],
                    }
                )

        return matrix

    def _calculate_overall_risk_profile(self, risk_scores: Dict) -> Dict[str, Any]:
        """Calculate overall risk profile."""
        if not risk_scores:
            return {
                "overall_score": 0.0,
                "overall_level": "low",
                "category_breakdown": {},
                "risk_distribution": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            }

        # Calculate overall score
        scores = [info["score"] for info in risk_scores.values()]
        overall_score = round(sum(scores) / len(scores), 3)

        # Determine overall level
        overall_level = "low"
        for level, config in self.RISK_LEVELS.items():
            if overall_score >= config["threshold"]:
                overall_level = level
                break

        # Category breakdown
        category_breakdown = {}
        for risk_type, info in risk_scores.items():
            category = info["category"]
            if category not in category_breakdown:
                category_breakdown[category] = {"count": 0, "total_score": 0.0}
            category_breakdown[category]["count"] += 1
            category_breakdown[category]["total_score"] += info["score"]

        for category, info in category_breakdown.items():
            info["average_score"] = round(info["total_score"] / info["count"], 3)

        # Risk distribution
        risk_distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for info in risk_scores.values():
            risk_distribution[info["level"]] += 1

        return {
            "overall_score": overall_score,
            "overall_level": overall_level,
            "category_breakdown": category_breakdown,
            "risk_distribution": risk_distribution,
        }

    def _create_risk_dashboard(
        self, risks: List[Dict], risk_scores: Dict, context: Dict
    ) -> Dict[str, Any]:
        """Create risk dashboard summary."""
        # Top risks
        top_risks = sorted(
            [(risk["type"], risk_scores.get(risk["type"], {}).get("score", 0)) for risk in risks],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        # Risk trends — no historical risk data table exists; show honest unavailable state
        risk_trends = {
            category: {"trend": "unknown", "change": None, "data_available": False}
            for category in ["technical", "business", "operational", "strategic"]
        }

        # Risk alerts
        alerts = []
        for risk_type, score in top_risks:
            if score > 0.7:
                alerts.append(
                    {
                        "type": risk_type,
                        "message": f"High risk detected: {risk_type}",
                        "severity": "high" if score > 0.8 else "medium",
                    }
                )

        return {
            "top_risks": [{"type": risk_type, "score": score} for risk_type, score in top_risks],
            "risk_trends": risk_trends,
            "alerts": alerts,
            "summary": {
                "total_risks": len(risks),
                "high_risks": len([r for r in risk_scores.values() if r["score"] > 0.7]),
                "mitigation_needed": len([r for r in risk_scores.values() if r["score"] > 0.5]),
            },
        }

    def _generate_monitoring_recommendations(self, risks: List[Dict], context: Dict) -> List[Dict]:
        """Generate recommendations for risk monitoring."""
        recommendations = []

        # High-risk monitoring
        high_risk_types = [
            risk["type"] for risk in risks if risk["probability"] * risk["impact"] > 0.6
        ]
        if high_risk_types:
            recommendations.append(
                {
                    "type": "monitoring",
                    "priority": "high",
                    "title": "Monitor high-risk areas",
                    "description": f"Close monitoring needed for: {', '.join(high_risk_types[:3])}",
                    "frequency": "weekly",
                }
            )

        # Critical system monitoring
        if context.get("is_critical", False):
            recommendations.append(
                {
                    "type": "monitoring",
                    "priority": "high",
                    "title": "Critical system monitoring",
                    "description": "Enhanced monitoring for critical business system",
                    "frequency": "daily",
                }
            )

        # Timeline monitoring
        if context.get("timeline_months", 12) < 6:
            recommendations.append(
                {
                    "type": "monitoring",
                    "priority": "medium",
                    "title": "Timeline monitoring",
                    "description": "Track progress against tight timeline",
                    "frequency": "daily",
                }
            )

        # Compliance monitoring
        if context.get("compliance_requirements"):
            recommendations.append(
                {
                    "type": "monitoring",
                    "priority": "medium",
                    "title": "Compliance monitoring",
                    "description": "Monitor compliance with regulatory requirements",
                    "frequency": "monthly",
                }
            )

        return recommendations

    def _identify_key_risk_factors(self, context: Dict) -> List[Dict]:
        """Identify key factors that influence risk levels."""
        factors = []

        # Timeline factor
        timeline = context.get("timeline_months", 12)
        if timeline < 6:
            factors.append(
                {
                    "factor": "tight_timeline",
                    "impact": "high",
                    "description": f"Tight {timeline}-month timeline increases implementation risk",
                }
            )

        # Criticality factor
        if context.get("is_critical", False):
            factors.append(
                {
                    "factor": "business_criticality",
                    "impact": "high",
                    "description": "Business critical system increases impact of failures",
                }
            )

        # Complexity factor
        description = context.get("solution_description", "").lower()
        if any(word in description for word in ["complex", "integration", "distributed"]):
            factors.append(
                {
                    "factor": "solution_complexity",
                    "impact": "medium",
                    "description": "Solution complexity increases technical risk",
                }
            )

        # Compliance factor
        if context.get("compliance_requirements"):
            factors.append(
                {
                    "factor": "compliance_requirements",
                    "impact": "medium",
                    "description": "Compliance requirements add complexity and risk",
                }
            )

        return factors

    def _determine_risk_tolerance(self, context: Dict) -> Dict[str, Any]:
        """Determine risk tolerance based on context."""
        tolerance_level = "medium"  # Default

        # Adjust based on organization size
        org_size = context.get("organization_size", "midmarket")
        if org_size == "enterprise":
            tolerance_level = "low"  # Enterprises are more risk-averse
        elif org_size == "smb":
            tolerance_level = "high"  # SMBs are more risk-tolerant

        # Adjust based on criticality
        if context.get("is_critical", False):
            tolerance_level = "low"  # Critical systems require low risk tolerance

        # Adjust based on timeline
        if context.get("timeline_months", 12) < 6:
            tolerance_level = "low"  # Tight timelines require low risk tolerance

        tolerance_thresholds = {
            "low": {"acceptable_score": 0.3, "action_threshold": 0.5},
            "medium": {"acceptable_score": 0.5, "action_threshold": 0.7},
            "high": {"acceptable_score": 0.7, "action_threshold": 0.8},
        }

        return {
            "tolerance_level": tolerance_level,
            "thresholds": tolerance_thresholds[tolerance_level],
            "rationale": f"Risk tolerance set to {tolerance_level} based on organization size, criticality, and timeline",
        }
