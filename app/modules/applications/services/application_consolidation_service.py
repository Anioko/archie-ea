"""

AI-Powered Application Consolidation Service

Analyzes application portfolio to identify duplicates, redundancy, and consolidation
opportunities using AI. Provides cost-benefit analysis and implementation recommendations.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_

from app import db
from app.models.application_capability import ApplicationCapabilityMapping
from app.models.application_consolidation import (
    ApplicationConsolidationRecommendation,
    ApplicationDuplicationReport,
    ApplicationSimilarityAnalysis,
)
from app.models.application_layer import ApplicationComponent
from app.models.business_capabilities import BusinessCapability
from app.models.cost_intelligence import CapabilityCostAllocation
from app.services.decorators import transactional
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ApplicationConsolidationService:
    """
    AI-powered application consolidation intelligence service.

    Key capabilities:
    1. Detect duplicate/similar applications across portfolio
    2. Calculate similarity scores across multiple dimensions
    3. Estimate cost savings from consolidation
    4. Assess migration complexity and risks
    5. Generate actionable recommendations with business case
    6. Track consolidation progress over time
    """

    def __init__(self):
        self.llm_service = LLMService()

    @transactional
    def analyze_portfolio_for_duplicates(
        self, min_similarity_threshold: int = 40, force_reanalysis: bool = False
    ) -> Dict:
        """
        Scan entire application portfolio for duplicates.

        Args:
            min_similarity_threshold: Minimum similarity score to flag (0 - 100)
            force_reanalysis: Re-analyze even if recent analysis exists

        Returns:
            Dict with analysis summary and duplicate pairs found
        """
        apps = ApplicationComponent.query.filter(
            ApplicationComponent.lifecycle_status.in_(["ACTIVE", "PHASING_IN"])
        ).all()

        total_apps = len(apps)
        pairs_analyzed = 0
        duplicates_found = []

        for i, app1 in enumerate(apps):
            for app2 in apps[i + 1 :]:
                query_filter = or_(
                    and_(
                        ApplicationSimilarityAnalysis.app_1_id == app1.id,
                        ApplicationSimilarityAnalysis.app_2_id == app2.id,
                    ),
                    and_(
                        ApplicationSimilarityAnalysis.app_1_id == app2.id,
                        ApplicationSimilarityAnalysis.app_2_id == app1.id,
                    ),
                )

                if not force_reanalysis:
                    existing = ApplicationSimilarityAnalysis.query.filter(
                        query_filter,
                        ApplicationSimilarityAnalysis.analysis_date
                        >= datetime.utcnow() - timedelta(days=30),
                    ).first()

                    if existing:
                        if existing.overall_similarity_score >= min_similarity_threshold:
                            duplicates_found.append(existing)
                        continue

                similarity = self.calculate_similarity_score(app1.id, app2.id)
                pairs_analyzed += 1

                if similarity and similarity.overall_similarity_score >= min_similarity_threshold:
                    duplicates_found.append(similarity)

        return {
            "total_applications": total_apps,
            "pairs_analyzed": pairs_analyzed,
            "duplicates_found": len(duplicates_found),
            "duplicate_pairs": duplicates_found,
            "analysis_date": datetime.utcnow().isoformat(),
        }

    @transactional
    def calculate_similarity_score(
        self, app1_id: int, app2_id: int
    ) -> Optional[ApplicationSimilarityAnalysis]:
        """
        Calculate multi-dimensional similarity between two applications.

        Analyzes:
        - Capability overlap (business functions)
        - Technology similarity (stack, languages)
        - Functional similarity (features, services)
        - Business domain match

        Returns:
            ApplicationSimilarityAnalysis object with scores
        """
        try:
            app1 = db.session.get(ApplicationComponent, app1_id)
            app2 = db.session.get(ApplicationComponent, app2_id)

            if not app1 or not app2:
                logger.error(f"Invalid application IDs: {app1_id}, {app2_id}")
                return None

            analysis = ApplicationSimilarityAnalysis(
                app_1_id=app1_id, app_2_id=app2_id, analysis_date=datetime.utcnow()
            )

            # Calculate dimension scores
            cap_score, shared_caps = self._analyze_capability_overlap(app1, app2)
            analysis.capability_overlap_score = cap_score
            analysis.shared_capabilities = json.dumps(shared_caps)

            tech_score, shared_tech = self._analyze_technology_similarity(app1, app2)
            analysis.technology_similarity_score = tech_score
            analysis.shared_technologies = json.dumps(shared_tech)

            domain_score = self._analyze_business_domain(app1, app2)
            analysis.business_domain_match = domain_score

            # Use AI for functional similarity
            ai_analysis = self._ai_analyze_functional_similarity(app1, app2)
            analysis.functional_similarity_score = ai_analysis.get("functional_score", 0)
            analysis.data_similarity_score = ai_analysis.get("data_score", 0)
            analysis.analyzed_by_ai_model = ai_analysis.get("model_used")
            analysis.reasoning = ai_analysis.get("reasoning")
            analysis.confidence_score = ai_analysis.get("confidence", 0.5)

            # Calculate overall similarity
            analysis.overall_similarity_score = self._calculate_overall_score(
                cap_score,
                tech_score,
                domain_score,
                ai_analysis.get("functional_score", 0),
                ai_analysis.get("data_score", 0),
            )

            # Generate consolidation recommendation
            self._generate_consolidation_recommendation(analysis, app1, app2, ai_analysis)

            # Estimate cost savings
            analysis.estimated_cost_savings = self._estimate_basic_savings(app1, app2)

            db.session.add(analysis)
            db.session.flush()

            return analysis

        except Exception as e:
            logger.error(
                f"Error calculating similarity for apps {app1_id}, {app2_id}: {e}", exc_info=True
            )
            return None

    def _analyze_capability_overlap(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> Tuple[int, List[str]]:
        """Calculate percentage of shared business capabilities"""
        caps1 = set(
            [
                m.capability_id
                for m in ApplicationCapabilityMapping.query.filter_by(
                    application_component_id=app1.id
                ).all()
            ]
        )
        caps2 = set(
            [
                m.capability_id
                for m in ApplicationCapabilityMapping.query.filter_by(
                    application_component_id=app2.id
                ).all()
            ]
        )

        if not caps1 or not caps2:
            return 0, []

        shared = caps1.intersection(caps2)
        union = caps1.union(caps2)

        overlap_percentage = int((len(shared) / len(union)) * 100) if union else 0

        shared_names = []
        for cap_id in shared:
            capability = db.session.get(BusinessCapability, cap_id)
            if capability:
                shared_names.append(capability.name)

        return overlap_percentage, shared_names

    def _analyze_technology_similarity(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> Tuple[int, List[str]]:
        """Calculate technology stack similarity"""
        shared_tech = []
        similarity_points = 0
        max_points = 0

        if app1.technology_stack and app2.technology_stack:
            tech1 = set([t.strip().lower() for t in app1.technology_stack.split(",")])
            tech2 = set([t.strip().lower() for t in app2.technology_stack.split(",")])
            shared_tech.extend(tech1.intersection(tech2))
            similarity_points += len(tech1.intersection(tech2)) * 10
            max_points += max(len(tech1), len(tech2)) * 10

        score = int((similarity_points / max_points) * 100) if max_points > 0 else 0
        return score, shared_tech

    def _analyze_business_domain(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> int:
        """Check if apps serve same business domain"""
        if not app1.business_domain or not app2.business_domain:
            return 0

        if app1.business_domain.lower() == app2.business_domain.lower():
            return 100

        domain1_words = set(app1.business_domain.lower().split())
        domain2_words = set(app2.business_domain.lower().split())

        if domain1_words.intersection(domain2_words):
            return 50

        return 0

    def _ai_analyze_functional_similarity(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> Dict:
        """Use AI to analyze functional and data similarity"""
        prompt = f"""Analyze these two applications for similarity:

