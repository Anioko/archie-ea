"""
Options Analysis Service for Course of Action Determination

Analyzes requirements and capabilities to recommend:
- Buy (Commercial Off-The-Shelf / SaaS)
- Build (Custom Development)
- Reuse (Extend Existing Systems)
- Partner (Outsource / Co-develop)
- Hybrid (Combination approach)
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.services.core.cache_service import cache_service
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class OptionsAnalysisService:
    """
    AI-driven options analysis to determine optimal Course of Action
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.cache = cache_service

    # ------------------------------------------------------------------
    # Database CRUD methods (used by vendor_analysis_routes.py)
    # ------------------------------------------------------------------

    def create_analysis(
        self,
        name,
        capability_id,
        vendor_org_ids=None,
        vendor_product_ids=None,
        created_by=None,
        criteria_weights=None,
        analysis_type="standard",
        tco_years=5,
        organization_size=None,
        industry_vertical=None,
        deployment_scale=None,
        user_count_estimate=None,
        integration_complexity=None,
    ):
        """
        Create an OptionsAnalysis record with VendorOption children.

        Returns the newly created OptionsAnalysis (flushed, not yet committed).
        The caller (route) is responsible for ``db.session.commit()``.
        """
        from app import db
        from app.models.vendor_analysis import OptionsAnalysis, VendorOption

        analysis = OptionsAnalysis(
            name=name,
            capability_id=capability_id,
            created_by_id=created_by.id if created_by else None,
            status="draft",
            analysis_type=analysis_type,
            tco_years=tco_years,
            organization_size=organization_size,
            industry_vertical=industry_vertical,
            deployment_scale=deployment_scale,
            user_count_estimate=user_count_estimate,
            integration_complexity=integration_complexity,
        )
        if criteria_weights:
            analysis.set_criteria_weights(criteria_weights)

        db.session.add(analysis)
        db.session.flush()  # assign analysis.id

        # Create a VendorOption for each vendor organisation
        for org_id in vendor_org_ids or []:
            try:
                from app.models.vendor.vendor_organization import VendorOrganization

                org = db.session.get(VendorOrganization, org_id)
                if org:
                    db.session.add(
                        VendorOption(
                            analysis_id=analysis.id,
                            vendor_organization_id=org_id,
                            vendor_name=org.name,
                            vendor_type="organization",
                        )
                    )
            except Exception:
                logger.debug("VendorOrganization %s skipped", org_id)

        # Create a VendorOption for each vendor product
        for prod_id in vendor_product_ids or []:
            try:
                from app.models.vendor.vendor_organization import VendorProduct

                prod = db.session.get(VendorProduct, prod_id)
                if prod:
                    db.session.add(
                        VendorOption(
                            analysis_id=analysis.id,
                            vendor_product_id=prod_id,
                            vendor_name=prod.name,
                            vendor_type="product",
                        )
                    )
            except Exception:
                logger.debug("VendorProduct %s skipped", prod_id)

        db.session.flush()
        analysis.total_vendors_analyzed = len(analysis.vendor_options)
        return analysis

    def run_analysis(self, analysis_id):
        """
        Score every VendorOption in an analysis, rank them, and mark completed.

        Three-phase approach:
          Phase 1 — Per-vendor scoring: enrich each vendor with real data from
                    VendorOrganization, VendorProduct, and VendorProductCapability.
          Phase 2 — Batch normalisation: cost scores are relative (cheapest = best),
                    so we normalise across all vendors after collecting raw data.
          Phase 3 — Weighted totals and ranking.

        The caller is responsible for ``db.session.commit()``.
        """
        from app import db
        from app.models.vendor_analysis import OptionsAnalysis

        analysis = db.session.get(OptionsAnalysis, analysis_id)
        if not analysis:
            raise ValueError(f"Analysis {analysis_id} not found")

        analysis.status = "running"
        analysis.started_at = datetime.utcnow()
        db.session.flush()

        weights = analysis.get_criteria_weights()
        required_cap_ids = self._collect_required_capability_ids(analysis)

        # Phase 1: per-vendor enrichment
        for vo in analysis.vendor_options:
            vo.analysis_status = "analyzing"
            vo.analysis_started_at = datetime.utcnow()
            self._score_vendor_option(vo, weights, required_cap_ids)

        # Phase 2: batch-normalise cost scores
        self._normalize_cost_scores(analysis.vendor_options)

        # Phase 3: weighted totals and ranking
        for vo in analysis.vendor_options:
            vo.calculate_total_score(weights)
            vo.analysis_status = "completed"
            vo.analysis_completed_at = datetime.utcnow()

        ranked = sorted(
            analysis.vendor_options, key=lambda v: v.total_score or 0, reverse=True
        )
        for rank, vo in enumerate(ranked, 1):
            vo.ranking = rank

        analysis.status = "completed"
        analysis.completed_at = datetime.utcnow()
        if analysis.started_at:
            analysis.execution_duration_seconds = int(
                (analysis.completed_at - analysis.started_at).total_seconds()
            )

        if ranked and ranked[0].total_score:
            analysis.recommendation_confidence = round(
                ranked[0].total_score / 100.0, 3
            )
        else:
            analysis.recommendation_confidence = 0.5

        db.session.flush()
        return analysis

    # ------------------------------------------------------------------
    # Scoring helpers (called by run_analysis)
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_required_capability_ids(analysis):
        """Gather the capability IDs that this analysis is evaluating against."""
        ids = []
        if analysis.capability_id:
            ids.append(analysis.capability_id)
        return ids

    @staticmethod
    def _score_vendor_option(vo, weights, required_cap_ids):
        """Enrich a single VendorOption with real data. None means no data available."""

        vo.capability_coverage_score = OptionsAnalysisService._score_capability_coverage(vo, required_cap_ids)

        vo.risk_score = OptionsAnalysisService._score_risk(vo)

        vo.strategic_fit_score = OptionsAnalysisService._score_strategic_fit(vo)

        impl = OptionsAnalysisService._score_implementation(vo, required_cap_ids)
        vo.implementation_score = impl or OptionsAnalysisService._score_implementation_from_vo(vo)

        # Cost: populate raw cost fields (score assigned in batch normalisation)
        OptionsAnalysisService._enrich_cost_data(vo)

    @staticmethod
    def _enrich_cost_data(vo):
        """Populate license/support/TCO sub-fields from VendorProduct pricing."""
        product = vo.vendor_product
        if not product and vo.vendor_organization:
            # Pick the first product with pricing data from this org
            for p in (vo.vendor_organization.products or []):
                if p.base_license_cost_annual:
                    product = p
                    break

        if not product or not product.base_license_cost_annual:
            return

        license_cost = float(product.base_license_cost_annual)
        vo.license_cost_annual = license_cost

        support_pct = product.support_cost_percentage if product.support_cost_percentage else 20.0
        vo.support_cost_annual = round(license_cost * (support_pct / 100.0), 2)

        impl_cost = float(product.implementation_cost_estimate) if product.implementation_cost_estimate else 0.0

        # TCO = (license + support) * years + implementation
        tco_years = 5
        if vo.analysis and hasattr(vo.analysis, "tco_years") and vo.analysis.tco_years:
            tco_years = vo.analysis.tco_years
        vo.tco_total = round(
            (license_cost + vo.support_cost_annual) * tco_years + impl_cost, 2
        )

    @staticmethod
    def _normalize_cost_scores(vendor_options):
        """Batch-normalise cost scores: cheapest vendor scores highest."""
        costs = [
            (vo, float(vo.license_cost_annual))
            for vo in vendor_options
            if vo.license_cost_annual
        ]
        if len(costs) >= 2:
            min_cost = min(c for _, c in costs)
            max_cost = max(c for _, c in costs)
            spread = max_cost - min_cost
            if spread > 0:
                for vo, cost in costs:
                    # Invert: cheapest = 95, most expensive = 25
                    vo.cost_score = round(25.0 + 70.0 * (1.0 - (cost - min_cost) / spread), 1)
            else:
                for vo, _ in costs:
                    vo.cost_score = 75.0  # identical pricing
        elif len(costs) == 1:
            costs[0][0].cost_score = 60.0  # data exists but no comparison

    @staticmethod
    def _score_capability_coverage(vo, required_cap_ids):
        """Score based on VendorProductCapability coverage data. Returns float or None."""
        if not required_cap_ids:
            return None

        from app import db
        from app.models.vendor.vendor_organization import VendorProductCapability

        product_ids = OptionsAnalysisService._get_product_ids_for_vo(vo)
        if not product_ids:
            return None

        caps = (
            db.session.query(VendorProductCapability)
            .filter(
                VendorProductCapability.vendor_product_id.in_(product_ids),
                VendorProductCapability.business_capability_id.in_(required_cap_ids),
            )
            .all()
        )
        if not caps:
            return None

        # Use coverage_percentage as primary metric, fall back to fit_score
        scores = []
        for c in caps:
            if c.coverage_percentage is not None:
                scores.append(float(c.coverage_percentage))
            elif c.fit_score is not None:
                scores.append(float(c.fit_score))

        if not scores:
            return None

        avg_score = sum(scores) / len(scores)

        # Also populate capability_match_percentage
        matched = len(caps)
        total = len(required_cap_ids)
        vo.capability_match_percentage = round((matched / total) * 100, 1) if total else 0

        return round(min(avg_score, 100.0), 1)

    @staticmethod
    def _score_risk(vo):
        """Score risk from VendorOption manual fields, then VendorOrganization. Returns float or None.

        Priority 1: VendorOption's own risk fields (1-10, 10=risky, inverted to score).
        Priority 2: VendorOrganization financial health and lock-in.
        Returns None if no data exists at all.
        """
        # Priority 1: VendorOption manual risk fields
        vo_risk_fields = {
            "vendor_lock_in_risk": 0.30,
            "market_position_risk": 0.25,
            "support_continuity_risk": 0.20,
            "technology_maturity_risk": 0.15,
            "compliance_risk": 0.10,
        }
        vo_parts = []
        for field, weight in vo_risk_fields.items():
            val = getattr(vo, field, None)
            if val is not None:
                # 1-10 where 10=risky → invert to score where 100=best
                vo_parts.append((max(100.0 - float(val) * 10.0, 0.0), weight))

        if vo_parts:
            total_weight = sum(w for _, w in vo_parts)
            return round(sum(s * w for s, w in vo_parts) / total_weight, 1)

        # Priority 2: VendorOrganization data
        org = vo.vendor_organization
        if not org:
            return None

        components = []

        if getattr(org, "financial_health_score", None):
            components.append(float(org.financial_health_score))

        lock_in = getattr(org, "vendor_lock_in_risk", None)
        if lock_in:
            # lock_in is 1-10 (higher = riskier), invert to score (higher = better)
            components.append(100.0 - float(lock_in) * 10.0)
            vo.vendor_lock_in_risk = int(lock_in)

        if not components:
            return None

        if len(components) == 2:
            # Blend: 60% financial health, 40% lock-in inverted
            return round(components[0] * 0.6 + components[1] * 0.4, 1)
        return round(components[0], 1)

    @staticmethod
    def _score_strategic_fit(vo):
        """Score strategic fit from VendorOption fields, then VendorOrganization. Returns float or None.

        Priority 1: VendorOption's own alignment fields (1-10 → 0-100).
        Priority 2: VendorOrganization readiness, innovation, product quality.
        Returns None if no data exists at all.
        """
        # Priority 1: VendorOption manual strategic fit fields
        vo_strat_fields = {
            "technology_alignment": 0.25,
            "roadmap_alignment": 0.25,
            "ecosystem_fit": 0.20,
            "future_proofing": 0.15,
            "vendor_relationship": 0.15,
        }
        vo_parts = []
        for field, weight in vo_strat_fields.items():
            val = getattr(vo, field, None)
            if val is not None:
                # 1-10 → scale to 0-100
                vo_parts.append((float(val) * 10.0, weight))

        if vo_parts:
            total_weight = sum(w for _, w in vo_parts)
            score = sum(s * w for s, w in vo_parts) / total_weight

            # Partnership bonus from org if available
            org = vo.vendor_organization
            if org:
                partnership = getattr(org, "partnership_level", None)
                if partnership == "strategic_partner":
                    score = min(score + 8, 100.0)
                elif partnership == "preferred":
                    score = min(score + 4, 100.0)

            return round(score, 1)

        # Priority 2: VendorOrganization data
        org = vo.vendor_organization
        if not org:
            return None

        parts = []  # (score, weight)

        if getattr(org, "enterprise_readiness_score", None):
            parts.append((float(org.enterprise_readiness_score), 0.4))

        if getattr(org, "innovation_score", None):
            parts.append((float(org.innovation_score), 0.2))

        # Product quality: avg of scalability/security/performance ratings (1-10 → 0-100)
        product = vo.vendor_product
        if not product and org.products:
            product = org.products[0] if org.products else None

        if product:
            ratings = []
            for attr in ("scalability_rating", "security_rating", "performance_rating"):
                val = getattr(product, attr, None)
                if val:
                    ratings.append(float(val) * 10.0)
            if ratings:
                parts.append((sum(ratings) / len(ratings), 0.2))

        if not parts:
            return None

        # Weighted average using only available components
        total_weight = sum(w for _, w in parts)
        score = sum(s * w for s, w in parts) / total_weight

        # Partnership bonus
        partnership = getattr(org, "partnership_level", None)
        if partnership == "strategic_partner":
            score = min(score + 8, 100.0)
        elif partnership == "preferred":
            score = min(score + 4, 100.0)

        return round(score, 1)

    @staticmethod
    def _score_implementation(vo, required_cap_ids):
        """Score implementation ease from VendorProductCapability complexity. Returns float or None."""
        if not required_cap_ids:
            return None

        from app import db
        from app.models.vendor.vendor_organization import VendorProductCapability

        product_ids = OptionsAnalysisService._get_product_ids_for_vo(vo)
        if not product_ids:
            return None

        caps = (
            db.session.query(VendorProductCapability)
            .filter(
                VendorProductCapability.vendor_product_id.in_(product_ids),
                VendorProductCapability.business_capability_id.in_(required_cap_ids),
            )
            .all()
        )

        complexities = [
            float(c.implementation_complexity)
            for c in caps
            if c.implementation_complexity is not None
        ]

        if complexities:
            avg = sum(complexities) / len(complexities)
            # Invert: lower complexity = higher score (1 → 90, 10 → 0)
            return round(max(100.0 - avg * 10.0, 0.0), 1)

        return None

    @staticmethod
    def _score_implementation_from_vo(vo):
        """Score implementation ease from VendorOption manual fields. Returns float or None.

        Inverted fields (1-10 where 10=bad → invert to score):
          implementation_complexity (w=0.25), integration_difficulty (w=0.20),
          data_migration_risk (w=0.15), change_management_impact (w=0.15),
          training_requirements (w=0.10).
        Direct field (1-10 where 10=good → scale to score):
          skill_availability (w=0.15).
        """
        # Fields where 10 = bad → invert
        inverted_fields = {
            "implementation_complexity": 0.25,
            "integration_difficulty": 0.20,
            "data_migration_risk": 0.15,
            "change_management_impact": 0.15,
            "training_requirements": 0.10,
        }
        # Fields where 10 = good → direct scale
        direct_fields = {
            "skill_availability": 0.15,
        }

        parts = []

        for field, weight in inverted_fields.items():
            val = getattr(vo, field, None)
            if val is not None:
                parts.append((max(100.0 - float(val) * 10.0, 0.0), weight))

        for field, weight in direct_fields.items():
            val = getattr(vo, field, None)
            if val is not None:
                parts.append((float(val) * 10.0, weight))

        if not parts:
            return None

        total_weight = sum(w for _, w in parts)
        return round(sum(s * w for s, w in parts) / total_weight, 1)

    @staticmethod
    def _get_product_ids_for_vo(vo):
        """Get all product IDs associated with this VendorOption."""
        ids = []
        if vo.vendor_product_id:
            ids.append(vo.vendor_product_id)
        if vo.vendor_organization and vo.vendor_organization.products:
            for p in vo.vendor_organization.products:
                if p.id not in ids:
                    ids.append(p.id)
        return ids

    def analyze_requirement_options(
        self, requirement: Dict, context: Optional[Dict] = None
    ) -> Dict:
        """
        Perform options analysis for a single requirement

        CACHED: Results cached for 24 hours to reduce LLM costs

        Args:
            requirement: Requirement element with name, description, type
            context: Optional organizational context (policies, constraints, existing systems)

        Returns:
            Options analysis with recommended Course of Action
        """

        # Check cache first (24 hour TTL)
        cache_key = self.cache._generate_cache_key(
            "options_analysis",
            requirement.get("name", ""),
            requirement.get("description", ""),
            context or {},
        )

        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.info(f"Using cached options analysis for: {requirement.get('name', '')}")
            return cached_result

        req_name = requirement.get("name", "")
        req_description = requirement.get("description", "")
        req_type = requirement.get("category", "Functional")

        # Build context string
        org_context = ""
        if context:
            org_context = f"""
**Organizational Context**:
- Build vs Buy Policy: {context.get('build_buy_policy', 'Not specified')}
- Cloud Strategy: {context.get('cloud_strategy', 'Not specified')}
- Budget Constraints: {context.get('budget', 'Not specified')}
- Time Constraints: {context.get('timeline', 'Not specified')}
- Existing Systems: {', '.join(context.get('existing_systems', []))}
"""

        prompt = f"""Perform a comprehensive OPTIONS ANALYSIS for this requirement to determine the optimal Course of Action.

**Requirement**: {req_name}
**Description**: {req_description}
**Type**: {req_type}

{org_context}

Analyze the following strategic options using multi-criteria decision analysis:

1. **BUY (COTS/SaaS)**
   - Commercial off-the-shelf solutions
   - SaaS platforms
   - Managed services

2. **BUILD (Custom Development)**
   - In-house development
   - Custom coding
   - Proprietary solutions

3. **REUSE (Extend Existing)**
   - Leverage existing internal systems
   - Extend current platforms
   - Configure existing tools

4. **PARTNER (Outsource/Co-develop)**
   - Outsource to specialist vendor
   - Co-development partnership
   - Managed service provider

5. **HYBRID**
   - Combination of above approaches
   - Buy core + customize
   - Build orchestration + buy components

For each viable option, evaluate:

**Strategic Fit**:
- Is this a core competency or commodity capability?
- Does it provide competitive differentiation?
- Strategic importance: High/Medium/Low

**Market Availability** (for Buy/Partner):
- Are there mature solutions available?
- Typical vendors/products
- Estimated licensing/subscription costs

**Development Feasibility** (for Build):
- Technical complexity: Low/Medium/High
- Estimated development effort (person-weeks)
- Required skills/technology stack

**Reuse Potential** (for Reuse):
- Likely existing systems that could be extended
- Integration complexity
- Customization required

**Decision Criteria Scoring** (0 - 100 scale):
- Strategic Importance (25%): Core competency value
- Time-to-Market (20%): Speed of delivery
- Total Cost (20%): TCO over 3 years
- Risk (15%): Technical, vendor, operational risk
- Capability Fit (20%): How well it meets requirements

Return ONLY valid JSON:
{{
  "requirement": "{req_name}",
  "options": [
    {{
      "course_of_action": "Buy|Build|Reuse|Partner|Hybrid",
      "approach_name": "Specific approach (e.g., 'Buy Salesforce', 'Build Custom Service')",
      "description": "Detailed description of this option",
      "rationale": "Why this option makes sense",
      "strategic_fit": "core|differentiator|commodity",
      "cost_estimate": "Low|Medium|High|Specific amount",
      "time_to_implement": "Days|Weeks|Months|Specific timeline",
      "risk_level": "Low|Medium|High",
      "pros": ["List of advantages"],
      "cons": ["List of disadvantages"],
      "scores": {{
        "strategic_importance": 0 - 100,
        "time_to_market": 0 - 100,
        "total_cost": 0 - 100,
        "risk": 0 - 100,
        "capability_fit": 0 - 100,
        "weighted_total": 0 - 100
      }}
    }}
  ],
  "recommended_option": {{
    "course_of_action": "Selected option",
    "approach_name": "Specific recommendation",
    "recommendation_confidence": "High|Medium|Low",
    "decision_rationale": ["Key factors driving this recommendation"],
    "dependencies": ["What needs to be in place"],
    "next_steps": ["Immediate actions to take"]
  }},
  "decision_matrix_summary": "Summary of how options were evaluated"
}}

Be specific and practical. Consider real-world constraints.
"""

        response = self.llm_service.generate_from_prompt(prompt)

        # Parse JSON
        try:
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_text = response[json_start:json_end].strip()
            elif "{" in response and "}" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_text = response[json_start:json_end].strip()
            else:
                json_text = response

            parsed = json.loads(json_text)

            # Cache the result (24 hour TTL)
            self.cache.set(cache_key, parsed, ttl=86400)
            logger.info(f"Cached options analysis for: {req_name}")

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Options analysis JSON parsing failed: {e}")
            error_result = {
                "requirement": req_name,
                "options": [],
                "recommended_option": {},
                "error": str(e),
            }
            # Don't cache errors
            return error_result

    def generate_course_of_action_elements(self, options_analysis: Dict) -> List[Dict]:
        """
        Convert options analysis into ArchiMate Course of Action elements

        Args:
            options_analysis: Output from analyze_requirement_options

        Returns:
            List of ArchiMate CourseOfAction elements
        """

        course_of_actions = []

        # Create Course of Action for recommended option
        recommended = options_analysis.get("recommended_option", {})

        if recommended:
            coa = {
                "name": recommended.get("approach_name", "Unknown Approach"),
                "type": "CourseOfAction",
                "layer": "strategy",
                "description": f"{recommended.get('decision_rationale', ['No rationale provided'])[0] if recommended.get('decision_rationale') else 'Strategic initiative'}",
                "properties": {
                    "option_type": recommended.get("course_of_action", ""),
                    "confidence": recommended.get("recommendation_confidence", "Medium"),
                    "source_requirement": options_analysis.get("requirement", ""),
                },
            }
            course_of_actions.append(coa)

        # Optionally create alternative Course of Action elements for viable options
        for option in options_analysis.get("options", []):
            if option.get("scores", {}).get("weighted_total", 0) > 60:  # High-scoring alternatives
                if option.get("approach_name") != recommended.get("approach_name"):
                    coa = {
                        "name": f"{option.get('approach_name', '')} (Alternative)",
                        "type": "CourseOfAction",
                        "layer": "strategy",
                        "description": option.get("description", ""),
                        "properties": {
                            "option_type": option.get("course_of_action", ""),
                            "status": "alternative",
                            "weighted_score": option.get("scores", {}).get("weighted_total", 0),
                        },
                    }
                    course_of_actions.append(coa)

        return course_of_actions

    def batch_analyze_requirements(
        self, requirements: List[Dict], context: Optional[Dict] = None
    ) -> Dict:
        """
        Perform options analysis for multiple requirements

        Args:
            requirements: List of requirement elements
            context: Organizational context

        Returns:
            Dictionary with options analyses and generated Course of Action elements
        """

        logger.info(f"\n[OPTIONS ANALYSIS] Analyzing {len(requirements)} requirements...")

        all_analyses = []
        all_course_of_actions = []

        for i, req in enumerate(requirements):
            logger.info(
                f"  [{i + 1}/{len(requirements)}] Analyzing: {req.get('name', 'Unknown')[:60]}..."
            )

            analysis = self.analyze_requirement_options(req, context)
            all_analyses.append(analysis)

            # Generate Course of Action elements
            coa_elements = self.generate_course_of_action_elements(analysis)
            all_course_of_actions.extend(coa_elements)

            logger.info(
                f"    Recommended: {analysis.get('recommended_option', {}).get('course_of_action', 'Unknown')}"
            )

        logger.info(f"\n[RESULT] Generated {len(all_course_of_actions)} Course of Action elements")

        return {
            "analyses": all_analyses,
            "course_of_action_elements": all_course_of_actions,
            "summary": {
                "total_requirements_analyzed": len(requirements),
                "buy_recommendations": sum(
                    1
                    for a in all_analyses
                    if "Buy" in a.get("recommended_option", {}).get("course_of_action", "")
                ),
                "build_recommendations": sum(
                    1
                    for a in all_analyses
                    if "Build" in a.get("recommended_option", {}).get("course_of_action", "")
                ),
                "reuse_recommendations": sum(
                    1
                    for a in all_analyses
                    if "Reuse" in a.get("recommended_option", {}).get("course_of_action", "")
                ),
                "partner_recommendations": sum(
                    1
                    for a in all_analyses
                    if "Partner" in a.get("recommended_option", {}).get("course_of_action", "")
                ),
                "hybrid_recommendations": sum(
                    1
                    for a in all_analyses
                    if "Hybrid" in a.get("recommended_option", {}).get("course_of_action", "")
                ),
            },
        }

    def create_decision_matrix_visualization(self, options_analysis: Dict) -> str:
        """
        Create a text-based decision matrix visualization

        Args:
            options_analysis: Output from analyze_requirement_options

        Returns:
            Formatted decision matrix as string
        """

        requirement = options_analysis.get("requirement", "Unknown")
        options = options_analysis.get("options", [])

        output = f"\n{'='*80}\n"
        output += f"DECISION MATRIX: {requirement}\n"
        output += f"{'='*80}\n\n"

        if not options:
            output += "No options available\n"
            return output

        # Header
        output += f"{'Option':<30} {'Strategic':<10} {'Time':<10} {'Cost':<10} {'Risk':<10} {'Fit':<10} {'TOTAL':<10}\n"
        output += f"{'-'*30} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}\n"

        # Rows
        for option in options:
            name = option.get("approach_name", "Unknown")[:28]
            scores = option.get("scores", {})

            strategic = scores.get("strategic_importance", 0)
            time = scores.get("time_to_market", 0)
            cost = scores.get("total_cost", 0)
            risk = scores.get("risk", 0)
            fit = scores.get("capability_fit", 0)
            total = scores.get("weighted_total", 0)

            output += f"{name:<30} {strategic:<10.0f} {time:<10.0f} {cost:<10.0f} {risk:<10.0f} {fit:<10.0f} {total:<10.0f}\n"

        # Recommendation
        recommended = options_analysis.get("recommended_option", {})
        if recommended:
            output += f"\n{'='*80}\n"
            output += f"RECOMMENDED: {recommended.get('approach_name', 'Unknown')}\n"
            output += f"Confidence: {recommended.get('recommendation_confidence', 'Unknown')}\n"
            output += f"\nRationale:\n"
            for reason in recommended.get("decision_rationale", []):
                output += f"  - {reason}\n"

        return output
