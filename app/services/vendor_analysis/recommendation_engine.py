"""
Recommendation Engine

AI-powered vendor recommendation engine that provides:
- Intelligent vendor selection with transparent reasoning
- Explainable AI recommendations
- Alternative scenarios and what-if analysis
- Risk-aware decision support
- Implementation roadmap generation
"""

import json
import logging
from decimal import Decimal
from typing import Dict, List

from app.models import AnalysisRecommendation, OptionsAnalysis, VendorOption
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    AI-powered recommendation engine for vendor selection.

    Uses LLM to generate intelligent, explainable recommendations
    based on comprehensive vendor analysis data.
    FALLBACK: Generates algorithmic recommendation if LLM unavailable.
    """

    def __init__(self):
        """Initialize recommendation engine with LLM service."""
        self.llm_service = LLMService()

    def generate_recommendation(
        self, analysis: OptionsAnalysis, vendor_options: List[VendorOption], use_ai: bool = True
    ) -> AnalysisRecommendation:
        """
        Generate vendor recommendation (AI-powered or algorithmic).

        Args:
            analysis: The OptionsAnalysis session
            vendor_options: List of evaluated VendorOptions
            use_ai: If False, skip LLM and use pure algorithm

        Returns:
            AnalysisRecommendation with insights
        """
        # Get top 3 vendors by score
        sorted_vendors = sorted(vendor_options, key=lambda v: v.total_score or 0, reverse=True)[:3]

        if not sorted_vendors:
            raise ValueError("No vendor options available for recommendation")

        # Create recommendation record
        recommendation = AnalysisRecommendation(
            analysis_id=analysis.id,
            recommended_vendor_option_id=sorted_vendors[0].id,
            second_choice_id=sorted_vendors[1].id if len(sorted_vendors) > 1 else None,
            third_choice_id=sorted_vendors[2].id if len(sorted_vendors) > 2 else None,
        )

        if use_ai:
            # Prepare context for AI
            context = self._prepare_recommendation_context(analysis, sorted_vendors)

            # Generate AI recommendation
            ai_response = self._call_ai_for_recommendation(context)

            # Populate from AI response
            self._populate_recommendation(recommendation, ai_response, sorted_vendors)

            # Track LLM usage
            recommendation.llm_model_used = ai_response.get("model_used", "unknown")
            recommendation.llm_tokens_used = ai_response.get("tokens_used", 0)
            recommendation.llm_cost = Decimal(str(ai_response.get("cost", 0.0)))
            recommendation.prompt_version = "v1.0"
        else:
            # Use pure algorithmic recommendation
            logger.info("Generating algorithmic recommendation (no LLM)")
            self._generate_algorithmic_recommendation(recommendation, analysis, sorted_vendors)

        return recommendation

    def _prepare_recommendation_context(
        self, analysis: OptionsAnalysis, vendors: List[VendorOption]
    ) -> Dict:
        """
        Prepare comprehensive context for AI recommendation.

        Args:
            analysis: The analysis session
            vendors: Top vendor options

        Returns:
            Dict with all context data
        """
        capability = analysis.capability

        # Build vendor summaries
        vendor_summaries = []
        for i, vendor in enumerate(vendors, 1):
            summary = {
                "rank": i,
                "name": vendor.vendor_name,
                "total_score": float(vendor.total_score or 0),
                "scores": {
                    "cost": float(vendor.cost_score or 0),
                    "capability_coverage": float(vendor.capability_coverage_score or 0),
                    "risk": float(vendor.risk_score or 0),
                    "strategic_fit": float(vendor.strategic_fit_score or 0),
                    "implementation": float(vendor.implementation_score or 0),
                },
                "tco_5_year": float(vendor.tco_total or 0),
                "implementation_weeks": vendor.estimated_implementation_weeks,
                "health_score": vendor.vendor_health_score,
                "capability_gaps": json.loads(vendor.capability_gaps)
                if vendor.capability_gaps
                else [],
                "pros": json.loads(vendor.pros) if vendor.pros else [],
                "cons": json.loads(vendor.cons) if vendor.cons else [],
            }
            vendor_summaries.append(summary)

        context = {
            "analysis_name": analysis.name,
            "capability": {
                "name": capability.name,
                "description": capability.description,
                "current_maturity": capability.current_maturity_level,
                "target_maturity": capability.target_maturity_level,
                "maturity_gap": capability.maturity_gap,
                "strategic_importance": capability.strategic_importance,
                "business_value": capability.business_value,
            },
            "criteria_weights": analysis.get_criteria_weights(),
            "budget_constraint": float(analysis.budget_constraint)
            if analysis.budget_constraint
            else None,
            "vendors": vendor_summaries,
            "analysis_type": analysis.analysis_type,
            "tco_years": analysis.tco_years,
        }

        return context

    def _call_ai_for_recommendation(self, context: Dict) -> Dict:
        """
        Call LLM service to generate recommendation.

        Args:
            context: Recommendation context

        Returns:
            Dict with AI-generated recommendation data
        """
        prompt = self._build_recommendation_prompt(context)

        try:
            # Call LLM service
            response = self.llm_service.generate_completion(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.3,  # Lower temperature for more consistent recommendations
                response_format="json",
            )

            # Parse JSON response
            if isinstance(response, dict) and "content" in response:
                content = response["content"]
                if isinstance(content, str):
                    ai_data = json.loads(content)
                else:
                    ai_data = content
            else:
                ai_data = response

            # Add usage metadata
            ai_data["model_used"] = response.get("model", "unknown")
            ai_data["tokens_used"] = response.get("usage", {}).get("total_tokens", 0)
            ai_data["cost"] = response.get("cost", 0.0)

            return ai_data

        except Exception as e:
            logger.error(f"Error calling AI for recommendation: {e}")
            # Return fallback recommendation
            return self._generate_fallback_recommendation(context)

    def _build_recommendation_prompt(self, context: Dict) -> str:
        """
        Build detailed prompt for AI recommendation.

        Args:
            context: Recommendation context

        Returns:
            Prompt string
        """
        prompt = f"""You are an expert Enterprise Architect providing vendor selection recommendations.

