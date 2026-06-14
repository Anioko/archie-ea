"""
Trade-off Analysis Agent

Evaluates cost-benefit scenarios with architectural principles
and provides multi-criteria decision analysis.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TradeoffAnalysisAgent:
    """
    Agent for analyzing trade-offs in architectural decisions.

    Evaluates different options against multiple criteria including
    cost, complexity, performance, and architectural principles.
    """

    # Architectural principles for evaluation
    ARCHITECTURAL_PRINCIPLES = {
        "simplicity": {
            "weight": 0.2,
            "description": "Keep solutions simple and understandable",
            "indicators": ["complexity", "maintenance", "learning_curve"],
        },
        "performance": {
            "weight": 0.25,
            "description": "Ensure adequate performance for requirements",
            "indicators": ["response_time", "throughput", "scalability"],
        },
        "security": {
            "weight": 0.2,
            "description": "Protect systems and data appropriately",
            "indicators": ["authentication", "authorization", "encryption"],
        },
        "scalability": {
            "weight": 0.15,
            "description": "Design for growth and increased load",
            "indicators": ["horizontal_scaling", "vertical_scaling", "elasticity"],
        },
        "maintainability": {
            "weight": 0.1,
            "description": "Ensure code can be maintained and evolved",
            "indicators": ["modularity", "documentation", "testing"],
        },
        "reliability": {
            "weight": 0.1,
            "description": "Design for availability and fault tolerance",
            "indicators": ["availability", "fault_tolerance", "recovery"],
        },
    }

    # Common trade-off scenarios
    TRADEOFF_SCENARIOS = {
        "monolith_vs_microservices": {
            "options": ["monolithic", "microservices"],
            "criteria": [
                "simplicity",
                "performance",
                "scalability",
                "maintainability",
                "reliability",
            ],
        },
        "sql_vs_nosql": {
            "options": ["sql_database", "nosql_database"],
            "criteria": ["performance", "scalability", "maintainability", "reliability"],
        },
        "cloud_vs_onpremise": {
            "options": ["cloud_deployment", "onpremise_deployment"],
            "criteria": ["performance", "security", "scalability", "reliability"],
        },
        "sync_vs_async": {
            "options": ["synchronous", "asynchronous"],
            "criteria": ["simplicity", "performance", "reliability"],
        },
        "rest_vs_graphql": {
            "options": ["rest_api", "graphql_api"],
            "criteria": ["simplicity", "performance", "maintainability"],
        },
    }

    async def analyze_tradeoffs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze trade-offs for the given solution context.

        Args:
            context: Solution context including constraints and requirements

        Returns:
            Dictionary with trade-off analysis results and recommendations
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

            # Identify relevant trade-off scenarios
            relevant_scenarios = self._identify_relevant_scenarios(context)

            # Analyze each scenario
            scenario_analyses = []
            for scenario_name, scenario_info in relevant_scenarios.items():
                analysis = await self._analyze_scenario(scenario_name, scenario_info, context)
                scenario_analyses.append(analysis)

            # Generate overall trade-off matrix
            tradeoff_matrix = self._generate_tradeoff_matrix(scenario_analyses)

            # Calculate overall scores
            overall_scores = self._calculate_overall_scores(scenario_analyses)

            # Generate recommendations
            recommendations = self._generate_tradeoff_recommendations(
                scenario_analyses, overall_scores, context
            )

            # Risk/benefit analysis
            risk_benefit_analysis = self._analyze_risks_benefits(scenario_analyses, context)

            result = {
                "success": True,
                "scenarios_analyzed": len(scenario_analyses),
                "scenario_analyses": scenario_analyses,
                "tradeoff_matrix": tradeoff_matrix,
                "overall_scores": overall_scores,
                "recommendations": recommendations,
                "risk_benefit_analysis": risk_benefit_analysis,
                "key_insights": self._extract_key_insights(scenario_analyses, context),
                "decision_factors": self._identify_decision_factors(context),
            }

            logger.info(
                f"Trade-off analysis completed: {len(scenario_analyses)} scenarios analyzed"
            )
            return result

        except Exception as e:
            logger.error(f"Error in trade-off analysis: {e}")
            return {
                "success": False,
                "error": str(e),
                "scenarios_analyzed": 0,
            }

    def _identify_relevant_scenarios(self, context: Dict) -> Dict[str, Dict]:
        """Identify which trade-off scenarios are relevant for this context."""
        relevant = {}
        description = context.get("solution_description", "").lower()
        solution_type = context.get("solution_type", "").lower()
        constraints = [c.lower() for c in context.get("constraints", [])]

        # Check each scenario for relevance
        for scenario_name, scenario_info in self.TRADEOFF_SCENARIOS.items():
            relevance_score = 0

            # Check description keywords
            if scenario_name == "monolith_vs_microservices":
                if any(kw in description for kw in ["service", "api", "distributed", "scale"]):
                    relevance_score += 2
                if solution_type in ["platform", "integration"]:
                    relevance_score += 1

            elif scenario_name == "sql_vs_nosql":
                if any(kw in description for kw in ["database", "data", "storage", "query"]):
                    relevance_score += 2
                if any(kw in description for kw in ["unstructured", "big data", "document"]):
                    relevance_score += 1

            elif scenario_name == "cloud_vs_onpremise":
                if any(kw in description for kw in ["cloud", "hosting", "infrastructure"]):
                    relevance_score += 2
                if "cloud" in constraints or "on-premise" in constraints:
                    relevance_score += 1

            elif scenario_name == "sync_vs_async":
                if any(kw in description for kw in ["real-time", "immediate", "instant"]):
                    relevance_score += 2
                if any(kw in description for kw in ["queue", "message", "event"]):
                    relevance_score += 1

            elif scenario_name == "rest_vs_graphql":
                if any(kw in description for kw in ["api", "interface", "integration"]):
                    relevance_score += 2
                if any(kw in description for kw in ["flexible", "query", "data"]):
                    relevance_score += 1

            # Include if relevant enough
            if relevance_score >= 2:
                relevant[scenario_name] = scenario_info

        return relevant

    async def _analyze_scenario(
        self, scenario_name: str, scenario_info: Dict, context: Dict
    ) -> Dict[str, Any]:
        """Analyze a specific trade-off scenario."""
        options = scenario_info["options"]
        criteria = scenario_info["criteria"]

        # Score each option against each criterion
        option_scores = {}
        for option in options:
            scores = {}
            for criterion in criteria:
                if criterion in self.ARCHITECTURAL_PRINCIPLES:
                    scores[criterion] = self._score_option_against_criterion(
                        option, criterion, context
                    )
                else:
                    scores[criterion] = self._score_custom_criterion(option, criterion, context)
            option_scores[option] = scores

        # Calculate weighted scores
        weighted_scores = {}
        for option, scores in option_scores.items():
            total_score = 0
            total_weight = 0
            for criterion, score in scores.items():
                weight = self.ARCHITECTURAL_PRINCIPLES.get(criterion, {}).get("weight", 0.1)
                total_score += score * weight
                total_weight += weight
            weighted_scores[option] = total_score / total_weight if total_weight > 0 else 0

        # Generate recommendation
        best_option = max(weighted_scores, key=weighted_scores.get)
        confidence = (
            max(weighted_scores.values()) - min(weighted_scores.values())
            if len(weighted_scores) > 1
            else 0
        )

        return {
            "scenario": scenario_name,
            "options": options,
            "criteria": criteria,
            "option_scores": option_scores,
            "weighted_scores": weighted_scores,
            "recommendation": best_option,
            "confidence": round(confidence, 3),
            "rationale": self._generate_scenario_rationale(best_option, weighted_scores, context),
        }

    def _score_option_against_criterion(self, option: str, criterion: str, context: Dict) -> float:
        """Score an option against a specific architectural principle."""
        # Base scores for different option/criterion combinations
        base_scores = {
            ("monolithic", "simplicity"): 0.8,
            ("monolithic", "performance"): 0.6,
            ("monolithic", "scalability"): 0.3,
            ("monolithic", "maintainability"): 0.4,
            ("monolithic", "reliability"): 0.7,
            ("microservices", "simplicity"): 0.4,
            ("microservices", "performance"): 0.7,
            ("microservices", "scalability"): 0.9,
            ("microservices", "maintainability"): 0.6,
            ("microservices", "reliability"): 0.6,
            ("sql_database", "simplicity"): 0.7,
            ("sql_database", "performance"): 0.6,
            ("sql_database", "scalability"): 0.5,
            ("sql_database", "maintainability"): 0.7,
            ("sql_database", "reliability"): 0.8,
            ("nosql_database", "simplicity"): 0.5,
            ("nosql_database", "performance"): 0.8,
            ("nosql_database", "scalability"): 0.9,
            ("nosql_database", "maintainability"): 0.6,
            ("nosql_database", "reliability"): 0.6,
            ("cloud_deployment", "simplicity"): 0.6,
            ("cloud_deployment", "performance"): 0.7,
            ("cloud_deployment", "scalability"): 0.9,
            ("cloud_deployment", "maintainability"): 0.6,
            ("cloud_deployment", "reliability"): 0.7,
            ("onpremise_deployment", "simplicity"): 0.5,
            ("onpremise_deployment", "performance"): 0.7,
            ("onpremise_deployment", "scalability"): 0.4,
            ("onpremise_deployment", "maintainability"): 0.5,
            ("onpremise_deployment", "reliability"): 0.8,
            ("synchronous", "simplicity"): 0.8,
            ("synchronous", "performance"): 0.5,
            ("synchronous", "reliability"): 0.7,
            ("asynchronous", "simplicity"): 0.4,
            ("asynchronous", "performance"): 0.8,
            ("asynchronous", "reliability"): 0.6,
            ("rest_api", "simplicity"): 0.8,
            ("rest_api", "performance"): 0.7,
            ("rest_api", "maintainability"): 0.7,
            ("graphql_api", "simplicity"): 0.5,
            ("graphql_api", "performance"): 0.6,
            ("graphql_api", "maintainability"): 0.6,
        }

        base_score = base_scores.get((option, criterion), 0.5)

        # Adjust based on context
        if criterion == "scalability" and context.get("user_count", 0) > 1000:
            if option in ["microservices", "nosql_database", "cloud_deployment"]:
                base_score += 0.2
            elif option in ["monolithic", "sql_database", "onpremise_deployment"]:
                base_score -= 0.2

        if criterion == "security" and context.get("compliance_requirements"):
            if option in ["onpremise_deployment", "sql_database"]:
                base_score += 0.1
            elif option in ["cloud_deployment", "nosql_database"]:
                base_score -= 0.1

        if criterion == "simplicity" and context.get("organization_size") == "smb":
            if option in ["monolithic", "sql_database", "rest_api"]:
                base_score += 0.2
            elif option in ["microservices", "nosql_database", "graphql_api"]:
                base_score -= 0.2

        return max(0.0, min(1.0, base_score))

    def _score_custom_criterion(self, option: str, criterion: str, context: Dict) -> float:
        """Score against custom criteria not in standard principles."""
        # Default to neutral score for custom criteria
        return 0.5

    def _generate_scenario_rationale(
        self, best_option: str, weighted_scores: Dict, context: Dict
    ) -> str:
        """Generate rationale for scenario recommendation."""
        rationale_parts = []

        best_score = weighted_scores.get(best_option, 0)
        other_scores = [s for o, s in weighted_scores.items() if o != best_option]
        margin = best_score - max(other_scores) if other_scores else 0

        # Score-based rationale
        if best_score > 0.7:
            rationale_parts.append(f"{best_option} scores highly ({best_score:.1%})")
        elif best_score > 0.5:
            rationale_parts.append(f"{best_option} shows good fit ({best_score:.1%})")
        else:
            rationale_parts.append(f"{best_option} is the best available option ({best_score:.1%})")

        # Margin-based rationale
        if margin > 0.3:
            rationale_parts.append("with clear advantage over alternatives")
        elif margin > 0.1:
            rationale_parts.append("with moderate advantage over alternatives")
        else:
            rationale_parts.append("but alternatives are close in scoring")

        # Context-based rationale
        if context.get("user_count", 0) > 1000 and "microservices" in best_option.lower():
            rationale_parts.append("supporting high user scalability requirements")
        elif context.get("organization_size") == "smb" and "monolithic" in best_option.lower():
            rationale_parts.append("matching SMB operational simplicity needs")
        elif context.get("is_critical") and "sql" in best_option.lower():
            rationale_parts.append("providing reliability for critical workloads")

        return ". ".join(rationale_parts) + "."

    def _generate_tradeoff_matrix(self, scenario_analyses: List[Dict]) -> Dict[str, Any]:
        """Generate a comprehensive trade-off matrix."""
        matrix = {
            "scenarios": [],
            "criteria_summary": {},
            "option_summary": {},
        }

        for analysis in scenario_analyses:
            scenario_name = analysis["scenario"]
            matrix["scenarios"].append(
                {
                    "name": scenario_name,
                    "recommendation": analysis["recommendation"],
                    "confidence": analysis["confidence"],
                    "options": analysis["options"],
                }
            )

        # Summarize criteria performance
        criteria_performance = {}
        for analysis in scenario_analyses:
            for option, scores in analysis["option_scores"].items():
                for criterion, score in scores.items():
                    if criterion not in criteria_performance:
                        criteria_performance[criterion] = []
                    criteria_performance[criterion].append(score)

        for criterion, scores in criteria_performance.items():
            matrix["criteria_summary"][criterion] = {
                "average": round(sum(scores) / len(scores), 3),
                "min": round(min(scores), 3),
                "max": round(max(scores), 3),
                "range": round(max(scores) - min(scores), 3),
            }

        return matrix

    def _calculate_overall_scores(self, scenario_analyses: List[Dict]) -> Dict[str, float]:
        """Calculate overall scores for each option across all scenarios."""
        option_scores = {}

        for analysis in scenario_analyses:
            for option, score in analysis["weighted_scores"].items():
                if option not in option_scores:
                    option_scores[option] = []
                option_scores[option].append(score)

        overall_scores = {}
        for option, scores in option_scores.items():
            overall_scores[option] = round(sum(scores) / len(scores), 3)

        return overall_scores

    def _generate_tradeoff_recommendations(
        self, scenario_analyses: List[Dict], overall_scores: Dict, context: Dict
    ) -> List[Dict]:
        """Generate actionable trade-off recommendations."""
        recommendations = []

        # Top recommendation based on overall scores
        if overall_scores:
            best_option = max(overall_scores, key=overall_scores.get)
            recommendations.append(
                {
                    "type": "primary_recommendation",
                    "option": best_option,
                    "score": overall_scores[best_option],
                    "rationale": f"Highest overall score across all trade-off analyses",
                    "confidence": "high",
                }
            )

        # Scenario-specific recommendations
        for analysis in scenario_analyses:
            if analysis["confidence"] > 0.3:  # Only include confident recommendations
                recommendations.append(
                    {
                        "type": "scenario_recommendation",
                        "scenario": analysis["scenario"],
                        "option": analysis["recommendation"],
                        "score": analysis["weighted_scores"][analysis["recommendation"]],
                        "rationale": analysis["rationale"],
                        "confidence": "medium" if analysis["confidence"] > 0.5 else "low",
                    }
                )

        # Context-aware recommendations
        if context.get("user_count", 0) > 1000:
            recommendations.append(
                {
                    "type": "context_recommendation",
                    "option": "microservices",
                    "rationale": "High user count suggests need for scalable architecture",
                    "confidence": "medium",
                }
            )

        if context.get("compliance_requirements"):
            recommendations.append(
                {
                    "type": "context_recommendation",
                    "option": "sql_database",
                    "rationale": "Compliance requirements benefit from structured data and ACID properties",
                    "confidence": "medium",
                }
            )

        return recommendations[:5]  # Limit to top 5 recommendations

    def _analyze_risks_benefits(
        self, scenario_analyses: List[Dict], context: Dict
    ) -> Dict[str, Any]:
        """Analyze risks and benefits for each option."""
        risks_benefits = {}

        # Collect all unique options
        all_options = set()
        for analysis in scenario_analyses:
            all_options.update(analysis["options"])

        for option in all_options:
            risks = []
            benefits = []

            # Analyze based on option characteristics
            if option == "monolithic":
                risks.extend(
                    ["Limited scalability", "Single point of failure", "Deployment complexity"]
                )
                benefits.extend(
                    ["Simpler development", "Easier debugging", "Lower operational overhead"]
                )
            elif option == "microservices":
                risks.extend(
                    ["Operational complexity", "Network latency", "Data consistency challenges"]
                )
                benefits.extend(["Independent scaling", "Technology diversity", "Fault isolation"])
            elif option == "sql_database":
                risks.extend(["Scaling limitations", "Schema rigidity"])
                benefits.extend(["ACID compliance", "Strong consistency", "Mature tooling"])
            elif option == "nosql_database":
                risks.extend(["Eventual consistency", "Limited query capabilities"])
                benefits.extend(["Horizontal scaling", "Flexible schema", "High performance"])
            elif option == "cloud_deployment":
                risks.extend(["Vendor lock-in", "Data privacy concerns"])
                benefits.extend(["Elastic scaling", "Managed services", "Pay-as-you-go"])
            elif option == "onpremise_deployment":
                risks.extend(["Capital expenditure", "Limited elasticity"])
                benefits.extend(["Full control", "Data sovereignty", "Compliance advantages"])

            risks_benefits[option] = {
                "risks": risks,
                "benefits": benefits,
                "risk_score": min(len(risks) * 0.2, 1.0),
                "benefit_score": min(len(benefits) * 0.2, 1.0),
            }

        return risks_benefits

    def _extract_key_insights(self, scenario_analyses: List[Dict], context: Dict) -> List[str]:
        """Extract key insights from the trade-off analysis."""
        insights = []

        # High confidence insights
        high_confidence_scenarios = [a for a in scenario_analyses if a["confidence"] > 0.5]
        if high_confidence_scenarios:
            insights.append(
                f"{len(high_confidence_scenarios)} scenarios show clear trade-off patterns"
            )

        # Context insights
        if context.get("user_count", 0) > 1000:
            insights.append("Large user count favors scalable solutions")

        if context.get("compliance_requirements"):
            insights.append("Compliance requirements influence technology choices")

        if context.get("organization_size") == "smb":
            insights.append("SMB organization favors simpler solutions")

        # Option insights
        all_options = set()
        for analysis in scenario_analyses:
            all_options.update(analysis["options"])

        if len(all_options) > 5:
            insights.append("Multiple architectural options available for consideration")

        return insights[:5]

    def _identify_decision_factors(self, context: Dict) -> List[Dict]:
        """Identify key factors that should influence the decision."""
        factors = []

        # User count factor
        user_count = context.get("user_count", 0)
        if user_count > 0:
            factors.append(
                {
                    "factor": "user_count",
                    "value": user_count,
                    "impact": "high" if user_count > 1000 else "medium",
                    "description": f"{'Large' if user_count > 1000 else 'Medium' if user_count > 100 else 'Small'} user base affects scalability requirements",
                }
            )

        # Budget factor
        budget_range = context.get("budget_range", {})
        if budget_range.get("max", 0) > 0:
            factors.append(
                {
                    "factor": "budget",
                    "value": f"${budget_range.get('min', 0):,} - ${budget_range.get('max', 0):,}",
                    "impact": "high" if budget_range.get("max", 0) > 100000 else "medium",
                    "description": f"{'Large' if budget_range.get('max', 0) > 100000 else 'Medium' if budget_range.get('max', 0) > 10000 else 'Small'} budget affects technology options",
                }
            )

        # Timeline factor
        timeline = context.get("timeline_months", 0)
        if timeline > 0:
            factors.append(
                {
                    "factor": "timeline",
                    "value": f"{timeline} months",
                    "impact": "high" if timeline < 6 else "medium",
                    "description": f"{'Tight' if timeline < 6 else 'Moderate' if timeline < 12 else 'Flexible'} timeline affects complexity choices",
                }
            )

        # Criticality factor
        is_critical = context.get("is_critical", False)
        factors.append(
            {
                "factor": "criticality",
                "value": "Critical" if is_critical else "Standard",
                "impact": "high" if is_critical else "medium",
                "description": "Critical systems require higher reliability and security",
            }
        )

        return factors
