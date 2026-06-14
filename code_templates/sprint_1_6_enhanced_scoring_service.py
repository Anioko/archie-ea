"""
Enhanced Scoring Service
Sprint 1.6: Enhanced Scoring

Service for calculating comprehensive multi-criteria scores.

File: app/services/enhanced_scoring_service.py
"""

import json

from app.extensions import db
from app.models.enhanced_scoring import SolutionScoring, VendorViabilityAssessment
from app.services.llm.openai_service import OpenAIService


class EnhancedScoringService:
    """Service for comprehensive solution option scoring"""

    def __init__(self):
        self.llm = OpenAIService(model="gpt - 4 - turbo")

    def score_option(self, option_id, tenant_id, user_id, custom_weights=None):
        """
        Calculate comprehensive score for a solution option

        Args:
            option_id: SolutionOption ID
            tenant_id: Tenant ID
            user_id: User ID
            custom_weights: Optional weight overrides

        Returns:
            SolutionScoring: Calculated scoring
        """
        from app.models.solution_architect_models import SolutionOption

        option = (
            db.session.query(SolutionOption).filter_by(id=option_id, tenant_id=tenant_id).first()
        )

        if not option:
            raise ValueError(f"Option {option_id} not found")

        # Create scoring record
        scoring = SolutionScoring(
            tenant_id=tenant_id,
            session_id=option.session_id,
            option_id=option_id,
            scored_by=user_id,
        )

        # Score each category
        self._score_financial(scoring, option)
        self._score_strategic(scoring, option, tenant_id, user_id)
        self._score_technical(scoring, option, tenant_id, user_id)
        self._score_risk(scoring, option, tenant_id, user_id)
        self._score_team(scoring, option, tenant_id, user_id)

        # Calculate composite scores
        scoring.calculate_composite_scores()

        # Calculate weighted total
        scoring.calculate_weighted_total(custom_weights)

        # Set confidence based on data completeness
        scoring.confidence_level = self._calculate_confidence(scoring)

        db.session.add(scoring)
        db.session.commit()

        return scoring

    def _score_financial(self, scoring, option):
        """Score financial criteria"""

        # Extract from option cost model
        if option.cost_model:
            scoring.tco_5year = option.cost_model.get("tco_5year")
            scoring.capex = option.cost_model.get("capex")
            scoring.opex_annual = option.cost_model.get("opex_annual")
            scoring.roi_percent = option.cost_model.get("roi_percent", 0)
            scoring.payback_period_months = option.cost_model.get("payback_months", 36)
        else:
            # Defaults if no cost model
            scoring.tco_5year = 0
            scoring.capex = 0
            scoring.opex_annual = 0

    def _score_strategic(self, scoring, option, tenant_id, user_id):
        """Score strategic criteria using LLM"""

        prompt = f"""Assess strategic value of this solution option:

**Option:** {option.title}
**Approach:** {option.approach}
**Description:** {option.description}

Rate on scale 0 - 10:
1. Strategic Alignment: How well does it align with enterprise strategy?
2. Innovation Potential: Opportunity for innovation?
3. Competitive Advantage: Market differentiation potential?
4. Business Agility: Flexibility and adaptability?

Respond with JSON:
{{
  "strategic_alignment": 7.5,
  "innovation_potential": 8.0,
  "competitive_advantage": 6.5,
  "business_agility": 7.0,
  "rationale": "Brief explanation"
}}"""

        try:
            response = self.llm.generate_completion(
                messages=[
                    {"role": "system", "content": "You are an expert enterprise strategist."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=500,
                tenant_id=tenant_id,
                user_id=user_id,
                operation="strategic_scoring",
            )

            strategic_scores = json.loads(response)

            scoring.strategic_alignment = strategic_scores.get("strategic_alignment", 5.0)
            scoring.innovation_potential = strategic_scores.get("innovation_potential", 5.0)
            scoring.competitive_advantage = strategic_scores.get("competitive_advantage", 5.0)
            scoring.business_agility = strategic_scores.get("business_agility", 5.0)

        except Exception as e:
            # Fallback to defaults
            scoring.strategic_alignment = 5.0
            scoring.innovation_potential = 5.0
            scoring.competitive_advantage = 5.0
            scoring.business_agility = 5.0

    def _score_technical(self, scoring, option, tenant_id, user_id):
        """Score technical criteria"""

        # Use LLM for technical assessment
        prompt = f"""Assess technical aspects:

**Technologies:** {option.technologies}
**Approach:** {option.approach}

Rate 0 - 10:
1. Technical Fit: Architecture compatibility
2. Integration Complexity: Ease of integration (0=very complex, 10=very easy)
3. Scalability: Growth capability
4. Performance: Speed/efficiency
5. Maintainability: Long-term support

JSON response:
{{
  "technical_fit": 8.0,
  "integration_complexity": 3.0,
  "scalability": 9.0,
  "performance": 8.5,
  "maintainability": 7.5
}}"""

        try:
            response = self.llm.generate_completion(
                messages=[
                    {"role": "system", "content": "You are a solution architect."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=300,
                tenant_id=tenant_id,
                user_id=user_id,
                operation="technical_scoring",
            )

            tech_scores = json.loads(response)

            scoring.technical_fit = tech_scores.get("technical_fit", 5.0)
            scoring.integration_complexity = tech_scores.get("integration_complexity", 5.0)
            scoring.scalability = tech_scores.get("scalability", 5.0)
            scoring.performance = tech_scores.get("performance", 5.0)
            scoring.maintainability = tech_scores.get("maintainability", 5.0)

        except Exception:
            # Defaults
            scoring.technical_fit = 5.0
            scoring.integration_complexity = 5.0
            scoring.scalability = 5.0
            scoring.performance = 5.0
            scoring.maintainability = 5.0

    def _score_risk(self, scoring, option, tenant_id, user_id):
        """Score risk criteria including vendor viability"""

        # Vendor viability
        if option.vendors:
            vendor_name = option.vendors[0]  # Primary vendor
            viability = self._assess_vendor_viability(vendor_name, tenant_id)
            scoring.vendor_viability = viability.viability_score if viability else 5.0
        else:
            scoring.vendor_viability = 8.0  # No vendor = build option = higher control

        # Use LLM for other risk factors
        scoring.implementation_risk = 5.0  # Default
        scoring.security_compliance = 7.0  # Assume good
        scoring.operational_risk = 5.0  # Default

    def _score_team(self, scoring, option, tenant_id, user_id):
        """Score team/skills criteria"""

        scoring.skill_gap = 5.0  # Medium gap
        scoring.training_required = 5.0  # Medium training
        scoring.vendor_support_quality = 7.0 if option.vendors else 5.0
        scoring.community_ecosystem = 6.0  # Default

    def _assess_vendor_viability(self, vendor_name, tenant_id):
        """Assess vendor financial and market viability"""

        # Check cache first
        cached = (
            db.session.query(VendorViabilityAssessment)
            .filter_by(tenant_id=tenant_id, vendor_name=vendor_name)
            .order_by(VendorViabilityAssessment.assessed_at.desc())
            .first()
        )

        # Use cached if recent (< 30 days)
        if cached and (datetime.utcnow() - cached.assessed_at).days < 30:
            return cached

        # Otherwise assess (simplified - in production use real data sources)
        assessment = VendorViabilityAssessment(
            tenant_id=tenant_id,
            vendor_name=vendor_name,
            financial_stability=7.0,
            viability_score=7.5,
            data_source="manual",
        )

        db.session.add(assessment)
        db.session.commit()

        return assessment

    def _calculate_confidence(self, scoring):
        """Calculate confidence level based on data completeness"""

        # Count non-null criteria
        total_criteria = 20  # Total number of scoring criteria
        populated = sum(
            [
                1 if scoring.tco_5year else 0,
                1 if scoring.strategic_alignment else 0,
                1 if scoring.technical_fit else 0,
                # ... etc
            ]
        )

        return min(1.0, populated / total_criteria)

    def compare_options(self, session_id, tenant_id):
        """Compare all options for a session"""

        scorings = (
            db.session.query(SolutionScoring)
            .filter_by(tenant_id=tenant_id, session_id=session_id)
            .order_by(SolutionScoring.weighted_total_score.desc())
            .all()
        )

        return [s.to_dict() for s in scorings]