# ANALYSIS CONTEXT

**Capability**: {context['capability']['name']}
{context['capability']['description']}

**Strategic Importance**: {context['capability']['strategic_importance']}
**Business Value**: {context['capability']['business_value']}
**Maturity Gap**: Level {context['capability']['current_maturity']} → {context['capability']['target_maturity']} (gap of {context['capability']['maturity_gap']})

**Budget Constraint**: ${context['budget_constraint']:,.2f if context['budget_constraint'] else 0} {'(specified)' if context['budget_constraint'] else '(not specified)'}

**Decision Criteria Weights**:
- Cost: {context['criteria_weights']['cost'] * 100:.0f}%
- Capability Coverage: {context['criteria_weights']['capability_coverage'] * 100:.0f}%
- Risk: {context['criteria_weights']['risk'] * 100:.0f}%
- Strategic Fit: {context['criteria_weights']['strategic_fit'] * 100:.0f}%
- Implementation: {context['criteria_weights']['implementation'] * 100:.0f}%

# VENDOR OPTIONS EVALUATED

"""

        for vendor in context["vendors"]:
            prompt += f"""
## Rank #{vendor['rank']}: {vendor['name']}
**Total Score**: {vendor['total_score']:.1f}/100

**Dimension Scores**:
- Cost: {vendor['scores']['cost']:.1f}/100 (5 - year TCO: ${vendor['tco_5_year']:,.2f})
- Capability Coverage: {vendor['scores']['capability_coverage']:.1f}/100
- Risk: {vendor['scores']['risk']:.1f}/100
- Strategic Fit: {vendor['scores']['strategic_fit']:.1f}/100
- Implementation: {vendor['scores']['implementation']:.1f}/100 ({vendor['implementation_weeks']} weeks)

**Vendor Health**: {vendor['health_score']}/100

**Capability Gaps**: {len(vendor['capability_gaps'])} identified
{json.dumps(vendor['capability_gaps'], indent=2) if vendor['capability_gaps'] else 'None'}

**Strengths**: {', '.join(vendor['pros']) if vendor['pros'] else 'Not specified'}
**Concerns**: {', '.join(vendor['cons']) if vendor['cons'] else 'Not specified'}

