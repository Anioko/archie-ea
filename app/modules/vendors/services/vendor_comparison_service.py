"""
-> app.modules.vendors.services.analysis_service

Vendor Comparison Matrix Generator Service

Provides side-by-side vendor comparison with weighted criteria scoring,
sensitivity analysis, and export capabilities for Enterprise Architects.

Features:
- 5 - dimensional scoring matrix generation
- Configurable weighted criteria
- Sensitivity analysis on weight changes
- Export to JSON/CSV formats
- Gap analysis overlay on comparison
- AI-powered recommendation summaries

Usage:
    service = VendorComparisonService()

    # Generate comparison matrix
    matrix = service.generate_comparison_matrix(analysis_id=123)

    # Run sensitivity analysis
    sensitivity = service.sensitivity_analysis(analysis_id=123, criteria='cost', range=0.1)

    # Export comparison
    csv_data = service.export_comparison(analysis_id=123, format='csv')
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
from sqlalchemy import and_, func, or_

from app import db
from app.models.vendor_analysis import (
    AnalysisRecommendation,
    OptionsAnalysis,
    VendorComparisonCriteria,
    VendorOption,
)

logger = logging.getLogger(__name__)


class VendorComparisonService:
    """
    Service for generating vendor comparison matrices with multi-criteria analysis.

    Supports:
    - 5 - dimensional scoring (Cost, Capability, Risk, Strategic Fit, Implementation)
    - Weighted scoring with customizable criteria
    - Sensitivity analysis for decision robustness
    - Export to multiple formats
    """

    DEFAULT_CRITERIA = {
        "cost": {
            "name": "Total Cost",
            "weight": 0.25,
            "description": "Total cost of ownership including licensing, support, and infrastructure",
            "higher_is_better": False,
        },
        "capability_coverage": {
            "name": "Capability Coverage",
            "weight": 0.25,
            "description": "How well the vendor covers required business capabilities",
            "higher_is_better": True,
        },
        "risk": {
            "name": "Risk Score",
            "weight": 0.20,
            "description": "Overall risk assessment including vendor lock-in and market position",
            "higher_is_better": False,
        },
        "strategic_fit": {
            "name": "Strategic Fit",
            "weight": 0.15,
            "description": "Alignment with technology strategy and enterprise roadmap",
            "higher_is_better": True,
        },
        "implementation": {
            "name": "Implementation",
            "weight": 0.15,
            "description": "Ease of implementation and time-to-value",
            "higher_is_better": True,
        },
    }

    def __init__(self):
        """Initialize the Vendor Comparison Service."""
        self.app = current_app._get_current_object() if current_app else None

    def _validate_weights(self, weights: Dict[str, float]) -> tuple[bool, str]:
        """
        Validate criteria weights.

        Args:
            weights: Dictionary of criteria weights

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not weights:
            return False, "No criteria weights provided"

        # Check all required criteria are present
        required_criteria = set(self.DEFAULT_CRITERIA.keys())
        provided_criteria = set(weights.keys())

        if not required_criteria.issubset(provided_criteria):
            missing = required_criteria - provided_criteria
            return False, f"Missing required criteria: {', '.join(missing)}"

        # Check all weights are numeric and in valid range (0-1)
        for criterion, weight in weights.items():
            if not isinstance(weight, (int, float)):
                return False, f"Weight for '{criterion}' must be numeric"
            if weight < 0 or weight > 1:
                return False, f"Weight for '{criterion}' must be between 0 and 1"

        # Check weights sum to 1.0 (with floating point tolerance)
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:  # Allow 1% tolerance
            return False, f"Weights must sum to 100% (current: {round(total * 100)}%)"

        return True, ""

    def generate_comparison_matrix(
        self, analysis_id: int, include_gaps: bool = True, include_recommendations: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive vendor comparison matrix.

        Args:
            analysis_id: ID of the OptionsAnalysis
            include_gaps: Include capability gap analysis
            include_recommendations: Include AI recommendations

        Returns:
            Dictionary containing the comparison matrix and metadata
        """
        logger.info(f"Generating comparison matrix for analysis {analysis_id}")

        try:
            analysis = db.session.get(OptionsAnalysis, analysis_id)
            if not analysis:
                return {"error": f"Analysis {analysis_id} not found"}

            # Get criteria weights
            weights = analysis.get_criteria_weights()

            # Validate weights
            is_valid, error_msg = self._validate_weights(weights)
            if not is_valid:
                logger.error(f"Invalid criteria weights for analysis {analysis_id}: {error_msg}")
                return {"error": f"Invalid criteria weights: {error_msg}"}

            # Build vendor comparison data
            vendors = []
            for vendor_opt in analysis.vendor_options:
                try:
                    vendor_data = self._extract_vendor_scores(vendor_opt)
                    vendor_data["weighted_total"] = self._calculate_weighted_score(vendor_data, weights)
                    vendors.append(vendor_data)
                except Exception as e:
                    logger.error(f"Error extracting scores for vendor option {vendor_opt.id}: {e}")
                    continue

            # Sort by weighted total (descending)
            vendors.sort(key=lambda v: v["weighted_total"], reverse=True)

            # Assign rankings
            for idx, vendor in enumerate(vendors, 1):
                vendor["ranking"] = idx

            # Build matrix structure
            matrix = {
                "analysis_id": analysis_id,
                "analysis_name": analysis.name,
                "capability": analysis.capability.name if analysis.capability else None,
                "status": analysis.status,
                "generated_at": datetime.utcnow().isoformat(),
                "criteria": self._get_criteria_config(weights),
                "vendors": vendors,
                "summary": self._generate_summary(vendors, analysis),
            }

            if include_gaps:
                matrix["gap_analysis"] = self._generate_gap_overlay(vendors)

            if include_recommendations:
                matrix["recommendations"] = self._get_recommendations(analysis)

            return matrix

        except Exception as e:
            logger.error(f"Error generating comparison matrix for analysis {analysis_id}: {e}")
            return {"error": f"Failed to generate comparison matrix: {str(e)}"}

    def _safe_json_loads(self, json_str: Optional[str], default: Any = None) -> Any:
        """Safely parse JSON string with error handling.

        Args:
            json_str: JSON string to parse
            default: Default value to return if parsing fails

        Returns:
            Parsed JSON or default value if parsing fails
        """
        if not json_str:
            return default
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse JSON: {e}. Using default: {default}")
            return default

    def _extract_vendor_scores(self, vendor_opt: VendorOption) -> Dict[str, Any]:
        """Extract and normalize vendor scores."""
        # Get vendor name from appropriate source
        vendor_name = "Unknown Vendor"
        if vendor_opt.vendor_product:
            vendor_name = vendor_opt.vendor_product.product_name
        elif vendor_opt.vendor_organization:
            vendor_name = vendor_opt.vendor_organization.name
        elif vendor_opt.technology_stack:
            vendor_name = vendor_opt.technology_stack.name

        return {
            "vendor_id": vendor_opt.id,
            "vendor_name": vendor_name,
            "vendor_type": vendor_opt.vendor_type,
            "analysis_status": vendor_opt.analysis_status,
            "scores": {
                "cost": {
                    "score": vendor_opt.cost_score or 0,
                    "raw_value": float(vendor_opt.tco_total) if vendor_opt.tco_total else None,
                    "details": {
                        "license_annual": float(vendor_opt.license_cost_annual)
                        if vendor_opt.license_cost_annual
                        else None,
                        "support_annual": float(vendor_opt.support_cost_annual)
                        if vendor_opt.support_cost_annual
                        else None,
                        "infrastructure_monthly": float(vendor_opt.infrastructure_cost_monthly)
                        if vendor_opt.infrastructure_cost_monthly
                        else None,
                        "training": float(vendor_opt.training_cost_estimate)
                        if vendor_opt.training_cost_estimate
                        else None,
                    },
                },
                "capability_coverage": {
                    "score": vendor_opt.capability_coverage_score or 0,
                    "raw_value": vendor_opt.capability_match_percentage,
                    "details": {
                        "match_percentage": vendor_opt.capability_match_percentage,
                        "gaps": self._safe_json_loads(vendor_opt.capability_gaps, []),
                        "supported": self._safe_json_loads(vendor_opt.supported_capabilities, []),
                        "missing": self._safe_json_loads(vendor_opt.missing_capabilities, []),
                    },
                },
                "risk": {
                    "score": vendor_opt.risk_score or 0,
                    "raw_value": self._calculate_avg_risk(vendor_opt),
                    "details": {
                        "vendor_lock_in": vendor_opt.vendor_lock_in_risk,
                        "market_position": vendor_opt.market_position_risk,
                        "support_continuity": vendor_opt.support_continuity_risk,
                        "technology_maturity": vendor_opt.technology_maturity_risk,
                        "compliance": vendor_opt.compliance_risk,
                        "mitigations": self._safe_json_loads(vendor_opt.risk_mitigation_strategies, []),
                    },
                },
                "strategic_fit": {
                    "score": vendor_opt.strategic_fit_score or 0,
                    "raw_value": self._calculate_avg_strategic_fit(vendor_opt),
                    "details": {
                        "technology_alignment": vendor_opt.technology_alignment,
                        "roadmap_alignment": vendor_opt.roadmap_alignment,
                        "vendor_relationship": vendor_opt.vendor_relationship,
                        "future_proofing": vendor_opt.future_proofing,
                        "ecosystem_fit": vendor_opt.ecosystem_fit,
                    },
                },
                "implementation": {
                    "score": vendor_opt.implementation_score or 0,
                    "raw_value": vendor_opt.implementation_complexity,
                    "details": {
                        "complexity": vendor_opt.implementation_complexity,
                        "estimated_weeks": vendor_opt.estimated_implementation_weeks,
                        "resources": self._safe_json_loads(vendor_opt.resource_requirements, {}),
                    },
                },
            },
            "total_score": vendor_opt.total_score or 0,
        }

    def _calculate_weighted_score(self, vendor_data: Dict, weights: Dict[str, float]) -> float:
        """Calculate weighted total score based on criteria weights."""
        total = 0
        for criterion, weight in weights.items():
            score = vendor_data["scores"].get(criterion, {}).get("score", 0)
            total += score * weight
        return round(total, 2)

    def _calculate_avg_risk(self, vendor_opt: VendorOption) -> Optional[float]:
        """Calculate average risk score."""
        risks = [
            vendor_opt.vendor_lock_in_risk,
            vendor_opt.market_position_risk,
            vendor_opt.support_continuity_risk,
            vendor_opt.technology_maturity_risk,
            vendor_opt.compliance_risk,
        ]
        valid_risks = [r for r in risks if r is not None]
        if valid_risks:
            return sum(valid_risks) / len(valid_risks)
        return None

    def _calculate_avg_strategic_fit(self, vendor_opt: VendorOption) -> Optional[float]:
        """Calculate average strategic fit score."""
        fits = [
            vendor_opt.technology_alignment,
            vendor_opt.roadmap_alignment,
            vendor_opt.vendor_relationship,
            vendor_opt.future_proofing,
            vendor_opt.ecosystem_fit,
        ]
        valid_fits = [f for f in fits if f is not None]
        if valid_fits:
            return sum(valid_fits) / len(valid_fits)
        return None

    def _get_criteria_config(self, weights: Dict[str, float]) -> List[Dict[str, Any]]:
        """Get criteria configuration with weights."""
        criteria = []
        for key, default in self.DEFAULT_CRITERIA.items():
            criteria.append(
                {
                    "key": key,
                    "name": default["name"],
                    "weight": weights.get(key, default["weight"]),
                    "weight_percent": round(weights.get(key, default["weight"]) * 100),
                    "description": default["description"],
                    "higher_is_better": default["higher_is_better"],
                }
            )
        return criteria

    def _generate_summary(self, vendors: List[Dict], analysis: OptionsAnalysis) -> Dict[str, Any]:
        """Generate comparison summary statistics."""
        if not vendors:
            return {"message": "No vendors to compare"}

        winner = vendors[0] if vendors else None
        scores = [v["weighted_total"] for v in vendors]

        summary = {
            "vendor_count": len(vendors),
            "recommended_vendor": winner["vendor_name"] if winner else None,
            "recommended_score": winner["weighted_total"] if winner else 0,
            "score_statistics": {
                "max": max(scores) if scores else 0,
                "min": min(scores) if scores else 0,
                "avg": round(sum(scores) / len(scores), 2) if scores else 0,
                "spread": round(max(scores) - min(scores), 2) if len(scores) > 1 else 0,
            },
            "decision_clarity": self._calculate_decision_clarity(scores),
        }

        # Add runner-up if exists
        if len(vendors) > 1:
            summary["runner_up"] = {
                "vendor_name": vendors[1]["vendor_name"],
                "score": vendors[1]["weighted_total"],
                "gap_from_winner": round(
                    winner["weighted_total"] - vendors[1]["weighted_total"], 2
                ),
            }

        return summary

    def _calculate_decision_clarity(self, scores: List[float]) -> Dict[str, Any]:
        """
        Calculate how clear the decision is based on score distribution.
        High clarity = large gap between winner and others.
        """
        if len(scores) < 2:
            return {"clarity": "N/A", "message": "Need at least 2 vendors to compare"}

        sorted_scores = sorted(scores, reverse=True)
        gap_to_second = sorted_scores[0] - sorted_scores[1]
        score_range = sorted_scores[0] - sorted_scores[-1]

        # Calculate relative gap
        relative_gap = gap_to_second / sorted_scores[0] if sorted_scores[0] > 0 else 0

        if relative_gap > 0.15:
            clarity = "high"
            message = "Clear winner with significant score advantage"
        elif relative_gap > 0.08:
            clarity = "medium"
            message = "Moderate differentiation between top vendors"
        else:
            clarity = "low"
            message = "Close competition - consider additional criteria"

        return {
            "clarity": clarity,
            "message": message,
            "gap_to_second": round(gap_to_second, 2),
            "gap_percentage": round(relative_gap * 100, 1),
        }

    def _generate_gap_overlay(self, vendors: List[Dict]) -> Dict[str, Any]:
        """Generate capability gap analysis overlay."""
        all_gaps = []
        vendor_gaps = {}

        for vendor in vendors:
            gaps = (
                vendor["scores"].get("capability_coverage", {}).get("details", {}).get("gaps", [])
            )
            vendor_gaps[vendor["vendor_name"]] = len(gaps)
            all_gaps.extend(gaps)

        # Identify common gaps (appear in multiple vendors)
        gap_descriptions = [g.get("gap", "") for g in all_gaps if isinstance(g, dict)]
        common_gaps = [g for g in set(gap_descriptions) if gap_descriptions.count(g) > 1]

        return {
            "total_unique_gaps": len(set(gap_descriptions)),
            "common_gaps": common_gaps,
            "gaps_by_vendor": vendor_gaps,
            "vendor_with_fewest_gaps": min(vendor_gaps, key=vendor_gaps.get)
            if vendor_gaps
            else None,
        }

    def _get_recommendations(self, analysis: OptionsAnalysis) -> List[Dict[str, Any]]:
        """Get AI recommendations for the analysis."""
        recommendations = []

        for rec in analysis.recommendations:
            recommendations.append(
                {
                    "recommended_vendor_id": rec.recommended_vendor_option_id,
                    "rationale": rec.rationale,
                    "confidence_score": rec.confidence_score,
                    "key_strengths": self._safe_json_loads(rec.key_strengths, []),
                    "key_concerns": self._safe_json_loads(rec.key_concerns, []),
                    "estimated_timeline_weeks": rec.estimated_timeline_weeks,
                    "estimated_total_cost": float(rec.estimated_total_cost)
                    if rec.estimated_total_cost
                    else None,
                }
            )

        return recommendations

    def sensitivity_analysis(
        self, analysis_id: int, criteria: str, variation_range: float = 0.1
    ) -> Dict[str, Any]:
        """
        Perform sensitivity analysis on criteria weights.

        Tests how ranking changes when a specific criteria weight varies.

        Args:
            analysis_id: ID of the OptionsAnalysis
            criteria: Criteria key to vary (e.g., 'cost', 'risk')
            variation_range: How much to vary the weight (±range)

        Returns:
            Dictionary with sensitivity analysis results
        """
        logger.info(
            f"Running sensitivity analysis for analysis {analysis_id}, criteria: {criteria}"
        )

        analysis = db.session.get(OptionsAnalysis, analysis_id)
        if not analysis:
            return {"error": f"Analysis {analysis_id} not found"}

        base_weights = analysis.get_criteria_weights()
        if criteria not in base_weights:
            return {"error": f"Unknown criteria: {criteria}"}

        base_weight = base_weights[criteria]
        results = []

        # Test different weight values
        test_weights = [
            base_weight - variation_range,
            base_weight - (variation_range / 2),
            base_weight,
            base_weight + (variation_range / 2),
            base_weight + variation_range,
        ]

        for test_weight in test_weights:
            # Ensure weight stays in valid range
            test_weight = max(0.05, min(0.50, test_weight))

            # Recalculate other weights proportionally
            adjusted_weights = self._adjust_weights(base_weights, criteria, test_weight)

            # Calculate rankings with adjusted weights
            rankings = self._calculate_rankings_with_weights(analysis, adjusted_weights)

            results.append(
                {
                    "weight_value": round(test_weight, 3),
                    "weight_percent": round(test_weight * 100, 1),
                    "rankings": rankings,
                    "winner": rankings[0]["vendor_name"] if rankings else None,
                }
            )

        # Analyze stability
        winners = [r["winner"] for r in results]
        unique_winners = set(winners)

        return {
            "analysis_id": analysis_id,
            "criteria_analyzed": criteria,
            "base_weight": round(base_weight, 3),
            "variation_range": variation_range,
            "results": results,
            "stability": {
                "is_stable": len(unique_winners) == 1,
                "unique_winners": list(unique_winners),
                "switches": len(unique_winners) - 1,
                "message": "Winner is stable across weight variations"
                if len(unique_winners) == 1
                else f"Winner changes {len(unique_winners) - 1} time(s) across variations",
            },
        }

    def _adjust_weights(
        self, base_weights: Dict[str, float], changed_criteria: str, new_weight: float
    ) -> Dict[str, float]:
        """Adjust other weights proportionally when one changes."""
        adjusted = base_weights.copy()
        old_weight = adjusted[changed_criteria]
        weight_change = new_weight - old_weight

        # Distribute the change proportionally among other criteria
        other_criteria = [k for k in adjusted.keys() if k != changed_criteria]
        total_other = sum(adjusted[k] for k in other_criteria)

        if total_other > 0:
            for crit in other_criteria:
                proportion = adjusted[crit] / total_other
                adjusted[crit] -= weight_change * proportion
                adjusted[crit] = max(0.05, adjusted[crit])  # Minimum weight

        adjusted[changed_criteria] = new_weight

        # Normalize to sum to 1.0
        total = sum(adjusted.values())
        if total > 0:
            for k in adjusted:
                adjusted[k] = adjusted[k] / total

        return adjusted

    def _calculate_rankings_with_weights(
        self, analysis: OptionsAnalysis, weights: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Calculate vendor rankings with specified weights."""
        rankings = []

        for vendor_opt in analysis.vendor_options:
            vendor_data = self._extract_vendor_scores(vendor_opt)
            weighted_total = self._calculate_weighted_score(vendor_data, weights)
            rankings.append(
                {
                    "vendor_id": vendor_opt.id,
                    "vendor_name": vendor_data["vendor_name"],
                    "weighted_total": weighted_total,
                }
            )

        # Sort by weighted total
        rankings.sort(key=lambda r: r["weighted_total"], reverse=True)

        # Add rankings
        for idx, r in enumerate(rankings, 1):
            r["rank"] = idx

        return rankings

    def compare_scenarios(
        self, analysis_id: int, scenario_weights: List[Dict[str, Dict[str, float]]]
    ) -> Dict[str, Any]:
        """
        Compare multiple weighting scenarios.

        Args:
            analysis_id: ID of the OptionsAnalysis
            scenario_weights: List of scenarios, each with name and weights dict

        Returns:
            Comparison of rankings across scenarios
        """
        analysis = db.session.get(OptionsAnalysis, analysis_id)
        if not analysis:
            return {"error": f"Analysis {analysis_id} not found"}

        scenario_results = []

        for scenario in scenario_weights:
            name = scenario.get("name", "Unnamed")
            weights = scenario.get("weights", {})

            rankings = self._calculate_rankings_with_weights(analysis, weights)

            scenario_results.append(
                {
                    "scenario_name": name,
                    "weights": weights,
                    "winner": rankings[0]["vendor_name"] if rankings else None,
                    "winner_score": rankings[0]["weighted_total"] if rankings else 0,
                    "full_rankings": rankings,
                }
            )

        # Check for consensus
        winners = [s["winner"] for s in scenario_results]
        unique_winners = set(winners)

        return {
            "analysis_id": analysis_id,
            "scenarios": scenario_results,
            "consensus": {
                "has_consensus": len(unique_winners) == 1,
                "winning_vendors": list(unique_winners),
                "consensus_message": "All scenarios agree on winner"
                if len(unique_winners) == 1
                else f"{len(unique_winners)} different winners across scenarios",
            },
        }

    def export_comparison(self, analysis_id: int, format: str = "json") -> Any:
        """
        Export comparison matrix in specified format.

        Args:
            analysis_id: ID of the OptionsAnalysis
            format: Export format ('json', 'csv')

        Returns:
            Formatted comparison data
        """
        matrix = self.generate_comparison_matrix(analysis_id)

        if format == "csv":
            return self._export_to_csv(matrix)
        else:
            return matrix

    def _export_to_csv(self, matrix: Dict[str, Any]) -> str:
        """Export matrix to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row
        header = ["Vendor", "Ranking", "Weighted Total"]
        criteria = matrix.get("criteria", [])
        for crit in criteria:
            header.append(f"{crit['name']} Score")
            header.append(f"{crit['name']} Weight %")

        writer.writerow(header)

        # Data rows
        for vendor in matrix.get("vendors", []):
            row = [
                vendor["vendor_name"],
                vendor["ranking"],
                vendor["weighted_total"],
            ]
            for crit in criteria:
                score = vendor["scores"].get(crit["key"], {}).get("score", 0)
                row.append(score)
                row.append(crit["weight_percent"])
            writer.writerow(row)

        return output.getvalue()

    def get_predefined_scenarios(self) -> List[Dict[str, Any]]:
        """Get predefined weighting scenarios for common use cases."""
        return [
            {
                "name": "Cost-Optimized",
                "description": "Prioritizes lowest total cost of ownership",
                "weights": {
                    "cost": 0.40,
                    "capability_coverage": 0.20,
                    "risk": 0.15,
                    "strategic_fit": 0.10,
                    "implementation": 0.15,
                },
            },
            {
                "name": "Best-of-Breed",
                "description": "Prioritizes capability coverage and strategic fit",
                "weights": {
                    "cost": 0.15,
                    "capability_coverage": 0.35,
                    "risk": 0.15,
                    "strategic_fit": 0.25,
                    "implementation": 0.10,
                },
            },
            {
                "name": "Risk-Averse",
                "description": "Prioritizes low risk and proven vendors",
                "weights": {
                    "cost": 0.20,
                    "capability_coverage": 0.20,
                    "risk": 0.35,
                    "strategic_fit": 0.15,
                    "implementation": 0.10,
                },
            },
            {
                "name": "Quick-Win",
                "description": "Prioritizes fast implementation and time-to-value",
                "weights": {
                    "cost": 0.20,
                    "capability_coverage": 0.20,
                    "risk": 0.15,
                    "strategic_fit": 0.10,
                    "implementation": 0.35,
                },
            },
            {
                "name": "Balanced",
                "description": "Equal weighting across all dimensions",
                "weights": {
                    "cost": 0.20,
                    "capability_coverage": 0.20,
                    "risk": 0.20,
                    "strategic_fit": 0.20,
                    "implementation": 0.20,
                },
            },
        ]
