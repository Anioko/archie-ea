"""
Technology Selection Agent

Recommends technology stacks based on constraints and
provides architecture principle compliance checking with vendor-neutral recommendations.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TechnologySelectionAgent:
    """
    Agent for recommending technology stacks and architectures.

    Provides vendor-neutral recommendations based on requirements,
    constraints, and architectural principles.
    """

    # Technology categories and options
    TECHNOLOGY_CATEGORIES = {
        "frontend": {
            "description": "Frontend frameworks and libraries",
            "options": {
                "react": {
                    "description": "Component-based UI library",
                    "pros": ["Large ecosystem", "Strong community", "Reusable components"],
                    "cons": ["Learning curve", "Bundle size", "Frequent updates"],
                    "fit_for": ["Complex UIs", "Single-page apps", "Component-heavy"],
                    "complexity": "medium",
                    "scalability": "high",
                    "learning_curve": "medium",
                },
                "vue": {
                    "description": "Progressive JavaScript framework",
                    "pros": ["Easy to learn", "Good documentation", "Flexible"],
                    "cons": ["Smaller ecosystem", "Fewer enterprise tools"],
                    "fit_for": [
                        "Simple to medium apps",
                        "Rapid prototyping",
                        "Progressive enhancement",
                    ],
                    "complexity": "low",
                    "scalability": "medium",
                    "learning_curve": "low",
                },
                "angular": {
                    "description": "Full-featured framework",
                    "pros": ["Enterprise-ready", "Complete solution", "TypeScript support"],
                    "cons": ["Complex", "Opinionated", "Heavy"],
                    "fit_for": ["Enterprise apps", "Large teams", "Complex forms"],
                    "complexity": "high",
                    "scalability": "high",
                    "learning_curve": "high",
                },
                "nextjs": {
                    "description": "React framework with SSR/SSG",
                    "pros": ["SEO friendly", "Performance", "React ecosystem"],
                    "cons": ["React dependency", "Complex setup"],
                    "fit_for": ["Content sites", "E-commerce", "SEO-critical apps"],
                    "complexity": "medium",
                    "scalability": "high",
                    "learning_curve": "medium",
                },
            },
        },
        "backend": {
            "description": "Backend frameworks and platforms",
            "options": {
                "nodejs": {
                    "description": "JavaScript runtime",
                    "pros": ["Fast", "Single language", "Large ecosystem"],
                    "cons": ["Single-threaded", "Memory limitations", "Callback hell"],
                    "fit_for": ["APIs", "Real-time apps", "Microservices"],
                    "complexity": "medium",
                    "scalability": "medium",
                    "learning_curve": "low",
                },
                "python": {
                    "description": "Python programming language",
                    "pros": ["Easy to learn", "Rich libraries", "AI/ML support"],
                    "cons": ["Performance", "GIL limitations", "Packaging"],
                    "fit_for": ["Data processing", "AI/ML", "Rapid prototyping"],
                    "complexity": "low",
                    "scalability": "medium",
                    "learning_curve": "low",
                },
                "java": {
                    "description": "Enterprise-grade language",
                    "pros": ["Performance", "Enterprise tools", "Type safety"],
                    "cons": ["Verbose", "Complex", "Memory usage"],
                    "fit_for": ["Enterprise apps", "Large systems", "High performance"],
                    "complexity": "high",
                    "scalability": "high",
                    "learning_curve": "high",
                },
                "dotnet": {
                    "description": "Microsoft development platform",
                    "pros": ["Enterprise support", "Performance", "Tooling"],
                    "cons": ["Platform lock-in", "Complex", "Cost"],
                    "fit_for": ["Enterprise apps", "Windows shops", "Microsoft stack"],
                    "complexity": "high",
                    "scalability": "high",
                    "learning_curve": "medium",
                },
                "go": {
                    "description": "Systems programming language",
                    "pros": ["Performance", "Concurrency", "Simple"],
                    "cons": ["Young ecosystem", "Verbose error handling"],
                    "fit_for": ["Microservices", "Systems tools", "Performance-critical"],
                    "complexity": "medium",
                    "scalability": "high",
                    "learning_curve": "medium",
                },
            },
        },
        "database": {
            "description": "Database technologies",
            "options": {
                "postgresql": {
                    "description": "Open-source relational database",
                    "pros": ["ACID compliance", "Rich features", "Extensible"],
                    "cons": ["Scaling limitations", "Complex setup"],
                    "fit_for": ["Transactional apps", "Complex queries", "Data integrity"],
                    "complexity": "medium",
                    "scalability": "medium",
                    "learning_curve": "medium",
                },
                "mysql": {
                    "description": "Popular open-source database",
                    "pros": ["Fast", "Easy to use", "Good ecosystem"],
                    "cons": ["Limited features", "Scaling issues"],
                    "fit_for": ["Web apps", "Simple to medium complexity", "Read-heavy"],
                    "complexity": "low",
                    "scalability": "medium",
                    "learning_curve": "low",
                },
                "mongodb": {
                    "description": "NoSQL document database",
                    "pros": ["Flexible schema", "Horizontal scaling", "JSON native"],
                    "cons": ["No ACID", "Query limitations", "Memory usage"],
                    "fit_for": ["Flexible data", "High write volume", "Rapid iteration"],
                    "complexity": "low",
                    "scalability": "high",
                    "learning_curve": "low",
                },
                "redis": {
                    "description": "In-memory data store",
                    "pros": ["Fast", "Simple", "Rich data types"],
                    "cons": ["Memory limitations", "Persistence overhead"],
                    "fit_for": ["Caching", "Sessions", "Real-time data"],
                    "complexity": "low",
                    "scalability": "medium",
                    "learning_curve": "low",
                },
                "elasticsearch": {
                    "description": "Search and analytics engine",
                    "pros": ["Full-text search", "Analytics", "Scalable"],
                    "cons": ["Complex", "Resource intensive", "Learning curve"],
                    "fit_for": ["Search apps", "Analytics", "Log analysis"],
                    "complexity": "high",
                    "scalability": "high",
                    "learning_curve": "high",
                },
            },
        },
        "infrastructure": {
            "description": "Infrastructure and deployment",
            "options": {
                "aws": {
                    "description": "Amazon Web Services",
                    "pros": ["Comprehensive", "Mature", "Scalable"],
                    "cons": ["Complex", "Cost", "Vendor lock-in"],
                    "fit_for": ["Enterprise apps", "Scalable solutions", "Global reach"],
                    "complexity": "high",
                    "scalability": "high",
                    "learning_curve": "high",
                },
                "azure": {
                    "description": "Microsoft Azure",
                    "pros": ["Enterprise tools", "Hybrid cloud", "Microsoft integration"],
                    "cons": ["Complex", "Cost", "Microsoft lock-in"],
                    "fit_for": ["Enterprise apps", "Microsoft shops", "Hybrid solutions"],
                    "complexity": "high",
                    "scalability": "high",
                    "learning_curve": "high",
                },
                "gcp": {
                    "description": "Google Cloud Platform",
                    "pros": ["AI/ML tools", "Pricing", "Performance"],
                    "cons": ["Smaller ecosystem", "Less mature", "Documentation"],
                    "fit_for": ["AI/ML apps", "Data analytics", "Performance-critical"],
                    "complexity": "medium",
                    "scalability": "high",
                    "learning_curve": "medium",
                },
                "onpremise": {
                    "description": "On-premise infrastructure",
                    "pros": ["Full control", "Security", "No vendor lock-in"],
                    "cons": ["High cost", "Limited scalability", "Management overhead"],
                    "fit_for": [
                        "Regulated industries",
                        "Security-critical",
                        "Existing investments",
                    ],
                    "complexity": "high",
                    "scalability": "low",
                    "learning_curve": "high",
                },
                "kubernetes": {
                    "description": "Container orchestration",
                    "pros": ["Portable", "Scalable", "Rich ecosystem"],
                    "cons": ["Complex", "Steep learning", "Operational overhead"],
                    "fit_for": ["Microservices", "Complex deployments", "Multi-cloud"],
                    "complexity": "high",
                    "scalability": "high",
                    "learning_curve": "high",
                },
            },
        },
    }

    # Architecture principles mapping
    ARCHITECTURE_PRINCIPLES = {
        "simplicity": {
            "description": "Keep solutions simple and understandable",
            "preferred": ["vue", "python", "mysql", "redis"],
            "avoid": ["kubernetes", "java", "elasticsearch"],
        },
        "performance": {
            "description": "Ensure adequate performance for requirements",
            "preferred": ["go", "nodejs", "redis", "postgresql"],
            "avoid": ["python", "mongodb", "onpremise"],
        },
        "scalability": {
            "description": "Design for growth and increased load",
            "preferred": ["kubernetes", "aws", "mongodb", "elasticsearch"],
            "avoid": ["onpremise", "mysql", "vue"],
        },
        "security": {
            "description": "Protect systems and data appropriately",
            "preferred": ["java", "dotnet", "postgresql", "onpremise"],
            "avoid": ["mongodb", "nodejs", "aws"],
        },
        "maintainability": {
            "description": "Ensure code can be maintained and evolved",
            "preferred": ["python", "vue", "postgresql", "kubernetes"],
            "avoid": ["nodejs", "mongodb", "onpremise"],
        },
        "cost_efficiency": {
            "description": "Optimize for total cost of ownership",
            "preferred": ["python", "vue", "mysql", "gcp"],
            "avoid": ["java", "dotnet", "aws", "onpremise"],
        },
    }

    async def recommend_technologies(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recommend technologies based on solution context.

        Args:
            context: Solution context including requirements and constraints

        Returns:
            Dictionary with technology recommendations and rationale
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

            # Analyze requirements
            requirements_analysis = self._analyze_requirements(context)

            # Score technologies against requirements
            technology_scores = self._score_technologies(requirements_analysis)

            # Generate recommendations
            recommendations = self._generate_recommendations(technology_scores, context)

            # Check architectural principle compliance
            principle_compliance = self._check_principle_compliance(recommendations, context)

            # Create technology stack
            technology_stack = self._create_technology_stack(recommendations, context)

            # Generate alternative stacks
            alternative_stacks = self._generate_alternative_stacks(recommendations, context)

            # Implementation considerations
            implementation_considerations = self._generate_implementation_considerations(
                recommendations, context
            )

            result = {
                "success": True,
                "requirements_analysis": requirements_analysis,
                "technology_scores": technology_scores,
                "recommendations": recommendations,
                "principle_compliance": principle_compliance,
                "technology_stack": technology_stack,
                "alternative_stacks": alternative_stacks,
                "implementation_considerations": implementation_considerations,
                "decision_factors": self._identify_decision_factors(context),
                "vendor_neutrality_note": "All recommendations are vendor-neutral and based on technical merits",
            }

            logger.info(
                f"Technology selection completed: {len(recommendations)} recommendations generated"
            )
            return result

        except Exception as e:
            logger.error(f"Error in technology selection: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendations": [],
            }

    def _analyze_requirements(self, context: Dict) -> Dict[str, Any]:
        """Analyze solution requirements to determine technology needs."""
        description = context.get("solution_description", "").lower()
        solution_type = context.get("solution_type", "").lower()
        user_count = context.get("user_count", 0)
        timeline_months = context.get("timeline_months", 12)
        is_critical = context.get("is_critical", False)
        compliance_requirements = context.get("compliance_requirements", [])
        constraints = [c.lower() for c in context.get("constraints", [])]

        requirements = {
            "performance": {
                "importance": "high"
                if user_count > 1000 or "performance" in description
                else "medium",
                "factors": [],
            },
            "scalability": {
                "importance": "high" if user_count > 5000 or "scale" in description else "medium",
                "factors": [],
            },
            "security": {
                "importance": "high" if is_critical or compliance_requirements else "medium",
                "factors": [],
            },
            "simplicity": {
                "importance": "high"
                if timeline_months < 6 or context.get("organization_size") == "smb"
                else "medium",
                "factors": [],
            },
            "maintainability": {
                "importance": "high" if timeline_months > 12 else "medium",
                "factors": [],
            },
            "cost_efficiency": {
                "importance": "high" if context.get("organization_size") == "smb" else "medium",
                "factors": [],
            },
        }

        # Add specific factors
        if user_count > 1000:
            requirements["performance"]["factors"].append("large_user_base")
            requirements["scalability"]["factors"].append("large_user_base")

        if is_critical:
            requirements["security"]["factors"].append("business_critical")
            requirements["reliability"] = {"importance": "high", "factors": ["business_critical"]}

        if compliance_requirements:
            requirements["security"]["factors"].append("compliance_requirements")

        if "real-time" in description or "instant" in description:
            requirements["performance"]["factors"].append("real_time_requirements")

        if "data" in description or "analytics" in description:
            requirements["scalability"]["factors"].append("data_processing")

        if "simple" in description or "quick" in description:
            requirements["simplicity"]["factors"].append("simplicity_needed")

        return requirements

    def _score_technologies(self, requirements: Dict) -> Dict[str, Any]:
        """Score technologies against requirements."""
        scores = {}

        for category, category_info in self.TECHNOLOGY_CATEGORIES.items():
            scores[category] = {}
            for tech_name, tech_info in category_info["options"].items():
                # Calculate score for each requirement
                requirement_scores = {}
                total_score = 0
                total_weight = 0

                for requirement, req_info in requirements.items():
                    if requirement in tech_info:
                        # Use predefined complexity/scalability values
                        if requirement == "performance":
                            score = self._normalize_score(tech_info.get("scalability", "medium"))
                        elif requirement == "scalability":
                            score = self._normalize_score(tech_info.get("scalability", "medium"))
                        elif requirement == "simplicity":
                            score = self._normalize_score(
                                tech_info.get("complexity", "medium"), invert=True
                            )
                        elif requirement == "maintainability":
                            score = self._normalize_score(
                                tech_info.get("learning_curve", "medium"), invert=True
                            )
                        else:
                            score = 0.5  # Default score for other requirements

                        weight = self._get_requirement_weight(req_info["importance"])
                        requirement_scores[requirement] = score
                        total_score += score * weight
                        total_weight += weight

                # Calculate final score
                final_score = total_score / total_weight if total_weight > 0 else 0.5
                fit_score = self._calculate_fit_score(tech_info, requirements)

                scores[category][tech_name] = {
                    "overall_score": round(final_score, 3),
                    "fit_score": round(fit_score, 3),
                    "requirement_scores": requirement_scores,
                    "technology_info": tech_info,
                }

        return scores

    def _normalize_score(self, value: str, invert: bool = False) -> float:
        """Normalize string values to numeric scores."""
        mapping = {"low": 0.25, "medium": 0.5, "high": 0.75}
        score = mapping.get(value, 0.5)
        return 1.0 - score if invert else score

    def _get_requirement_weight(self, importance: str) -> float:
        """Get weight for requirement importance."""
        mapping = {"low": 0.1, "medium": 0.2, "high": 0.3}
        return mapping.get(importance, 0.2)

    def _calculate_fit_score(self, tech_info: Dict, requirements: Dict) -> float:
        """Calculate how well technology fits the requirements."""
        fit_for = tech_info.get("fit_for", [])
        score = 0.5  # Base score

        # Boost score if technology fits requirements
        if any("complex" in req for req in requirements.get("scalability", {}).get("factors", [])):
            if any("Complex" in fit for fit in fit_for):
                score += 0.2

        if any("simple" in req for req in requirements.get("simplicity", {}).get("factors", [])):
            if any("Simple" in fit for fit in fit_for):
                score += 0.2

        if any(
            "performance" in req for req in requirements.get("performance", {}).get("factors", [])
        ):
            if any("Performance" in fit for fit in fit_for):
                score += 0.2

        return min(score, 1.0)

    def _generate_recommendations(self, technology_scores: Dict, context: Dict) -> List[Dict]:
        """Generate technology recommendations."""
        recommendations = []

        for category, category_scores in technology_scores.items():
            # Sort technologies by score
            sorted_techs = sorted(
                category_scores.items(),
                key=lambda x: x[1]["overall_score"],
                reverse=True,
            )

            # Get top 3 recommendations
            for i, (tech_name, tech_info) in enumerate(sorted_techs[:3]):
                recommendations.append(
                    {
                        "category": category,
                        "technology": tech_name,
                        "rank": i + 1,
                        "score": tech_info["overall_score"],
                        "fit_score": tech_info["fit_score"],
                        "description": tech_info["technology_info"]["description"],
                        "pros": tech_info["technology_info"]["pros"],
                        "cons": tech_info["technology_info"]["cons"],
                        "rationale": self._generate_recommendation_rationale(
                            tech_name, tech_info, category, context
                        ),
                        "confidence": "high"
                        if tech_info["overall_score"] > 0.7
                        else "medium"
                        if tech_info["overall_score"] > 0.5
                        else "low",
                    }
                )

        return recommendations

    def _generate_recommendation_rationale(
        self, tech_name: str, tech_info: Dict, category: str, context: Dict
    ) -> str:
        """Generate rationale for technology recommendation."""
        score = tech_info["overall_score"]
        tech_details = tech_info["technology_info"]

        rationale_parts = []

        # High score rationale
        if score > 0.7:
            rationale_parts.append(f"Strong match with requirements ({score:.1%} score)")
        elif score > 0.5:
            rationale_parts.append(f"Good fit for requirements ({score:.1%} score)")
        else:
            rationale_parts.append(f"Moderate fit for requirements ({score:.1%} score)")

        # Category-specific rationale
        if category == "frontend":
            if tech_name == "react":
                rationale_parts.append("Component-based approach supports complex UIs")
            elif tech_name == "vue":
                rationale_parts.append("Easy learning curve supports rapid development")
        elif category == "backend":
            if tech_name == "python":
                rationale_parts.append("Rich ecosystem supports rapid prototyping")
            elif tech_name == "java":
                rationale_parts.append("Enterprise-ready for large-scale systems")
        elif category == "database":
            if tech_name == "postgresql":
                rationale_parts.append("ACID compliance ensures data integrity")
            elif tech_name == "mongodb":
                rationale_parts.append("Flexible schema supports rapid iteration")

        # Context-specific rationale
        if (
            context.get("organization_size") == "smb"
            and tech_details.get("learning_curve") == "low"
        ):
            rationale_parts.append("Low learning curve suitable for SMB teams")

        if context.get("user_count", 0) > 1000 and tech_details.get("scalability") == "high":
            rationale_parts.append("High scalability supports large user base")

        return "; ".join(rationale_parts)

    def _check_principle_compliance(
        self, recommendations: List[Dict], context: Dict
    ) -> Dict[str, Any]:
        """Check compliance with architectural principles."""
        compliance = {}

        # Get top recommendation for each category
        top_recommendations = {}
        for rec in recommendations:
            if rec["rank"] == 1:
                top_recommendations[rec["category"]] = rec["technology"]

        # Check each principle
        for principle, principle_info in self.ARCHITECTURE_PRINCIPLES.items():
            principle_compliance = {
                "compliant": True,
                "violations": [],
                "score": 0.0,
                "recommendation": "",
            }

            # Check for violations
            for category, tech in top_recommendations.items():
                if tech in principle_info.get("avoid", []):
                    principle_compliance["violations"].append(
                        {
                            "category": category,
                            "technology": tech,
                            "reason": f"Technology not recommended for {principle}",
                        }
                    )
                    principle_compliance["compliant"] = False

            # Calculate compliance score
            if principle_compliance["violations"]:
                principle_compliance["score"] = max(
                    0, 1.0 - len(principle_compliance["violations"]) * 0.2
                )
                principle_compliance[
                    "recommendation"
                ] = f"Consider alternatives: {', '.join(principle_info.get('preferred', []))}"
            else:
                principle_compliance["score"] = 1.0
                principle_compliance["recommendation"] = "Good compliance with principle"

            compliance[principle] = principle_compliance

        # Overall compliance score
        overall_score = sum(info["score"] for info in compliance.values()) / len(compliance)
        compliance["overall"] = {
            "score": round(overall_score, 3),
            "compliant": overall_score > 0.7,
            "violations": sum(len(info["violations"]) for info in compliance.values()),
        }

        return compliance

    def _create_technology_stack(
        self, recommendations: List[Dict], context: Dict
    ) -> Dict[str, Any]:
        """Create a recommended technology stack."""
        stack = {
            "primary": {},
            "alternatives": {},
            "rationale": "",
            "implementation_complexity": "medium",
            "estimated_cost": "medium",
            "learning_curve": "medium",
        }

        # Get top recommendation for each category
        for rec in recommendations:
            if rec["rank"] == 1:
                stack["primary"][rec["category"]] = {
                    "technology": rec["technology"],
                    "score": rec["score"],
                    "confidence": rec["confidence"],
                }
            elif rec["rank"] == 2:
                stack["alternatives"][rec["category"]] = {
                    "technology": rec["technology"],
                    "score": rec["score"],
                    "confidence": rec["confidence"],
                }

        # Calculate overall stack metrics
        scores = [rec["score"] for rec in stack["primary"].values()]
        if scores:
            stack["overall_score"] = round(sum(scores) / len(scores), 3)
        else:
            stack["overall_score"] = 0.0

        # Determine complexity
        complexity_levels = []
        for category, tech_info in stack["primary"].items():
            # This is a simplified complexity calculation
            if tech_info["technology"] in ["java", "dotnet", "kubernetes", "elasticsearch"]:
                complexity_levels.append("high")
            elif tech_info["technology"] in ["python", "nodejs", "react", "postgresql"]:
                complexity_levels.append("medium")
            else:
                complexity_levels.append("low")

        if complexity_levels:
            stack["implementation_complexity"] = max(
                complexity_levels, key=lambda x: {"low": 1, "medium": 2, "high": 3}[x]
            )

        # Generate rationale
        stack[
            "rationale"
        ] = f"Selected stack based on {len(stack['primary'])} categories with overall score of {stack['overall_score']:.1%}"

        return stack

    def _generate_alternative_stacks(
        self, recommendations: List[Dict], context: Dict
    ) -> List[Dict]:
        """Generate alternative technology stacks."""
        alternatives = []

        # Group recommendations by rank
        rank_groups = {}
        for rec in recommendations:
            rank = rec["rank"]
            if rank not in rank_groups:
                rank_groups[rank] = {}
            rank_groups[rank][rec["category"]] = rec

        # Create stacks from different rank combinations
        for rank in [2, 3]:  # Use 2nd and 3rd choices
            if rank in rank_groups:
                stack = {
                    "name": f"Alternative Stack (Rank {rank} Choices)",
                    "technologies": {},
                    "overall_score": 0.0,
                    "rationale": f"Using rank {rank} choices for all categories",
                }

                for category, rec in rank_groups[rank].items():
                    stack["technologies"][category] = {
                        "technology": rec["technology"],
                        "score": rec["score"],
                    }

                # Calculate overall score
                scores = [rec["score"] for rec in stack["technologies"].values()]
                if scores:
                    stack["overall_score"] = round(sum(scores) / len(scores), 3)

                alternatives.append(stack)

        return alternatives

    def _generate_implementation_considerations(
        self, recommendations: List[Dict], context: Dict
    ) -> List[Dict]:
        """Generate implementation considerations for the technology stack."""
        considerations = []

        # Team skills consideration
        primary_techs = [rec["technology"] for rec in recommendations if rec["rank"] == 1]
        considerations.append(
            {
                "type": "team_skills",
                "title": "Team Skills Assessment",
                "description": f"Ensure team has skills for: {', '.join(primary_techs[:3])}",
                "priority": "high",
                "actions": [
                    "Conduct skills assessment",
                    "Plan training if needed",
                    "Consider hiring if gaps",
                ],
            }
        )

        # Learning curve consideration
        high_complexity_techs = [
            rec["technology"]
            for rec in recommendations
            if rec["rank"] == 1
            and rec["technology"] in ["java", "dotnet", "kubernetes", "elasticsearch"]
        ]
        if high_complexity_techs:
            considerations.append(
                {
                    "type": "learning_curve",
                    "title": "Learning Curve Management",
                    "description": f"Complex technologies require learning time: {', '.join(high_complexity_techs)}",
                    "priority": "medium",
                    "actions": [
                        "Allocate training time",
                        "Start with pilot projects",
                        "Consider expert consultation",
                    ],
                }
            )

        # Integration consideration
        considerations.append(
            {
                "type": "integration",
                "title": "Integration Planning",
                "description": "Plan integration between selected technologies",
                "priority": "high",
                "actions": [
                    "Design integration architecture",
                    "Plan data flow",
                    "Consider API contracts",
                ],
            }
        )

        # Timeline consideration
        timeline_months = context.get("timeline_months", 12)
        if timeline_months < 6:
            considerations.append(
                {
                    "type": "timeline",
                    "title": "Timeline Constraints",
                    "description": f"Tight {timeline_months}-month timeline requires efficient implementation",
                    "priority": "high",
                    "actions": [
                        "Use proven technologies",
                        "Minimize custom development",
                        "Consider phased rollout",
                    ],
                }
            )

        return considerations

    def _identify_decision_factors(self, context: Dict) -> List[Dict]:
        """Identify key factors influencing technology decisions."""
        factors = []

        # Organization size factor
        org_size = context.get("organization_size", "midmarket")
        factors.append(
            {
                "factor": "organization_size",
                "value": org_size,
                "impact": "medium",
                "description": f"{org_size.title()} organization affects technology complexity and cost tolerance",
            }
        )

        # Budget factor
        budget_range = context.get("budget_range", {})
        if budget_range.get("max", 0) > 0:
            factors.append(
                {
                    "factor": "budget",
                    "value": f"${budget_range.get('min', 0):,} - ${budget_range.get('max', 0):,}",
                    "impact": "high",
                    "description": f"Budget range affects technology choices and implementation approach",
                }
            )

        # Timeline factor
        timeline = context.get("timeline_months", 12)
        factors.append(
            {
                "factor": "timeline",
                "value": f"{timeline} months",
                "impact": "medium",
                "description": f"Timeline affects technology complexity and implementation approach",
            }
        )

        # Criticality factor
        is_critical = context.get("is_critical", False)
        factors.append(
            {
                "factor": "criticality",
                "value": "Critical" if is_critical else "Standard",
                "impact": "high",
                "description": "Critical systems require higher reliability and security standards",
            }
        )

        return factors
