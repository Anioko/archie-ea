"""
Quality Optimization Agent

Optimizes for performance, security, scalability with
non-functional requirements analysis and quality attribute scoring.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QualityOptimizationAgent:
    """
    Agent for optimizing quality attributes in solution architecture.

    Analyzes and optimizes performance, security, scalability,
    and other non-functional requirements.
    """

    # Quality attributes and their characteristics
    QUALITY_ATTRIBUTES = {
        "performance": {
            "description": "System performance and responsiveness",
            "weight": 0.25,
            "metrics": ["response_time", "throughput", "latency", "resource_utilization"],
            "optimization_areas": [
                "caching_strategies",
                "database_optimization",
                "code_optimization",
                "load_balancing",
                "cdn_usage",
            ],
        },
        "security": {
            "description": "Security controls and protections",
            "weight": 0.25,
            "metrics": [
                "vulnerability_count",
                "security_score",
                "compliance_status",
                "incident_rate",
            ],
            "optimization_areas": [
                "authentication_mechanisms",
                "encryption_standards",
                "access_control",
                "security_monitoring",
                "vulnerability_scanning",
            ],
        },
        "scalability": {
            "description": "Ability to handle growth and load",
            "weight": 0.2,
            "metrics": [
                "user_capacity",
                "transaction_volume",
                "horizontal_scaling",
                "vertical_scaling",
            ],
            "optimization_areas": [
                "horizontal_scaling",
                "vertical_scaling",
                "load_distribution",
                "resource_provisioning",
                "auto_scaling",
            ],
        },
        "reliability": {
            "description": "System reliability and availability",
            "weight": 0.15,
            "metrics": ["uptime", "mttr", "mtbf", "error_rate"],
            "optimization_areas": [
                "redundancy_mechanisms",
                "failover_strategies",
                "backup_recovery",
                "health_checks",
                "monitoring_alerts",
            ],
        },
        "maintainability": {
            "description": "Ease of maintenance and evolution",
            "weight": 0.1,
            "metrics": ["code_quality", "documentation", "modularity", "test_coverage"],
            "optimization_areas": [
                "code_structure",
                "documentation",
                "testing_strategy",
                "modular_design",
                "standards_compliance",
            ],
        },
        "usability": {
            "description": "User experience and interface quality",
            "weight": 0.05,
            "metrics": ["user_satisfaction", "task_completion", "error_rate", "learnability"],
            "optimization_areas": [
                "ui_design",
                "user_experience",
                "accessibility",
                "responsive_design",
                "user_feedback",
            ],
        },
    }

    # Optimization strategies
    OPTIMIZATION_STRATEGIES = {
        "caching": {
            "description": "Implement caching to improve performance",
            "applicable_to": ["performance"],
            "techniques": ["redis_cache", "cdn_cache", "application_cache", "database_cache"],
            "impact": "high",
            "complexity": "medium",
        },
        "database_optimization": {
            "description": "Optimize database queries and structure",
            "applicable_to": ["performance", "scalability"],
            "techniques": ["query_optimization", "indexing", "partitioning", "connection_pooling"],
            "impact": "high",
            "complexity": "high",
        },
        "load_balancing": {
            "description": "Distribute load across multiple instances",
            "applicable_to": ["performance", "scalability", "reliability"],
            "techniques": ["round_robin", "weighted", "least_connections", "health_based"],
            "impact": "high",
            "complexity": "medium",
        },
        "security_hardening": {
            "description": "Implement comprehensive security controls",
            "applicable_to": ["security"],
            "techniques": ["encryption", "authentication", "authorization", "monitoring"],
            "impact": "high",
            "complexity": "high",
        },
        "auto_scaling": {
            "description": "Automatically scale resources based on demand",
            "applicable_to": ["scalability", "cost_optimization"],
            "techniques": ["horizontal_scaling", "vertical_scaling", "predictive_scaling"],
            "impact": "high",
            "complexity": "high",
        },
        "monitoring_alerting": {
            "description": "Implement comprehensive monitoring and alerting",
            "applicable_to": ["reliability", "performance", "security"],
            "techniques": ["metrics_collection", "alerting", "dashboards", "anomaly_detection"],
            "impact": "medium",
            "complexity": "medium",
        },
        "code_quality": {
            "description": "Improve code quality and maintainability",
            "applicable_to": ["maintainability", "reliability"],
            "techniques": ["code_review", "static_analysis", "testing", "documentation"],
            "impact": "medium",
            "complexity": "low",
        },
        "cdn_optimization": {
            "description": "Use CDN for static content delivery",
            "applicable_to": ["performance", "scalability"],
            "techniques": ["static_cdn", "dynamic_cdn", "edge_caching", "image_optimization"],
            "impact": "medium",
            "complexity": "low",
        },
    }

    async def optimize_quality(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize quality attributes for the solution context.

        Args:
            context: Solution context including requirements and constraints

        Returns:
            Dictionary with optimization recommendations and quality scores
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

            # Analyze current quality state
            quality_analysis = self._analyze_quality_state(context)

            # Identify optimization opportunities
            optimization_opportunities = self._identify_optimization_opportunities(
                quality_analysis, context
            )

            # Generate optimization recommendations
            optimization_recommendations = self._generate_optimization_recommendations(
                optimization_opportunities, context
            )

            # Calculate quality scores
            quality_scores = self._calculate_quality_scores(
                quality_analysis, optimization_recommendations
            )

            # Create quality dashboard
            quality_dashboard = self._create_quality_dashboard(quality_scores, context)

            # Generate implementation roadmap
            implementation_roadmap = self._generate_implementation_roadmap(
                optimization_recommendations, context
            )

            # Quality metrics and KPIs
            quality_metrics = self._define_quality_metrics(context)

            result = {
                "success": True,
                "quality_analysis": quality_analysis,
                "optimization_opportunities": optimization_opportunities,
                "optimization_recommendations": optimization_recommendations,
                "quality_scores": quality_scores,
                "quality_dashboard": quality_dashboard,
                "implementation_roadmap": implementation_roadmap,
                "quality_metrics": quality_metrics,
                "key_insights": self._extract_quality_insights(quality_analysis, context),
                "quality_targets": self._define_quality_targets(context),
            }

            logger.info(
                f"Quality optimization completed: {len(optimization_recommendations)} recommendations generated"
            )
            return result

        except Exception as e:
            logger.error(f"Error in quality optimization: {e}")
            return {
                "success": False,
                "error": str(e),
                "optimization_recommendations": [],
            }

    def _analyze_quality_state(self, context: Dict) -> Dict[str, Any]:
        """Analyze current quality state based on context."""
        description = context.get("solution_description", "").lower()
        user_count = context.get("user_count", 0)
        is_critical = context.get("is_critical", False)
        compliance_requirements = context.get("compliance_requirements", [])

        quality_state = {}

        for attribute, attr_info in self.QUALITY_ATTRIBUTES.items():
            current_score = 0.5  # Default score
            factors = []

            # Adjust score based on context
            if attribute == "performance":
                if user_count > 1000:
                    current_score += 0.2
                    factors.append("large_user_base")
                if "performance" in description:
                    current_score += 0.1
                    factors.append("performance_requirements")
                if "slow" in description:
                    current_score -= 0.2
                    factors.append("performance_concerns")

            elif attribute == "security":
                if is_critical:
                    current_score += 0.2
                    factors.append("business_critical")
                if compliance_requirements:
                    current_score += 0.1
                    factors.append("compliance_requirements")
                if "security" in description:
                    current_score += 0.1
                    factors.append("security_focus")

            elif attribute == "scalability":
                if user_count > 5000:
                    current_score += 0.2
                    factors.append("large_scale")
                if "scale" in description or "growth" in description:
                    current_score += 0.1
                    factors.append("scalability_requirements")
                if "limited" in description:
                    current_score -= 0.2
                    factors.append("scalability_constraints")

            elif attribute == "reliability":
                if is_critical:
                    current_score += 0.3
                    factors.append("high_reliability_required")
                if "reliable" in description or "stable" in description:
                    current_score += 0.1
                    factors.append("reliability_focus")

            elif attribute == "maintainability":
                if "complex" in description:
                    current_score -= 0.1
                    factors.append("complexity_concerns")
                if "simple" in description or "maintainable" in description:
                    current_score += 0.1
                    factors.append("maintainability_focus")

            elif attribute == "usability":
                if "user" in description or "interface" in description:
                    current_score += 0.1
                    factors.append("user_interface_focus")
                if "complex" in description:
                    current_score -= 0.1
                    factors.append("complexity_impact")

            quality_state[attribute] = {
                "current_score": max(0.0, min(1.0, current_score)),
                "factors": factors,
                "weight": attr_info["weight"],
                "target_score": self._get_target_score(attribute, context),
                "gap": 0.0,  # Will be calculated later
            }

        return quality_state

    def _get_target_score(self, attribute: str, context: Dict) -> float:
        """Get target score for quality attribute based on context."""
        base_targets = {
            "performance": 0.8,
            "security": 0.9,
            "scalability": 0.7,
            "reliability": 0.8,
            "maintainability": 0.7,
            "usability": 0.8,
        }

        target = base_targets.get(attribute, 0.7)

        # Adjust targets based on context
        if attribute == "security" and context.get("compliance_requirements"):
            target = min(0.95, target + 0.1)

        if attribute == "reliability" and context.get("is_critical", False):
            target = min(0.95, target + 0.1)

        if attribute == "scalability" and context.get("user_count", 0) > 5000:
            target = min(0.9, target + 0.1)

        return target

    def _identify_optimization_opportunities(
        self, quality_analysis: Dict, context: Dict
    ) -> List[Dict]:
        """Identify optimization opportunities based on quality gaps."""
        opportunities = []

        for attribute, analysis in quality_analysis.items():
            current_score = analysis["current_score"]
            target_score = analysis["target_score"]
            gap = target_score - current_score

            if gap > 0.1:  # Only consider significant gaps
                # Find applicable strategies
                applicable_strategies = []
                for strategy_name, strategy_info in self.OPTIMIZATION_STRATEGIES.items():
                    if attribute in strategy_info["applicable_to"]:
                        applicable_strategies.append(
                            {
                                "name": strategy_name,
                                "description": strategy_info["description"],
                                "techniques": strategy_info["techniques"],
                                "impact": strategy_info["impact"],
                                "complexity": strategy_info["complexity"],
                                "potential_improvement": min(gap, 0.3),  # Cap improvement at 0.3
                            }
                        )

                opportunities.append(
                    {
                        "attribute": attribute,
                        "current_score": current_score,
                        "target_score": target_score,
                        "gap": gap,
                        "priority": "high" if gap > 0.3 else "medium" if gap > 0.2 else "low",
                        "applicable_strategies": applicable_strategies,
                        "factors": analysis["factors"],
                    }
                )

        # Sort by gap size
        opportunities.sort(key=lambda x: x["gap"], reverse=True)

        return opportunities

    def _generate_optimization_recommendations(
        self, opportunities: List[Dict], context: Dict
    ) -> List[Dict]:
        """Generate specific optimization recommendations."""
        recommendations = []

        for opportunity in opportunities[:10]:  # Top 10 opportunities
            attribute = opportunity["attribute"]
            gap = opportunity["gap"]
            strategies = opportunity["applicable_strategies"]

            # Select best strategies based on impact and complexity
            best_strategies = sorted(
                strategies,
                key=lambda s: (
                    s["impact"],
                    -1 if s["complexity"] == "low" else 0 if s["complexity"] == "medium" else -1,
                ),
                reverse=True,
            )[:3]

            for strategy in best_strategies:
                recommendations.append(
                    {
                        "attribute": attribute,
                        "strategy": strategy["name"],
                        "description": strategy["description"],
                        "techniques": strategy["techniques"],
                        "impact": strategy["impact"],
                        "complexity": strategy["complexity"],
                        "potential_improvement": strategy["potential_improvement"],
                        "current_score": opportunity["current_score"],
                        "target_score": opportunity["target_score"],
                        "gap": gap,
                        "priority": opportunity["priority"],
                        "rationale": self._generate_recommendation_rationale(
                            attribute, strategy, gap, context
                        ),
                        "implementation_effort": self._estimate_implementation_effort(strategy),
                    }
                )

        return recommendations

    def _generate_recommendation_rationale(
        self, attribute: str, strategy: Dict, gap: float, context: Dict
    ) -> str:
        """Generate rationale for optimization recommendation."""
        rationale_parts = []

        # Gap-based rationale
        if gap > 0.3:
            rationale_parts.append(f"Significant {attribute} gap ({gap:.1%}) requires attention")
        elif gap > 0.2:
            rationale_parts.append(f"Moderate {attribute} gap ({gap:.1%}) should be addressed")
        else:
            rationale_parts.append(f"Small {attribute} gap ({gap:.1%}) can be improved")

        # Strategy-based rationale
        if strategy["impact"] == "high":
            rationale_parts.append(f"High-impact {strategy['name']} strategy")
        elif strategy["complexity"] == "low":
            rationale_parts.append(f"Low-complexity implementation")

        # Context-based rationale
        if context.get("user_count", 0) > 1000 and attribute == "performance":
            rationale_parts.append("Large user base benefits from performance optimization")

        if context.get("is_critical", False) and attribute == "reliability":
            rationale_parts.append("Critical system requires high reliability")

        return "; ".join(rationale_parts)

    def _estimate_implementation_effort(self, strategy: Dict) -> Dict[str, Any]:
        """Estimate implementation effort for a strategy."""
        effort_mapping = {
            "low": {"time_weeks": 2, "complexity": "low", "resources": "1 - 2 developers"},
            "medium": {"time_weeks": 4, "complexity": "medium", "resources": "2 - 3 developers"},
            "high": {"time_weeks": 8, "complexity": "high", "resources": "3 - 5 developers"},
        }

        complexity = strategy.get("complexity", "medium")
        return effort_mapping.get(complexity, effort_mapping["medium"])

    def _calculate_quality_scores(
        self, quality_analysis: Dict, recommendations: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate quality scores after optimization."""
        optimized_scores = {}

        for attribute, analysis in quality_analysis.items():
            current_score = analysis["current_score"]
            target_score = analysis["target_score"]

            # Calculate potential improvement from recommendations
            potential_improvement = 0.0
            for rec in recommendations:
                if rec["attribute"] == attribute:
                    potential_improvement += rec["potential_improvement"]

            # Calculate optimized score
            optimized_score = min(1.0, current_score + potential_improvement)
            gap = target_score - optimized_score

            optimized_scores[attribute] = {
                "current_score": current_score,
                "optimized_score": optimized_score,
                "target_score": target_score,
                "improvement": optimized_score - current_score,
                "gap": max(0.0, gap),
                "achievement_rate": (optimized_score / target_score) if target_score > 0 else 0.0,
            }

        # Calculate overall scores
        overall_current = sum(
            analysis["current_score"] * analysis["weight"] for analysis in quality_analysis.values()
        )
        overall_optimized = sum(
            optimized_scores[attribute]["optimized_score"] * quality_analysis[attribute]["weight"]
            for attribute in optimized_scores
        )
        overall_target = sum(
            analysis["target_score"] * analysis["weight"] for analysis in quality_analysis.values()
        )

        optimized_scores["overall"] = {
            "current_score": overall_current,
            "optimized_score": overall_optimized,
            "target_score": overall_target,
            "improvement": overall_optimized - overall_current,
            "gap": max(0.0, overall_target - overall_optimized),
            "achievement_rate": (overall_optimized / overall_target) if overall_target > 0 else 0.0,
        }

        return optimized_scores

    def _create_quality_dashboard(self, quality_scores: Dict, context: Dict) -> Dict[str, Any]:
        """Create a quality dashboard visualization."""
        dashboard = {
            "overall_metrics": {
                "current_quality_score": quality_scores["overall"]["current_score"],
                "optimized_quality_score": quality_scores["overall"]["optimized_score"],
                "target_quality_score": quality_scores["overall"]["target_score"],
                "improvement_percentage": quality_scores["overall"]["improvement"] * 100,
                "achievement_rate": quality_scores["overall"]["achievement_rate"] * 100,
            },
            "attribute_scores": {},
            "improvement_areas": [],
            "quality_trends": {
                "performance": {
                    "trend": "improving",
                    "change": quality_scores["performance"]["improvement"],
                },
                "security": {
                    "trend": "stable",
                    "change": quality_scores["security"]["improvement"],
                },
                "scalability": {
                    "trend": "improving",
                    "change": quality_scores["scalability"]["improvement"],
                },
                "reliability": {
                    "trend": "stable",
                    "change": quality_scores["reliability"]["improvement"],
                },
                "maintainability": {
                    "trend": "improving",
                    "change": quality_scores["maintainability"]["improvement"],
                },
                "usability": {
                    "trend": "stable",
                    "change": quality_scores["usability"]["improvement"],
                },
            },
        }

        # Attribute scores for visualization
        for attribute, scores in quality_scores.items():
            if attribute != "overall":
                dashboard["attribute_scores"][attribute] = {
                    "current": scores["current_score"],
                    "optimized": scores["optimized_score"],
                    "target": scores["target_score"],
                    "improvement": scores["improvement"],
                    "status": "excellent"
                    if scores["achievement_rate"] > 0.9
                    else "good"
                    if scores["achievement_rate"] > 0.7
                    else "needs_improvement",
                }

        # Top improvement areas
        improvement_areas = sorted(
            [(attr, scores) for attr, scores in dashboard["attribute_scores"].items()],
            key=lambda x: x[1]["improvement"],
            reverse=True,
        )[:5]

        dashboard["improvement_areas"] = [
            {"attribute": attr, "improvement": scores["improvement"], "status": scores["status"]}
            for attr, scores in improvement_areas
        ]

        return dashboard

    def _generate_implementation_roadmap(
        self, recommendations: List[Dict], context: Dict
    ) -> Dict[str, Any]:
        """Generate implementation roadmap for quality improvements."""
        # Group recommendations by priority and complexity
        high_priority = [r for r in recommendations if r["priority"] == "high"]
        medium_priority = [r for r in recommendations if r["priority"] == "medium"]
        low_priority = [r for r in recommendations if r["priority"] == "low"]

        # Create phases
        phases = []

        # Phase 1: High priority, low complexity
        phase1_items = [r for r in high_priority if r["complexity"] == "low"]
        if phase1_items:
            phases.append(
                {
                    "phase": 1,
                    "name": "Quick Wins",
                    "duration_weeks": 2,
                    "description": "High-impact, low-complexity improvements",
                    "items": phase1_items,
                    "expected_improvement": sum(r["potential_improvement"] for r in phase1_items),
                }
            )

        # Phase 2: High priority, medium complexity
        phase2_items = [r for r in high_priority if r["complexity"] == "medium"]
        if phase2_items:
            phases.append(
                {
                    "phase": 2,
                    "name": "Strategic Improvements",
                    "duration_weeks": 6,
                    "description": "High-impact, medium-complexity improvements",
                    "items": phase2_items,
                    "expected_improvement": sum(r["potential_improvement"] for r in phase2_items),
                }
            )

        # Phase 3: Medium priority
        if medium_priority:
            phases.append(
                {
                    "phase": 3,
                    "name": "Enhanced Quality",
                    "duration_weeks": 8,
                    "description": "Medium-priority improvements",
                    "items": medium_priority[:5],
                    "expected_improvement": sum(
                        r["potential_improvement"] for r in medium_priority[:5]
                    ),
                }
            )

        # Phase 4: Remaining items
        remaining_items = (
            low_priority
            + medium_priority[5:]
            + [r for r in high_priority if r["complexity"] == "high"]
        )
        if remaining_items:
            phases.append(
                {
                    "phase": 4,
                    "name": "Complete Optimization",
                    "duration_weeks": 12,
                    "description": "Remaining quality improvements",
                    "items": remaining_items[:10],
                    "expected_improvement": sum(
                        r["potential_improvement"] for r in remaining_items[:10]
                    ),
                }
            )

        # Calculate total duration and improvement
        total_duration = sum(phase["duration_weeks"] for phase in phases)
        total_improvement = sum(phase["expected_improvement"] for phase in phases)

        roadmap = {
            "phases": phases,
            "total_duration_weeks": total_duration,
            "total_expected_improvement": total_improvement,
            "timeline_months": round(total_duration / 4.33, 1),  # Convert weeks to months
            "resource_requirements": self._calculate_resource_requirements(phases),
            "success_metrics": self._define_success_metrics(phases),
        }

        return roadmap

    def _calculate_resource_requirements(self, phases: List[Dict]) -> Dict[str, Any]:
        """Calculate resource requirements for implementation."""
        total_developers = 0
        phase_requirements = []

        for phase in phases:
            phase_devs = 0
            for item in phase["items"]:
                effort = self._estimate_implementation_effort({"complexity": item["complexity"]})
                phase_devs = max(phase_devs, int(effort["resources"].split("-")[0].split()[0]))

            phase_requirements.append(
                {
                    "phase": phase["phase"],
                    "developers": phase_devs,
                    "duration_weeks": phase["duration_weeks"],
                }
            )
            total_developers = max(total_developers, phase_devs)

        return {
            "peak_developers": total_developers,
            "phase_requirements": phase_requirements,
            "total_effort_months": sum(
                req["developers"] * req["duration_weeks"] for req in phase_requirements
            )
            / 4.33,
        }

    def _define_success_metrics(self, phases: List[Dict]) -> List[Dict]:
        """Define success metrics for the roadmap."""
        metrics = []

        # Overall quality improvement metrics
        metrics.append(
            {
                "metric": "overall_quality_score",
                "target": "0.85",
                "measurement": "Quality assessment score",
                "frequency": "monthly",
            }
        )

        # Phase-specific metrics
        for phase in phases:
            phase_name = phase["name"].lower().replace(" ", "_")
            metrics.append(
                {
                    "metric": f"{phase_name}_completion",
                    "target": "100%",
                    "measurement": f"Percentage of {phase['name']} items completed",
                    "frequency": "phase_end",
                }
            )

        # Quality attribute metrics
        for attribute in ["performance", "security", "scalability", "reliability"]:
            metrics.append(
                {
                    "metric": f"{attribute}_score",
                    "target": "0.8",
                    "measurement": f"{attribute.title()} quality score",
                    "frequency": "monthly",
                }
            )

        return metrics

    def _define_quality_metrics(self, context: Dict) -> List[Dict]:
        """Define quality metrics for monitoring."""
        metrics = []

        # Performance metrics
        metrics.extend(
            [
                {
                    "metric": "response_time",
                    "target": "< 2s",
                    "description": "Average response time for API calls",
                    "unit": "seconds",
                    "frequency": "continuous",
                },
                {
                    "metric": "throughput",
                    "target": "> 1000 req/s",
                    "description": "System throughput capacity",
                    "unit": "requests/second",
                    "frequency": "continuous",
                },
                {
                    "metric": "resource_utilization",
                    "target": "70 - 80%",
                    "description": "CPU and memory utilization",
                    "unit": "percentage",
                    "frequency": "continuous",
                },
            ]
        )

        # Security metrics
        metrics.extend(
            [
                {
                    "metric": "vulnerability_count",
                    "target": "< 5",
                    "description": "Number of critical vulnerabilities",
                    "unit": "count",
                    "frequency": "weekly",
                },
                {
                    "metric": "security_score",
                    "target": "> 85",
                    "description": "Security assessment score",
                    "unit": "score",
                    "frequency": "monthly",
                },
            ]
        )

        # Reliability metrics
        metrics.extend(
            [
                {
                    "metric": "uptime",
                    "target": "> 99.9%",
                    "description": "System availability",
                    "unit": "percentage",
                    "frequency": "continuous",
                },
                {
                    "metric": "mttr",
                    "target": "< 1 hour",
                    "description": "Mean time to recovery",
                    "unit": "hours",
                    "frequency": "monthly",
                },
            ]
        )

        # Scalability metrics
        metrics.extend(
            [
                {
                    "metric": "user_capacity",
                    "target": f">{context.get('user_count', 100) * 10}",
                    "description": "Supported user capacity",
                    "unit": "users",
                    "frequency": "monthly",
                },
                {
                    "metric": "auto_scaling_events",
                    "target": "> 5/month",
                    "description": "Auto-scaling trigger events",
                    "unit": "count",
                    "frequency": "monthly",
                },
            ]
        )

        return metrics

    def _define_quality_targets(self, context: Dict) -> Dict[str, Any]:
        """Define quality targets based on context."""
        base_targets = {
            "performance": {"score": 0.8, "response_time": 2.0, "throughput": 1000},
            "security": {"score": 0.9, "vulnerabilities": 5, "compliance": 100},
            "scalability": {
                "score": 0.7,
                "users": context.get("user_count", 100) * 10,
                "scaling": "horizontal",
            },
            "reliability": {"score": 0.8, "uptime": 99.9, "mttr": 1.0},
            "maintainability": {"score": 0.7, "coverage": 80, "documentation": 90},
            "usability": {"score": 0.8, "satisfaction": 85, "completion": 90},
        }

        # Adjust targets based on context
        if context.get("is_critical", False):
            base_targets["reliability"]["score"] = 0.9
            base_targets["reliability"]["uptime"] = 99.99
            base_targets["security"]["score"] = 0.95

        if context.get("user_count", 0) > 10000:
            base_targets["scalability"]["score"] = 0.8
            base_targets["performance"]["throughput"] = 5000

        if context.get("compliance_requirements"):
            base_targets["security"]["compliance"] = 100
            base_targets["security"]["score"] = 0.95

        return base_targets

    def _extract_quality_insights(self, quality_analysis: Dict, context: Dict) -> List[str]:
        """Extract key insights from quality analysis."""
        insights = []

        # High-scoring attributes
        high_scoring = [
            attr for attr, analysis in quality_analysis.items() if analysis["current_score"] > 0.7
        ]
        if high_scoring:
            insights.append(f"Strong in {', '.join(high_scoring)} quality attributes")

        # Low-scoring attributes
        low_scoring = [
            attr for attr, analysis in quality_analysis.items() if analysis["current_score"] < 0.5
        ]
        if low_scoring:
            insights.append(f"Needs improvement in {', '.join(low_scoring)} quality attributes")

        # Context-specific insights
        if context.get("user_count", 0) > 1000:
            insights.append("Large user base requires performance and scalability focus")

        if context.get("is_critical", False):
            insights.append("Critical system requires high reliability and security")

        if context.get("compliance_requirements"):
            insights.append("Compliance requirements drive security and documentation standards")

        return insights[:5]
