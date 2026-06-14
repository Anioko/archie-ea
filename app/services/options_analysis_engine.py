"""
Options Analysis Engine

Multi-criteria decision analysis for application rationalization options.
Evaluates migration, investment, retirement, and consolidation options
against configurable criteria (cost, risk, technical fit, strategic alignment).

Used by:
- Dashboard API: POST /dashboard/api/rationalization/options-analysis/<app_id>
- Enterprise API: POST /api/v2/enterprise/options-analysis
"""

import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_currency_symbol() -> str:
    """Get currency symbol from CurrencyConfig, with safe fallback."""
    try:
        from config import CurrencyConfig
        return CurrencyConfig.get_currency_config().get("symbol", "£")
    except Exception:
        return "£"


@dataclass
class AnalysisOption:
    """An option to be evaluated by the analysis engine."""

    id: str = ""
    name: str = ""
    vendor_id: Optional[str] = None
    product_id: Optional[str] = None
    description: str = ""
    technical_specs: Dict[str, Any] = field(default_factory=dict)
    cost_estimates: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Scored result for a single option."""

    option_id: str = ""
    option_name: str = ""
    overall_score: float = 0.0
    confidence_score: float = 0.0
    ranking: int = 0
    criteria_scores: Dict[str, float] = field(default_factory=dict)
    reasoning: str = ""
    recommendations: List[str] = field(default_factory=list)
    risks_identified: List[str] = field(default_factory=list)


# Criteria weights by TIME action context
_CRITERIA_WEIGHTS = {
    "MIGRATE": {
        "cost_efficiency": 0.20,
        "technical_fit": 0.30,
        "risk_level": 0.15,
        "strategic_alignment": 0.20,
        "implementation_ease": 0.15,
    },
    "INVEST": {
        "cost_efficiency": 0.15,
        "technical_fit": 0.20,
        "risk_level": 0.10,
        "strategic_alignment": 0.35,
        "implementation_ease": 0.20,
    },
    "TOLERATE": {
        "cost_efficiency": 0.35,
        "technical_fit": 0.15,
        "risk_level": 0.20,
        "strategic_alignment": 0.10,
        "implementation_ease": 0.20,
    },
    "ELIMINATE": {
        "cost_efficiency": 0.30,
        "technical_fit": 0.10,
        "risk_level": 0.25,
        "strategic_alignment": 0.10,
        "implementation_ease": 0.25,
    },
}

_DEFAULT_WEIGHTS = {
    "cost_efficiency": 0.25,
    "technical_fit": 0.25,
    "risk_level": 0.15,
    "strategic_alignment": 0.20,
    "implementation_ease": 0.15,
}


class OptionsAnalysisEngine:
    """
    Multi-criteria decision analysis engine for application options.

    Evaluates each option against 5 criteria dimensions, weighted by
    the TIME framework action context, and produces ranked results.

    Supports two calling patterns:
    - Dashboard API (async via run_async_safely): analyze_options(requirements=..., options=...)
    - Enterprise API (sync): analyze_options(scenario=..., options=..., criteria=...)
    """

    def analyze_options(
        self,
        requirements: Optional[Dict] = None,
        options: Optional[List] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        # Enterprise API signature
        scenario: Optional[str] = None,
        criteria: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Analyze options using multi-criteria decision analysis.

        This is a synchronous method. The dashboard API wraps it via run_async_safely()
        but the enterprise API calls it directly. Making it sync avoids coroutine issues.
        """
        analysis_id = str(uuid.uuid4())

        # Enterprise API calling pattern
        if scenario is not None:
            return self._analyze_enterprise(analysis_id, scenario, options or [], criteria or {})

        requirements = requirements or {}
        options = options or []

        if not options:
            return {"analysis_id": analysis_id, "results": [], "scenarios": []}

        time_action = requirements.get("time_action", "TOLERATE")
        weights = _CRITERIA_WEIGHTS.get(time_action, _DEFAULT_WEIGHTS)
        current_tech_score = requirements.get("current_technical_score", 50)
        current_cost_score = requirements.get("current_cost_score", 50)

        results = []
        for option in options:
            criteria_scores = self._score_option(option, requirements, time_action, current_tech_score, current_cost_score)
            overall = sum(
                criteria_scores.get(k, 50) * w for k, w in weights.items()
            )
            confidence = self._calculate_confidence(option, requirements)
            reasoning = self._generate_reasoning(option, criteria_scores, time_action)
            recommendations = self._generate_recommendations(option, criteria_scores, time_action)
            risks = self._identify_risks(option, criteria_scores)

            results.append(AnalysisResult(
                option_id=option.id,
                option_name=option.name,
                overall_score=round(overall, 1),
                confidence_score=round(confidence, 2),
                criteria_scores=criteria_scores,
                reasoning=reasoning,
                recommendations=recommendations,
                risks_identified=risks,
            ))

        # Rank by overall score descending
        results.sort(key=lambda r: r.overall_score, reverse=True)
        for i, r in enumerate(results):
            r.ranking = i + 1

        logger.info(
            "Options analysis completed: %s options evaluated, top=%s (%.1f)",
            len(results),
            results[0].option_name if results else "N/A",
            results[0].overall_score if results else 0,
        )

        return {
            "analysis_id": analysis_id,
            "results": [asdict(r) for r in results],
            "scenarios": [],
        }

    def _score_option(
        self, option: AnalysisOption, requirements: Dict, time_action: str,
        current_tech_score: float, current_cost_score: float,
    ) -> Dict[str, float]:
        """Score an option across all criteria dimensions (0-100 scale)."""
        costs = option.cost_estimates or {}
        specs = option.technical_specs or {}
        meta = option.metadata or {}

        return {
            "cost_efficiency": self._score_cost_efficiency(costs, current_cost_score, time_action),
            "technical_fit": self._score_technical_fit(specs, meta, current_tech_score, time_action),
            "risk_level": self._score_risk(specs, meta, time_action),
            "strategic_alignment": self._score_strategic_alignment(meta, requirements, time_action),
            "implementation_ease": self._score_implementation_ease(specs, costs, time_action),
        }

    def _score_cost_efficiency(self, costs: Dict, current_cost_score: float, time_action: str) -> float:
        """Score based on cost estimates relative to current state."""
        annual = costs.get("annual_cost", 0)
        migration = costs.get("migration_cost", 0) or costs.get("consolidation_cost", 0)
        savings = costs.get("annual_savings", 0)
        optimization = costs.get("optimization_cost", 0)
        decommission = costs.get("decommission_cost", 0)
        has_any_data = bool(annual or migration or savings or optimization or decommission)

        # Start lower when we have no cost data at all
        score = 45.0 if not has_any_data else 50.0

        # Factor in the app's current cost score — options for low-cost apps
        # don't need to save as much to be "efficient"
        if current_cost_score > 70:
            score += 5  # current app is already cost-efficient
        elif current_cost_score < 30:
            score -= 5  # current app is expensive, option needs to improve

        # Savings boost
        if savings > 0:
            score += min(30, savings / 5000)

        # Low annual cost is better
        if annual > 0:
            if annual < 80000:
                score += 15
            elif annual < 120000:
                score += 5
            else:
                score -= 10

        # High migration/transition costs are a negative
        total_upfront = migration + optimization + decommission
        if total_upfront > 0:
            if total_upfront < 50000:
                score += 5
            elif total_upfront > 150000:
                score -= 15
            else:
                score -= 5

        # ELIMINATE options with decommission cost get a boost
        if time_action == "ELIMINATE" and decommission > 0 and savings > decommission:
            score += 10

        return max(10, min(100, score))

    def _score_technical_fit(
        self, specs: Dict, meta: Dict, current_tech_score: float, time_action: str
    ) -> float:
        """Score based on technical specifications alignment."""
        deployment = specs.get("deployment", "").lower()
        scalability = specs.get("scalability", "").lower()
        maintenance = specs.get("maintenance", "").lower()
        has_any_data = bool(deployment or scalability or maintenance or meta)

        # Start lower when we have no tech data
        score = 40.0 if not has_any_data else 50.0

        # Factor in app's current tech health — if current tech is poor,
        # options that improve it should score higher
        if current_tech_score < 30:
            # App has poor tech health; options with cloud/modern deployment get extra boost
            if deployment in ("cloud", "hybrid"):
                score += 5

        # Cloud deployment is generally favorable for MIGRATE
        if deployment == "cloud":
            score += 20 if time_action == "MIGRATE" else 10
        elif deployment == "hybrid":
            score += 10
        elif deployment == "current":
            score += 5 if time_action in ("TOLERATE", "INVEST") else -5

        # Scalability
        if scalability == "high":
            score += 15
        elif scalability == "improved":
            score += 10
        elif scalability == "medium":
            score += 5

        # Maintenance burden
        if maintenance == "vendor-managed":
            score += 10
        elif maintenance == "optimized":
            score += 8
        elif maintenance == "minimal":
            score += 5
        elif maintenance == "internal":
            score -= 5

        # Metadata bonuses
        if meta.get("reduces_tech_debt"):
            score += 10
        if meta.get("improves_scalability"):
            score += 5

        return max(10, min(100, score))

    def _score_risk(self, specs: Dict, meta: Dict, time_action: str) -> float:
        """Score risk level (higher = lower risk = better)."""
        deployment = specs.get("deployment", "").lower()
        has_any_data = bool(deployment or specs.get("migration_complexity") or meta)

        # Start lower when we have no risk-relevant data (unknown = uncertain)
        score = 45.0 if not has_any_data else 55.0

        if meta.get("low_risk") or meta.get("stable"):
            score += 20

        if meta.get("data_migration_required"):
            score -= 15

        complexity = specs.get("migration_complexity", "").lower()
        if complexity == "high":
            score -= 20
        elif complexity == "medium":
            score -= 10
        elif complexity == "low":
            score += 10

        # Cloud migration carries moderate risk
        if deployment == "cloud" and time_action == "MIGRATE":
            score -= 5
        # Keeping current deployment is lower risk
        if deployment in ("current", "existing"):
            score += 10

        if meta.get("gradual_transition"):
            score += 10
        if meta.get("preserves_customization"):
            score += 5

        return max(10, min(100, score))

    def _score_strategic_alignment(
        self, meta: Dict, requirements: Dict, time_action: str
    ) -> float:
        """Score strategic alignment with business objectives."""
        has_any_data = bool(meta)
        score = 40.0 if not has_any_data else 50.0
        criticality = requirements.get("business_criticality", "MEDIUM")

        if meta.get("business_growth") or meta.get("competitive_advantage"):
            score += 20
        if meta.get("cost_reduction"):
            score += 10 if criticality == "LOW" else 5
        if meta.get("reduces_portfolio"):
            score += 15

        # High criticality apps benefit more from investment
        if criticality == "HIGH" and time_action == "INVEST":
            score += 10
        elif criticality == "LOW" and time_action == "ELIMINATE":
            score += 10

        return max(10, min(100, score))

    def _score_implementation_ease(self, specs: Dict, costs: Dict, time_action: str) -> float:
        """Score ease of implementation (higher = easier)."""
        deployment = specs.get("deployment", "").lower()
        timeline = specs.get("timeline", "").lower()
        migration_cost = costs.get("migration_cost", 0) or costs.get("consolidation_cost", 0)
        has_any_data = bool(deployment or timeline or migration_cost)

        # Start lower when we have no implementation data
        score = 45.0 if not has_any_data else 55.0

        # Current deployment = easiest
        if deployment in ("current", "existing"):
            score += 15
        elif deployment == "hybrid":
            score += 5
        elif deployment == "cloud":
            score -= 5
        elif deployment == "none":
            score += 10  # decommission is straightforward

        # Timeline hints
        if "6-12" in timeline:
            score += 5
        elif "12" in timeline or "18" in timeline:
            score -= 10

        # Cost as proxy for complexity
        if migration_cost > 150000:
            score -= 15
        elif migration_cost > 80000:
            score -= 5
        elif migration_cost == 0 and has_any_data:
            score += 10

        return max(10, min(100, score))

    def _calculate_confidence(self, option: AnalysisOption, requirements: Dict) -> float:
        """
        Calculate confidence score (0.0-1.0) based on data richness.

        Checks not just presence but depth of data to differentiate between
        options with real cost numbers vs empty dicts.
        """
        score = 0.0
        max_score = 8.0

        # Cost data depth (0-2 points)
        cost_keys = len(option.cost_estimates) if option.cost_estimates else 0
        if cost_keys >= 2:
            score += 2.0
        elif cost_keys == 1:
            score += 1.0

        # Technical specs depth (0-2 points)
        spec_keys = len(option.technical_specs) if option.technical_specs else 0
        if spec_keys >= 2:
            score += 2.0
        elif spec_keys == 1:
            score += 1.0

        # Description (0-1 point)
        if option.description and len(option.description) > 10:
            score += 1.0

        # Metadata richness (0-1 point)
        meta_keys = len(option.metadata) if option.metadata else 0
        if meta_keys >= 1:
            score += 1.0

        # Requirements context (0-2 points)
        if requirements.get("current_technical_score"):
            score += 0.5
        if requirements.get("current_cost_score"):
            score += 0.5
        if requirements.get("business_criticality"):
            score += 0.5
        if requirements.get("time_action"):
            score += 0.5

        confidence = score / max_score
        return max(0.40, min(0.95, confidence))

    def _generate_reasoning(
        self, option: AnalysisOption, scores: Dict, time_action: str
    ) -> str:
        """Generate human-readable reasoning for the option's scores."""
        top_criteria = max(scores, key=scores.get)
        top_label = top_criteria.replace("_", " ")
        top_val = scores[top_criteria]

        weak_criteria = min(scores, key=scores.get)
        weak_label = weak_criteria.replace("_", " ")
        weak_val = scores[weak_criteria]

        parts = [f'"{option.name}" scores highest on {top_label} ({top_val:.0f}/100)']

        if weak_val < 40:
            parts.append(f"but has concerns in {weak_label} ({weak_val:.0f}/100)")

        action_context = {
            "MIGRATE": "Given the MIGRATE recommendation, platform transition options are weighted toward technical fit.",
            "INVEST": "Given the INVEST recommendation, strategic growth options are prioritized.",
            "TOLERATE": "Given the TOLERATE recommendation, cost-efficient maintenance options score best.",
            "ELIMINATE": "Given the ELIMINATE recommendation, options with clear savings and low complexity score best.",
        }
        parts.append(action_context.get(time_action, ""))

        return " ".join(parts)

    def _generate_recommendations(
        self, option: AnalysisOption, scores: Dict, time_action: str
    ) -> List[str]:
        """Generate actionable recommendations for the option."""
        recs = []

        if option.description:
            recs.append(option.description)

        if scores.get("cost_efficiency", 50) < 40:
            recs.append("Negotiate pricing or explore phased cost models to improve cost efficiency")
        if scores.get("technical_fit", 50) > 70:
            recs.append("Strong technical alignment; proceed with proof-of-concept evaluation")
        if scores.get("risk_level", 50) < 40:
            recs.append("High risk identified; develop detailed risk mitigation plan before proceeding")
        if scores.get("implementation_ease", 50) > 70:
            recs.append("Low implementation complexity; candidate for fast-track deployment")

        if time_action == "ELIMINATE" and option.metadata.get("data_migration_required"):
            recs.append("Plan data migration and archival strategy before decommission")
        if time_action == "MIGRATE" and option.metadata.get("reduces_tech_debt"):
            recs.append("Reduces technical debt; prioritize for next planning cycle")

        return recs if recs else [option.description or "Evaluate option in detail"]

    def _identify_risks(self, option: AnalysisOption, scores: Dict) -> List[str]:
        """Identify risks based on option characteristics and scores."""
        risks = []
        currency = _get_currency_symbol()

        if option.metadata.get("data_migration_required"):
            risks.append("Data migration required; risk of data loss or downtime")
        if scores.get("risk_level", 50) < 35:
            risks.append("High overall risk profile; requires executive approval")
        if scores.get("cost_efficiency", 50) < 35:
            risks.append("Cost efficiency below threshold; ROI may be negative in short term")
        if scores.get("implementation_ease", 50) < 35:
            risks.append("Complex implementation; schedule overruns likely")

        migration_cost = option.cost_estimates.get("migration_cost", 0)
        if migration_cost > 150000:
            risks.append(f"High upfront investment ({currency}{migration_cost:,.0f}); budget approval needed")

        return risks

    def _analyze_enterprise(
        self, analysis_id: str, scenario: str, options: list, criteria: Dict
    ) -> Dict[str, Any]:
        """
        Handle enterprise API calling pattern.

        Enterprise format uses raw dicts for options and explicit criteria weights.
        """
        results = []

        for i, opt in enumerate(options):
            if isinstance(opt, dict):
                opt_id = opt.get("id", f"opt-{i}")
                opt_name = opt.get("name", f"Option {i + 1}")
                opt_values = opt.get("values", {})
            else:
                opt_id = getattr(opt, "id", f"opt-{i}")
                opt_name = getattr(opt, "name", f"Option {i + 1}")
                opt_values = {}

            # Score against each criterion
            criteria_scores = {}
            weighted_total = 0.0
            total_weight = 0.0

            for criterion_name, criterion_config in criteria.items():
                weight = criterion_config.get("weight", 0.25)
                direction = criterion_config.get("direction", "maximize")
                raw_value = opt_values.get(criterion_name, 50)

                # Normalize: 0-100 scale, higher is always better
                if direction == "minimize":
                    normalized = max(10, 100 - float(raw_value))
                else:
                    normalized = max(10, min(100, float(raw_value)))

                criteria_scores[criterion_name] = round(normalized, 1)
                weighted_total += normalized * weight
                total_weight += weight

            overall = weighted_total / total_weight if total_weight > 0 else 50

            results.append({
                "option_id": opt_id,
                "option_name": opt_name,
                "overall_score": round(overall, 1),
                "confidence_score": 0.75,
                "criteria_scores": criteria_scores,
                "reasoning": f"Multi-criteria analysis for scenario: {scenario}",
                "recommendations": [f"Evaluate {opt_name} against scenario requirements"],
                "risks_identified": [],
            })

        results.sort(key=lambda r: r["overall_score"], reverse=True)
        for i, r in enumerate(results):
            r["ranking"] = i + 1

        return {"analysis_id": analysis_id, "results": results, "scenarios": []}


def get_options_analysis_engine() -> OptionsAnalysisEngine:
    """Factory function returning an OptionsAnalysisEngine instance."""
    return OptionsAnalysisEngine()