"""

        prompt += """
# YOUR TASK

Provide a comprehensive vendor recommendation in JSON format with the following structure:

{
  "recommended_vendor": "Name of recommended vendor",
  "rationale": "2 - 3 paragraph explanation of why this vendor is recommended, considering the weighted criteria, capability requirements, and strategic context",
  "confidence_score": 0.85,  // 0.0 - 1.0, your confidence in this recommendation
  "confidence_explanation": "Brief explanation of confidence level",
  "key_strengths": ["strength 1", "strength 2", "strength 3"],  // Top 3 - 5 strengths
  "key_concerns": ["concern 1", "concern 2"],  // Top 2 - 3 concerns to address
  "decision_factors": {
    "primary": "Most important factor",
    "secondary": "Second most important factor",
    "differentiator": "What made this vendor stand out"
  },
  "identified_risks": [
    {"risk": "Risk description", "severity": "high/medium/low", "probability": "high/medium/low"}
  ],
  "mitigation_recommendations": [
    {"risk": "Risk description", "mitigation": "How to mitigate", "cost": 5000}
  ],
  "implementation_roadmap": [
    {"phase": 1, "name": "Phase name", "tasks": ["task1", "task2"], "duration_weeks": 4},
    {"phase": 2, "name": "Phase name", "tasks": ["task1", "task2"], "duration_weeks": 6}
  ],
  "estimated_timeline_weeks": 16,
  "estimated_total_cost": 250000,
  "roi_estimate": {
    "year1": -100000,  // Implementation costs
    "year2": 50000,    // Beginning to see value
    "year3": 200000,   // Full value realization
    "year4": 250000,
    "year5": 300000
  },
  "payback_period_months": 18,
  "alternative_scenarios": [
    {
      "scenario": "If budget reduced by 30%",
      "recommendation": "Consider Vendor B instead",
      "tradeoffs": "Lower initial cost but longer implementation"
    }
  ]
}