Application 1: {app1.name}
- Description: {app1.description or 'N/A'}
- Type: {app1.component_type or 'N/A'}
- Domain: {app1.business_domain or 'N/A'}

Application 2: {app2.name}
- Description: {app2.description or 'N/A'}
- Type: {app2.component_type or 'N/A'}
- Domain: {app2.business_domain or 'N/A'}

Analyze:
1. Functional similarity (do they provide similar features/services?) - score 0 - 100
2. Data similarity (do they work with similar data models/entities?) - score 0 - 100
3. Are they potential duplicates or could they be consolidated?

Respond in JSON format:
{{
    "functional_score": <0 - 100>,
    "data_score": <0 - 100>,
    "are_duplicates": <true/false>,
    "consolidation_feasibility": "<easy/moderate/difficult/not_recommended>",
    "reasoning": "<brief explanation>",
    "confidence": <0.0 - 1.0>
}}"""

        try:
            response = self.llm_service.generate_from_prompt(prompt)
            match = re.search(r"\{[\s\S]*\}", response, re.DOTALL)
            payload = match.group(0) if match else response
            parsed = json.loads(payload)
            parsed["model_used"] = "llm_service"
            return parsed
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {
                "functional_score": 30,
                "data_score": 30,
                "are_duplicates": False,
                "consolidation_feasibility": "moderate",
                "reasoning": f"AI analysis failed: {str(e)}. Using conservative estimates.",
                "confidence": 0.3,
                "model_used": "fallback",
            }

    def _calculate_overall_score(
        self,
        cap_score: int,
        tech_score: int,
        domain_score: int,
        functional_score: int,
        data_score: int,
    ) -> int:
        """Calculate weighted overall similarity score"""
        weights = {
            "capability": 0.30,
            "functional": 0.25,
            "technology": 0.15,
            "data": 0.15,
            "domain": 0.15,
        }

        overall = (
            cap_score * weights["capability"]
            + functional_score * weights["functional"]
            + tech_score * weights["technology"]
            + data_score * weights["data"]
            + domain_score * weights["domain"]
        )

        return int(overall)

    def _generate_consolidation_recommendation(
        self,
        analysis: ApplicationSimilarityAnalysis,
        app1: ApplicationComponent,
        app2: ApplicationComponent,
        ai_analysis: Dict,
    ):
        """Generate consolidation recommendation based on similarity"""
        score = analysis.overall_similarity_score

        if score >= 70:
            analysis.consolidation_opportunity = "high"
            analysis.consolidation_complexity = "moderate"
        elif score >= 50:
            analysis.consolidation_opportunity = "medium"
            analysis.consolidation_complexity = "complex"
        elif score >= 30:
            analysis.consolidation_opportunity = "low"
            analysis.consolidation_complexity = "critical"
        else:
            analysis.consolidation_opportunity = "none"
            analysis.consolidation_complexity = "not_applicable"
            analysis.recommended_action = "keep_both"
            return

        # Determine survivor app
        app1_score = 10 if app1.lifecycle_status == "ACTIVE" else 0
        app2_score = 10 if app2.lifecycle_status == "ACTIVE" else 0

        if app1_score > app2_score:
            analysis.recommended_survivor = app1.id
            analysis.recommended_action = "retire_app2"
        elif app2_score > app1_score:
            analysis.recommended_survivor = app2.id
            analysis.recommended_action = "retire_app1"
        else:
            analysis.recommended_survivor = app1.id
            analysis.recommended_action = "merge"

        analysis.integration_changes_required = True
        analysis.data_migration_required = True
        analysis.user_migration_required = True

    def _estimate_basic_savings(
        self, app1: ApplicationComponent, app2: ApplicationComponent
    ) -> Decimal:
        """Estimate potential annual cost savings from consolidation"""
        savings = Decimal("0.00")

        if hasattr(app1, "license_cost_annual") and app1.license_cost_annual:
            savings += Decimal(str(app1.license_cost_annual))
        elif hasattr(app2, "license_cost_annual") and app2.license_cost_annual:
            savings += Decimal(str(app2.license_cost_annual))

        return savings

    def generate_consolidation_recommendations(
        self, min_similarity: int = 60, max_recommendations: int = 20
    ) -> List[ApplicationConsolidationRecommendation]:
        """
        Generate formal consolidation recommendations from similarity analyses.

        Args:
            min_similarity: Minimum similarity score to consider
            max_recommendations: Maximum number of recommendations to generate

        Returns:
            List of ApplicationConsolidationRecommendation objects
        """
        similar_pairs = (
            ApplicationSimilarityAnalysis.query.filter(
                ApplicationSimilarityAnalysis.overall_similarity_score >= min_similarity,
                ApplicationSimilarityAnalysis.consolidation_opportunity.in_(["high", "medium"]),
            )
            .order_by(ApplicationSimilarityAnalysis.overall_similarity_score.desc())
            .limit(max_recommendations)
            .all()
        )

        recommendations = []

        for analysis in similar_pairs:
            existing = ApplicationConsolidationRecommendation.query.filter(
                or_(
                    and_(
                        ApplicationConsolidationRecommendation.primary_app_id == analysis.app_1_id,
                        ApplicationConsolidationRecommendation.redundant_app_ids.contains(
                            str(analysis.app_2_id)
                        ),
                    ),
                    and_(
                        ApplicationConsolidationRecommendation.primary_app_id == analysis.app_2_id,
                        ApplicationConsolidationRecommendation.redundant_app_ids.contains(
                            str(analysis.app_1_id)
                        ),
                    ),
                )
            ).first()

            if not existing:
                recommendation = self._create_recommendation_from_analysis(analysis)
                if recommendation:
                    recommendations.append(recommendation)

        return recommendations

    @transactional
    def _create_recommendation_from_analysis(
        self, analysis: ApplicationSimilarityAnalysis
    ) -> Optional[ApplicationConsolidationRecommendation]:
        """Create detailed recommendation from similarity analysis"""
        try:
            app1 = db.session.get(ApplicationComponent, analysis.app_1_id)
            app2 = db.session.get(ApplicationComponent, analysis.app_2_id)

            if not app1 or not app2:
                return None

            if analysis.recommended_survivor == app1.id:
                primary_app = app1
                redundant_apps = [app2.id]
            else:
                primary_app = app2
                redundant_apps = [app1.id]

            rec_code = f"CONS-{datetime.utcnow().year}-{ApplicationConsolidationRecommendation.query.count() + 1:03d}"

            recommendation = ApplicationConsolidationRecommendation(
                recommendation_name=f"Consolidate {app1.name} and {app2.name}",
                recommendation_code=rec_code,
                description=f"High similarity detected ({analysis.overall_similarity_score}%). Consolidation opportunity identified.",
                consolidation_type="merge" if analysis.recommended_action == "merge" else "retire",
                primary_app_id=primary_app.id,
                redundant_app_ids=json.dumps(redundant_apps),
                total_apps_in_group=2,
            )

            recommendation.duplicate_capabilities = analysis.shared_capabilities
            recommendation.capability_coverage = analysis.capability_overlap_score
            recommendation.estimated_annual_savings = analysis.estimated_cost_savings or Decimal(
                "0.00"
            )
            recommendation.migration_complexity = analysis.consolidation_complexity
            recommendation.business_risk = (
                "medium" if analysis.overall_similarity_score > 70 else "high"
            )
            recommendation.technical_risk = (
                "low" if analysis.technology_similarity_score > 60 else "medium"
            )
            recommendation.generated_by_ai = True
            recommendation.ai_model_used = analysis.analyzed_by_ai_model
            recommendation.ai_confidence_score = analysis.confidence_score
            recommendation.ai_reasoning = analysis.reasoning
            recommendation.status = "proposed"
            recommendation.proposed_date = datetime.utcnow()
            recommendation.priority = "medium"

            db.session.add(recommendation)
            db.session.flush()

            return recommendation

        except Exception as e:
            logger.error(f"Error creating recommendation: {e}", exc_info=True)
            return None

    def get_consolidation_opportunities(self, limit: int = 10) -> List[Dict]:
        """Get top consolidation opportunities for dashboard display"""
        try:
            recommendations = (
                ApplicationConsolidationRecommendation.query.filter_by(status="proposed")
                .order_by(ApplicationConsolidationRecommendation.estimated_annual_savings.desc())
                .limit(limit)
                .all()
            )

            results = []
            for rec in recommendations:
                primary_app = db.session.get(ApplicationComponent, rec.primary_app_id)
                results.append(
                    {
                        "id": rec.id,
                        "code": rec.recommendation_code,
                        "name": rec.recommendation_name,
                        "primary_app": primary_app.name if primary_app else "Unknown",
                        "type": rec.consolidation_type,
                        "savings": float(rec.estimated_annual_savings)
                        if rec.estimated_annual_savings
                        else 0,
                        "complexity": rec.migration_complexity,
                        "priority": rec.priority,
                        "confidence": rec.ai_confidence_score,
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error getting consolidation opportunities: {e}", exc_info=True)
            return []
