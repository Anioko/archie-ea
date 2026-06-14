"""
Strategic Recommendation Engine

LLM-agnostic recommendation engine for strategic planning dashboards.
Uses whatever LLM provider the user has configured in APISettings (no hardcoded models).

Features:
- Context-aware prompts per dashboard (capability_health, investment_matrix, risk_assessment, impact_analysis)
- Uses existing LLMService infrastructure (respects user's configured provider)
- Confidence scoring for each recommendation
- User feedback tracking (ratings, implementation status)
- Full LLM metadata (model, provider, tokens)
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models.strategic import StrategicRecommendation
from app.modules.ai_chat.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class StrategicRecommendationEngine:
    """
    LLM-agnostic recommendation engine for strategic planning.
    
    Generates context-aware recommendations using user's configured LLM provider.
    """

    VALID_DASHBOARDS = [
        "capability_health",
        "investment_matrix",
        "risk_assessment",
        "impact_analysis",
    ]

    def __init__(self):
        """Initialize recommendation engine with LLM service."""
        self.llm_service = LLMService()

    def generate_recommendations(
        self,
        dashboard: str,
        context: Dict[str, Any],
        max_recommendations: int = 5,
        created_by_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate LLM-powered recommendations for a strategic dashboard.

        Args:
            dashboard: Dashboard name ('capability_health', 'investment_matrix', 'risk_assessment', 'impact_analysis')
            context: Rich context dict with org info, metrics, initiatives
            max_recommendations: Maximum number of recommendations to generate (default 5)
            created_by_id: User ID creating the recommendations

        Returns:
            List of recommendation dicts with confidence scores and metadata

        Raises:
            ValueError: If dashboard name is invalid
        """
        # Validate dashboard
        if dashboard not in self.VALID_DASHBOARDS:
            raise ValueError(
                f"Invalid dashboard: {dashboard}. Must be one of {self.VALID_DASHBOARDS}"
            )

        logger.info(f"Generating {max_recommendations} recommendations for {dashboard}")

        # Build context-aware prompt
        prompt = self._build_prompt(dashboard, context, max_recommendations)

        try:
            # Use the user's configured provider (respects APISettings)
            provider, model = LLMService._get_configured_provider()

            logger.info(f"Using {provider}/{model} for strategic recommendations")

            # Call LLM
            response_text, interaction = LLMService._call_llm(
                prompt=prompt, model=model, provider=provider
            )

            # Parse JSON response
            recommendations = self._parse_response(response_text)

            if not recommendations:
                logger.warning("No recommendations parsed from LLM response")
                return []

            # Enrich with metadata
            for rec in recommendations:
                rec["model_used"] = (interaction.model_name if interaction else model)[:100]
                rec["provider_used"] = provider
                rec["dashboard"] = dashboard
                rec["prompt_tokens"] = interaction.token_count_input if interaction else None
                rec["completion_tokens"] = (
                    interaction.token_count_output if interaction else None
                )

            # Store in database
            stored_recs = self._store_recommendations(recommendations, created_by_id)

            logger.info(
                f"Generated and stored {len(stored_recs)} recommendations for {dashboard}"
            )

            return [rec.to_dict() for rec in stored_recs]

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}", exc_info=True)
            return []

    def _build_prompt(
        self, dashboard: str, context: Dict[str, Any], max_recs: int
    ) -> str:
        """
        Build context-rich prompt for specific dashboard.

        Args:
            dashboard: Dashboard name
            context: Context dict with org info and metrics
            max_recs: Maximum recommendations to generate

        Returns:
            Formatted prompt string
        """
        # Extract common context
        org_context = context.get("organization", {})
        industry = org_context.get("industry", "general")
        size = org_context.get("size", "medium")
        risk_tolerance = org_context.get("risk_tolerance", "moderate")

        # Dashboard-specific prompt templates
        if dashboard == "capability_health":
            return self._build_capability_health_prompt(
                context, industry, size, risk_tolerance, max_recs
            )
        elif dashboard == "investment_matrix":
            return self._build_investment_matrix_prompt(
                context, industry, size, risk_tolerance, max_recs
            )
        elif dashboard == "risk_assessment":
            return self._build_risk_assessment_prompt(
                context, industry, size, risk_tolerance, max_recs
            )
        elif dashboard == "impact_analysis":
            return self._build_impact_analysis_prompt(
                context, industry, size, risk_tolerance, max_recs
            )
        else:
            raise ValueError(f"Unknown dashboard: {dashboard}")

    def _build_capability_health_prompt(
        self,
        context: Dict,
        industry: str,
        size: str,
        risk_tolerance: str,
        max_recs: int,
    ) -> str:
        """Build prompt for capability health dashboard."""
        metrics = context.get("metrics", {})
        capabilities = context.get("capabilities", [])
        active_initiatives = context.get("active_initiatives", [])

        return f"""You are an expert enterprise architect analyzing capability health for strategic planning.

ORGANIZATION CONTEXT:
- Industry: {industry}
- Size: {size} organization
- Risk Tolerance: {risk_tolerance}

CAPABILITY HEALTH DATA:
{json.dumps(metrics, indent=2)}

TOP CAPABILITIES (by health score):
{json.dumps(capabilities[:10], indent=2)}

ACTIVE INITIATIVES (avoid duplication):
{json.dumps(active_initiatives, indent=2)}

TASK:
Generate {max_recs} specific, actionable recommendations to improve capability health.
Consider:
1. Industry-specific best practices for {industry}
2. Organizational constraints (size: {size}, risk tolerance: {risk_tolerance})
3. Avoid duplicating active initiatives
4. Reference actual capability names from the data
5. Prioritize by business impact and feasibility

OUTPUT FORMAT:
Return ONLY a valid JSON array (no markdown, no code blocks):

[
  {{
    "title": "Brief action-oriented title (5-8 words)",
    "description": "Specific action plan referencing actual capabilities/systems (30-50 words)",
    "rationale": "Why this matters for THIS organization given their context (20-30 words)",
    "priority": "CRITICAL|HIGH|MEDIUM|LOW",
    "estimated_effort_weeks": <integer>,
    "expected_impact": "Quantified business impact (e.g., '15% reduction in...')",
    "dependencies": ["Prerequisite 1", "Prerequisite 2"],
    "confidence_score": <0.0-1.0 based on data availability>
  }}
]

Generate the JSON array now:"""

    def _build_investment_matrix_prompt(
        self,
        context: Dict,
        industry: str,
        size: str,
        risk_tolerance: str,
        max_recs: int,
    ) -> str:
        """Build prompt for investment matrix dashboard."""
        capability_scores = context.get("capability_scores", [])
        portfolio_metrics = context.get("portfolio_metrics", {})
        budget_constraints = context.get("budget_constraints", "not specified")

        return f"""You are an expert enterprise architect analyzing investment priorities for strategic planning.

ORGANIZATION CONTEXT:
- Industry: {industry}
- Size: {size} organization
- Risk Tolerance: {risk_tolerance}
- Budget Constraints: {budget_constraints}

INVESTMENT PORTFOLIO METRICS:
{json.dumps(portfolio_metrics, indent=2)}

TOP INVESTMENT PRIORITIES:
{json.dumps(capability_scores[:10], indent=2)}

TASK:
Generate {max_recs} specific investment recommendations that maximize ROI.
Consider:
1. Strategic importance vs current maturity gaps
2. Industry-specific investment patterns for {industry}
3. Budget constraints and phasing
4. Quick wins vs long-term strategic investments
5. Reference actual capability names and current scores

OUTPUT FORMAT:
Return ONLY a valid JSON array:

[
  {{
    "title": "Investment recommendation title",
    "description": "Specific investment plan with capability names and phasing",
    "rationale": "Business case and expected ROI",
    "priority": "CRITICAL|HIGH|MEDIUM|LOW",
    "estimated_effort_weeks": <integer>,
    "expected_impact": "Quantified ROI or business value",
    "dependencies": ["Prerequisites"],
    "confidence_score": <0.0-1.0>
  }}
]

Generate the JSON array now:"""

    def _build_risk_assessment_prompt(
        self,
        context: Dict,
        industry: str,
        size: str,
        risk_tolerance: str,
        max_recs: int,
    ) -> str:
        """Build prompt for risk assessment dashboard."""
        capability_risks = context.get("capability_risks", [])
        portfolio_metrics = context.get("portfolio_metrics", {})
        compliance_status = context.get("compliance_status", {})

        return f"""You are an expert enterprise architect analyzing portfolio risks for mitigation planning.

ORGANIZATION CONTEXT:
- Industry: {industry}
- Size: {size} organization
- Risk Tolerance: {risk_tolerance}

PORTFOLIO RISK METRICS:
{json.dumps(portfolio_metrics, indent=2)}

TOP RISKS:
{json.dumps(capability_risks[:10], indent=2)}

COMPLIANCE STATUS:
{json.dumps(compliance_status, indent=2)}

TASK:
Generate {max_recs} risk mitigation recommendations.
Consider:
1. Industry-specific regulatory requirements for {industry}
2. Risk tolerance level: {risk_tolerance}
3. Single points of failure vs technology debt vs compliance gaps
4. Prioritize by risk level and mitigation feasibility
5. Reference actual capabilities and risk factors

OUTPUT FORMAT:
Return ONLY a valid JSON array:

[
  {{
    "title": "Risk mitigation recommendation",
    "description": "Specific mitigation plan with affected capabilities",
    "rationale": "Risk impact and mitigation strategy",
    "priority": "CRITICAL|HIGH|MEDIUM|LOW",
    "estimated_effort_weeks": <integer>,
    "expected_impact": "Quantified risk reduction",
    "dependencies": ["Prerequisites"],
    "confidence_score": <0.0-1.0>
  }}
]

Generate the JSON array now:"""

    def _build_impact_analysis_prompt(
        self,
        context: Dict,
        industry: str,
        size: str,
        risk_tolerance: str,
        max_recs: int,
    ) -> str:
        """Build prompt for impact analysis dashboard."""
        capabilities = context.get("capabilities", [])
        applications = context.get("applications", [])
        dependencies = context.get("dependencies", {})

        return f"""You are an expert enterprise architect analyzing change impact for strategic planning.

ORGANIZATION CONTEXT:
- Industry: {industry}
- Size: {size} organization
- Risk Tolerance: {risk_tolerance}

CAPABILITIES:
{json.dumps(capabilities[:15], indent=2)}

APPLICATIONS:
{json.dumps(applications[:15], indent=2)}

DEPENDENCY SUMMARY:
{json.dumps(dependencies, indent=2)}

TASK:
Generate {max_recs} recommendations for managing change impact and dependencies.
Consider:
1. Cascade effects through capability dependencies
2. Application modernization opportunities
3. Integration complexity reduction
4. Vendor consolidation opportunities
5. Reference actual capabilities/applications

OUTPUT FORMAT:
Return ONLY a valid JSON array:

[
  {{
    "title": "Change management recommendation",
    "description": "Specific action plan with affected systems",
    "rationale": "Impact reduction strategy and benefits",
    "priority": "CRITICAL|HIGH|MEDIUM|LOW",
    "estimated_effort_weeks": <integer>,
    "expected_impact": "Quantified complexity or cost reduction",
    "dependencies": ["Prerequisites"],
    "confidence_score": <0.0-1.0>
  }}
]

Generate the JSON array now:"""

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse JSON response from LLM.

        Args:
            response_text: Raw LLM response

        Returns:
            List of validated recommendation dicts
        """
        try:
            # Try to find JSON array in response (remove markdown code blocks)
            json_match = re.search(r"\[[\s\S]*\]", response_text)
            if json_match:
                json_str = json_match.group(0)
                recommendations = json.loads(json_str)

                # Validate each recommendation has required fields
                validated = []
                required_fields = [
                    "title",
                    "description",
                    "rationale",
                    "priority",
                    "confidence_score",
                ]

                for rec in recommendations:
                    if all(field in rec for field in required_fields):
                        # Ensure confidence_score is valid
                        if 0.0 <= rec.get("confidence_score", 0.0) <= 1.0:
                            validated.append(rec)
                        else:
                            logger.warning(
                                f"Skipping recommendation with invalid confidence_score: {rec.get('confidence_score')}"
                            )
                    else:
                        logger.warning(
                            f"Skipping recommendation missing required fields: {rec}"
                        )

                return validated

            else:
                logger.error("No JSON array found in LLM response")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.debug(f"Response was: {response_text[:500]}...")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}", exc_info=True)
            return []

    def _store_recommendations(
        self, recommendations: List[Dict[str, Any]], created_by_id: Optional[int]
    ) -> List[StrategicRecommendation]:
        """
        Store recommendations in database.

        Args:
            recommendations: List of recommendation dicts
            created_by_id: User ID creating the recommendations

        Returns:
            List of StrategicRecommendation model instances
        """
        stored = []

        try:
            for rec_data in recommendations:
                rec = StrategicRecommendation(
                    dashboard=rec_data["dashboard"],
                    capability_id=rec_data.get("capability_id"),
                    title=rec_data["title"],
                    description=rec_data["description"],
                    rationale=rec_data["rationale"],
                    priority=rec_data["priority"],
                    estimated_effort_weeks=rec_data.get("estimated_effort_weeks"),
                    expected_impact=rec_data.get("expected_impact"),
                    dependencies=rec_data.get("dependencies"),
                    confidence_score=rec_data["confidence_score"],
                    model_used=rec_data["model_used"],
                    provider_used=rec_data["provider_used"],
                    prompt_tokens=rec_data.get("prompt_tokens"),
                    completion_tokens=rec_data.get("completion_tokens"),
                    created_by_id=created_by_id,
                    is_active=True,
                )
                db.session.add(rec)
                stored.append(rec)

            db.session.commit()
            logger.info(f"Stored {len(stored)} recommendations in database")

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error storing recommendations: {e}", exc_info=True)
            raise

        return stored

    def rate_recommendation(
        self,
        recommendation_id: int,
        rating: int,
        feedback_notes: Optional[str] = None,
        was_implemented: bool = False,
        user_id: Optional[int] = None,
    ) -> bool:
        """
        Store user feedback on recommendation quality.

        Args:
            recommendation_id: ID of recommendation to rate
            rating: User rating (1-5 stars)
            feedback_notes: Optional feedback text
            was_implemented: Whether recommendation was actually implemented
            user_id: User providing the rating

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If rating is not 1-5
        """
        if not 1 <= rating <= 5:
            raise ValueError(f"Rating must be 1-5, got {rating}")

        try:
            rec = StrategicRecommendation.query.get(recommendation_id)
            if not rec:
                logger.error(f"Recommendation {recommendation_id} not found")
                return False

            rec.user_rating = rating
            rec.feedback_notes = feedback_notes
            rec.was_implemented = was_implemented
            rec.rated_at = datetime.utcnow()
            rec.rated_by_id = user_id

            db.session.commit()
            logger.info(f"Rated recommendation {recommendation_id}: {rating} stars")

            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error rating recommendation: {e}", exc_info=True)
            return False

    def get_recommendations(
        self,
        dashboard: str,
        capability_id: Optional[int] = None,
        limit: int = 10,
        include_rated: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch stored recommendations from database.

        Args:
            dashboard: Dashboard name
            capability_id: Optional filter by capability
            limit: Maximum recommendations to return
            include_rated: Whether to include already-rated recommendations

        Returns:
            List of recommendation dicts
        """
        try:
            query = StrategicRecommendation.query.filter_by(
                dashboard=dashboard, is_active=True
            )

            if capability_id:
                query = query.filter_by(capability_id=capability_id)

            if not include_rated:
                query = query.filter(StrategicRecommendation.user_rating.is_(None))

            recommendations = (
                query.order_by(StrategicRecommendation.created_at.desc())
                .limit(limit)
                .all()
            )

            return [rec.to_dict() for rec in recommendations]

        except Exception as e:
            logger.error(f"Error fetching recommendations: {e}", exc_info=True)
            return []