Be specific, data-driven, and actionable. Focus on business value and risk-aware decision making.
"""

        return prompt

    def _populate_recommendation(
        self, recommendation: AnalysisRecommendation, ai_response: Dict, vendors: List[VendorOption]
    ) -> None:
        """
        Populate recommendation object from AI response.

        Args:
            recommendation: The recommendation object to populate
            ai_response: AI-generated data
            vendors: List of vendor options
        """
        # Basic recommendation data
        recommendation.rationale = ai_response.get(
            "rationale", "AI-generated recommendation based on weighted scoring."
        )
        recommendation.confidence_score = float(ai_response.get("confidence_score", 0.7))
        recommendation.confidence_explanation = ai_response.get("confidence_explanation", "")

        # Key factors
        recommendation.key_strengths = json.dumps(ai_response.get("key_strengths", []))
        recommendation.key_concerns = json.dumps(ai_response.get("key_concerns", []))
        recommendation.decision_factors = json.dumps(ai_response.get("decision_factors", {}))

        # Risk assessment
        recommendation.identified_risks = json.dumps(ai_response.get("identified_risks", []))
        recommendation.mitigation_recommendations = json.dumps(
            ai_response.get("mitigation_recommendations", [])
        )

        # Implementation planning
        recommendation.implementation_roadmap = json.dumps(
            ai_response.get("implementation_roadmap", [])
        )
        recommendation.estimated_timeline_weeks = ai_response.get("estimated_timeline_weeks")

        estimated_cost = ai_response.get("estimated_total_cost")
        if estimated_cost:
            recommendation.estimated_total_cost = Decimal(str(estimated_cost))

        # ROI
        recommendation.roi_estimate = json.dumps(ai_response.get("roi_estimate", {}))
        recommendation.payback_period_months = ai_response.get("payback_period_months")

        # Alternative scenarios
        recommendation.alternative_scenarios = json.dumps(
            ai_response.get("alternative_scenarios", [])
        )

    def _generate_fallback_recommendation(self, context: Dict) -> Dict:
        """
        Generate fallback recommendation if AI fails.

        Args:
            context: Recommendation context

        Returns:
            Dict with basic recommendation
        """
        top_vendor = context["vendors"][0]

        return {
            "recommended_vendor": top_vendor["name"],
            "rationale": f"{top_vendor['name']} achieved the highest overall score of {top_vendor['total_score']:.1f}/100 based on the weighted criteria. "
            f"It scored particularly well in capability coverage ({top_vendor['scores']['capability_coverage']:.1f}/100) and demonstrates strong strategic fit.",
            "confidence_score": 0.6,
            "confidence_explanation": "Automated scoring-based recommendation (AI generation unavailable)",
            "key_strengths": top_vendor.get(
                "pros", ["High overall score", "Good capability coverage"]
            ),
            "key_concerns": top_vendor.get(
                "cons", ["Review implementation timeline", "Validate cost estimates"]
            ),
            "decision_factors": {
                "primary": "Highest weighted score",
                "secondary": "Strong capability coverage",
                "differentiator": "Best balance across all criteria",
            },
            "identified_risks": [
                {"risk": "Implementation complexity", "severity": "medium", "probability": "medium"}
            ],
            "mitigation_recommendations": [
                {
                    "risk": "Implementation complexity",
                    "mitigation": "Engage vendor professional services",
                    "cost": 50000,
                }
            ],
            "implementation_roadmap": [
                {
                    "phase": 1,
                    "name": "Planning & Setup",
                    "tasks": ["Requirements validation", "Architecture design"],
                    "duration_weeks": 4,
                },
                {
                    "phase": 2,
                    "name": "Implementation",
                    "tasks": ["Development", "Integration"],
                    "duration_weeks": 8,
                },
                {
                    "phase": 3,
                    "name": "Testing & Deployment",
                    "tasks": ["Testing", "Deployment", "Training"],
                    "duration_weeks": 4,
                },
            ],
            "estimated_timeline_weeks": 16,
            "estimated_total_cost": float(top_vendor["tco_5_year"]),
            "roi_estimate": {
                "year1": -float(top_vendor["tco_5_year"]) * 0.4,
                "year2": float(top_vendor["tco_5_year"]) * 0.1,
                "year3": float(top_vendor["tco_5_year"]) * 0.3,
                "year4": float(top_vendor["tco_5_year"]) * 0.4,
                "year5": float(top_vendor["tco_5_year"]) * 0.5,
            },
            "payback_period_months": 24,
            "alternative_scenarios": [],
            "model_used": "fallback",
            "tokens_used": 0,
            "cost": 0.0,
        }

    def explain_decision(self, recommendation: AnalysisRecommendation) -> Dict:
        """
        Generate detailed explanation of the recommendation decision.

        Args:
            recommendation: The recommendation to explain

        Returns:
            Dict with decision explanation
        """
        explanation = {
            "recommended_vendor": recommendation.recommended_vendor.vendor_name
            if recommendation.recommended_vendor
            else "Unknown",
            "confidence": {
                "score": float(recommendation.confidence_score or 0),
                "explanation": recommendation.confidence_explanation,
            },
            "rationale": recommendation.rationale,
            "key_factors": {
                "strengths": recommendation.get_key_strengths(),
                "concerns": recommendation.get_key_concerns(),
                "decision_drivers": json.loads(recommendation.decision_factors)
                if recommendation.decision_factors
                else {},
            },
            "risk_assessment": {
                "risks": json.loads(recommendation.identified_risks)
                if recommendation.identified_risks
                else [],
                "mitigations": json.loads(recommendation.mitigation_recommendations)
                if recommendation.mitigation_recommendations
                else [],
            },
            "implementation": {
                "roadmap": recommendation.get_implementation_roadmap(),
                "timeline_weeks": recommendation.estimated_timeline_weeks,
                "total_cost": float(recommendation.estimated_total_cost or 0),
            },
            "financial": {
                "roi_by_year": recommendation.get_roi_estimate(),
                "payback_months": recommendation.payback_period_months,
            },
            "alternatives": json.loads(recommendation.alternative_scenarios)
            if recommendation.alternative_scenarios
            else [],
        }

        return explanation

    def suggest_alternatives(
        self, analysis: OptionsAnalysis, vendor_options: List[VendorOption], scenario: str
    ) -> List[Dict]:
        """
        Suggest alternative vendor recommendations for different scenarios.

        Args:
            analysis: The analysis session
            vendor_options: All vendor options
            scenario: Scenario description (e.g., "budget reduced by 30%")

        Returns:
            List of alternative recommendations
        """
        alternatives = []

        # Budget-constrained scenario
        if "budget" in scenario.lower():
            # Sort by cost score (higher = lower cost)
            by_cost = sorted(vendor_options, key=lambda v: v.cost_score or 0, reverse=True)
            if by_cost:
                alternatives.append(
                    {
                        "scenario": scenario,
                        "recommended_vendor": by_cost[0].vendor_name,
                        "rationale": f"Best cost option with TCO of ${by_cost[0].tco_total:,.2f}",
                        "tradeoffs": f"May sacrifice some capability coverage (score: {by_cost[0].capability_coverage_score:.1f}/100)",
                    }
                )

        # Risk-averse scenario
        if "risk" in scenario.lower() or "conservative" in scenario.lower():
            # Sort by risk score (higher = lower risk)
            by_risk = sorted(vendor_options, key=lambda v: v.risk_score or 0, reverse=True)
            if by_risk:
                alternatives.append(
                    {
                        "scenario": scenario,
                        "recommended_vendor": by_risk[0].vendor_name,
                        "rationale": f"Lowest risk option (risk score: {by_risk[0].risk_score:.1f}/100)",
                        "tradeoffs": f"May have higher cost (TCO: ${by_risk[0].tco_total:,.2f})",
                    }
                )

        # Fast implementation scenario
        if "fast" in scenario.lower() or "quick" in scenario.lower():
            # Sort by implementation score and timeline
            by_impl = sorted(
                vendor_options,
                key=lambda v: (
                    v.implementation_score or 0,
                    -(v.estimated_implementation_weeks or 999),
                ),
                reverse=True,
            )
            if by_impl:
                alternatives.append(
                    {
                        "scenario": scenario,
                        "recommended_vendor": by_impl[0].vendor_name,
                        "rationale": f"Fastest implementation ({by_impl[0].estimated_implementation_weeks} weeks, implementation score: {by_impl[0].implementation_score:.1f}/100)",
                        "tradeoffs": "Faster deployment may require more resources",
                    }
                )

        return alternatives

    def _generate_algorithmic_recommendation(
        self,
        recommendation: AnalysisRecommendation,
        analysis: OptionsAnalysis,
        sorted_vendors: List[VendorOption],
    ) -> None:
        """
        Generate recommendation using pure algorithm (no LLM).

        Uses template data and scoring to create readable recommendation.
        """
        top_vendor = sorted_vendors[0]
        weights = analysis.get_criteria_weights()

        # Determine why this vendor won
        score_breakdown = {
            "cost": float(top_vendor.cost_score or 0),
            "capability": float(top_vendor.capability_coverage_score or 0),
            "risk": float(top_vendor.risk_score or 0),
            "strategic_fit": float(top_vendor.strategic_fit_score or 0),
            "implementation": float(top_vendor.implementation_score or 0),
        }

        # Find strongest dimension
        strongest_dim = max(score_breakdown, key=score_breakdown.get)
        strongest_score = score_breakdown[strongest_dim]

        # Build rationale
        rationale_parts = [
            f"{top_vendor.vendor_name} scored highest overall with {float(top_vendor.total_score or 0):.1f}/100 points.",
            f"Strongest in {strongest_dim.replace('_', ' ')} ({strongest_score:.1f}/100).",
        ]

        if top_vendor.tco_total:
            rationale_parts.append(f"5 - year TCO: ${float(top_vendor.tco_total):,.0f}.")

        if top_vendor.capability_match_percentage:
            rationale_parts.append(
                f"Capability coverage: {top_vendor.capability_match_percentage:.0f}%."
            )

        if top_vendor.estimated_implementation_weeks:
            rationale_parts.append(
                f"Implementation time: {top_vendor.estimated_implementation_weeks} weeks."
            )

        recommendation.rationale = " ".join(rationale_parts)

        # Confidence based on score gap to second place
        if len(sorted_vendors) > 1:
            score_gap = float(top_vendor.total_score or 0) - float(
                sorted_vendors[1].total_score or 0
            )
            if score_gap > 15:
                recommendation.confidence_score = 0.9
            elif score_gap > 8:
                recommendation.confidence_score = 0.75
            else:
                recommendation.confidence_score = 0.6
        else:
            recommendation.confidence_score = 0.8

        # Key benefits
        benefits = []
        if score_breakdown["cost"] >= 75:
            benefits.append("Cost-effective solution")
        if score_breakdown["capability"] >= 75:
            benefits.append("Strong capability match")
        if score_breakdown["risk"] >= 75:
            benefits.append("Low-risk implementation")
        if score_breakdown["strategic_fit"] >= 75:
            benefits.append("Strategic alignment")
        if score_breakdown["implementation"] >= 75:
            benefits.append("Fast deployment")

        if not benefits:
            benefits = ["Balanced across all criteria"]

        recommendation.key_strengths = json.dumps(benefits[:4])

        # Considerations → key_concerns
        considerations = []
        if score_breakdown["cost"] < 60:
            considerations.append("Higher cost compared to alternatives")
        if score_breakdown["capability"] < 60:
            considerations.append("Some capability gaps may exist")
        if score_breakdown["risk"] < 60:
            considerations.append("Higher risk factors to mitigate")
        if score_breakdown["implementation"] < 60:
            considerations.append("Longer implementation timeline")

        if len(sorted_vendors) > 1:
            second = sorted_vendors[1]
            considerations.append(
                f"Consider {second.vendor_name} as alternative (score: {float(second.total_score or 0):.1f})"
            )

        recommendation.key_concerns = json.dumps(considerations[:4])

        # Implementation guidance → implementation_roadmap (phase format)
        impl_weeks = top_vendor.estimated_implementation_weeks or 12
        roadmap = [
            {
                "phase": 1,
                "name": "Planning & Procurement",
                "tasks": ["Review vendor contract terms", "Finalize stakeholder alignment"],
                "duration_weeks": max(2, impl_weeks // 4),
            },
            {
                "phase": 2,
                "name": "Setup & Configuration",
                "tasks": ["Environment setup", "Initial configuration"],
                "duration_weeks": max(2, impl_weeks // 3),
            },
            {
                "phase": 3,
                "name": "Implementation & Go-live",
                "tasks": [
                    f"Plan for {impl_weeks}-week implementation",
                    "Conduct proof of concept before full commitment",
                ],
                "duration_weeks": impl_weeks - max(2, impl_weeks // 4) - max(2, impl_weeks // 3),
            },
        ]
        recommendation.implementation_roadmap = json.dumps(roadmap)

        # Risks to mitigate → identified_risks (structured format)
        risk_items = []
        if top_vendor.vendor_lock_in_risk and top_vendor.vendor_lock_in_risk > 5:
            risk_items.append(
                {"risk": "High vendor lock-in", "severity": "high", "probability": "medium"}
            )
        if top_vendor.capability_gaps:
            try:
                gaps = json.loads(top_vendor.capability_gaps)
                if len(gaps) > 0:
                    risk_items.append(
                        {
                            "risk": f"{len(gaps)} capability gaps identified",
                            "severity": "medium",
                            "probability": "high",
                        }
                    )
            except (json.JSONDecodeError, ValueError):
                pass
        if top_vendor.implementation_complexity and top_vendor.implementation_complexity > 6:
            risk_items.append(
                {
                    "risk": "Complex implementation requires additional resources",
                    "severity": "medium",
                    "probability": "medium",
                }
            )

        if not risk_items:
            risk_items = [
                {
                    "risk": "Standard procurement and implementation risks",
                    "severity": "low",
                    "probability": "low",
                }
            ]

        recommendation.identified_risks = json.dumps(risk_items[:4])

        # Set metadata
        recommendation.llm_model_used = "algorithmic"
        recommendation.llm_tokens_used = 0
        recommendation.llm_cost = Decimal("0.00")
        recommendation.prompt_version = "algorithmic_v1.0"

        logger.info(
            f"Generated algorithmic recommendation: {top_vendor.vendor_name} with {recommendation.confidence_score} confidence"
        )
