"""
ImpactAnalysisService - Architecture Change Impact Analysis

Analyzes impact of changes across architecture elements with full dependency tracking.

Single persistence store: ImpactAnalysisResult (table impact_analysis_results).
All analysis results are stored via this ORM model only.
"""
from typing import Dict, List

from app import db
from .decorators import transactional


def _acting_user_id():
    """Id of the signed-in user running the analysis, or None outside a request.

    Stored results belong to the organisation of this user, so a result with no
    user is visible to nobody.
    """
    from flask import has_request_context
    from flask_login import current_user

    if not has_request_context() or not current_user.is_authenticated:
        return None
    return getattr(current_user, "id", None)


class ImpactAnalysisService:
    """Service for analyzing impact of architecture changes with transitive dependencies."""

    @classmethod
    def analyze_change_impact(
        cls, element_id: int, change_type: str = "MODIFY", scenario: str = None,
        cursor: int = None, page_size: int = None,
    ) -> Dict:
        """
        Analyze complete impact of changing an element.

        Args:
            element_id: Element being changed
            change_type: MODIFY, RETIRE, REPLACE
            scenario: Optional API scenario name (e.g. retirement, modification) for persistence.
            cursor: Optional pagination cursor (0-based index into the full result set).
            page_size: Optional page size for pagination.

        Returns:
            Full impact analysis with risk assessment
        """
        # Repointed to the canonical cross_layer_impact walk (max_depth=3, 3 hops from seed).
        from app.modules.intelligence.services.query_service import IntelligenceQueryService

        result = IntelligenceQueryService.cross_layer_impact(
            element_id,
            include_derived=False,
            max_depth=3,
            direction="downstream",
            with_owner=True,
            cursor=cursor,
            page_size=page_size,
        )
        rows = result.get("rows") or []
        elements = result.get("elements") or {}

        def _row_to_dep(row):
            el = elements.get(str(row["element_id"]), {})
            return {
                "id": row["element_id"],
                "name": el.get("name"),
                "type": el.get("type"),
                "level": row["relation"]["depth"],
                "dependency_level": "medium",
                "app_name": None,
                "criticality": None,
                "tco": 0.0,
                "owner": row.get("owner"),
                "health": row.get("health"),
            }

        all_deps = [_row_to_dep(r) for r in rows]
        direct_deps = [d for d in all_deps if d["level"] == 1]
        indirect_deps = [d for d in all_deps if d["level"] > 1]

        # Severity-weighted risk: critical elements count 5x, high 3x, medium 2x, low/unknown 1x
        _dep_weights = {"critical": 5, "high": 3, "medium": 2, "low": 1}
        total_affected = len(direct_deps) + len(indirect_deps)
        weighted_score = sum(
            _dep_weights.get((d.get("dependency_level") or "low").lower(), 1)
            for d in all_deps
        )
        if weighted_score > 40:
            risk_level = "CRITICAL"
        elif weighted_score > 20:
            risk_level = "HIGH"
        elif weighted_score > 5:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Compute real financial exposure from linked application TCO. No
        # invented fallback (CLAUDE.md "never invent data") — a per-element
        # dollar guess is indistinguishable from a measured figure to the
        # architect reading it. None -> the template renders "not costed".
        real_tco = sum(d.get("tco", 0) for d in all_deps)
        estimated_financial_risk = real_tco if real_tco > 0 else None

        # Store in impact_analysis_results (ORM model - table exists)
        analysis_id = None
        try:
            from app.models.traceability import ImpactAnalysisResult
            import json as _json
            record = ImpactAnalysisResult(
                analysis_type="change_impact",
                trigger_element_type=change_type,
                trigger_element_id=element_id,
                scenario=scenario,
                impacted_elements=_json.dumps([d["id"] for d in all_deps]),
                overall_severity=risk_level.lower(),
                affected_applications_count=sum(1 for d in all_deps if d.get("app_name")),
                created_by_id=_acting_user_id(),
            )
            db.session.add(record)
            db.session.commit()
            analysis_id = record.id
        except Exception:
            db.session.rollback()

        return {
            "element_id": element_id,
            "change_type": change_type,
            "direct_dependencies": direct_deps,
            "indirect_dependencies": indirect_deps,
            "total_affected": total_affected,
            "weighted_score": weighted_score,
            "risk_level": risk_level,
            "estimated_financial_risk": estimated_financial_risk,
            "analysis_id": analysis_id,
            "total": result.get("total"),
            "next_cursor": result.get("next_cursor"),
        }

    @classmethod
    @transactional
    def analyze_portfolio_impact(cls, change_scenarios: List[Dict]) -> Dict:
        """
        Analyze impact of multiple changes across the portfolio.

        Args:
            change_scenarios: List of {'element_id': int, 'change_type': str}

        Returns:
            Portfolio-wide impact analysis
        """
        portfolio_impact = []

        for scenario in change_scenarios:
            impact = cls.analyze_change_impact(
                scenario["element_id"], scenario.get("change_type", "MODIFY")
            )
            portfolio_impact.append(impact)

        # Calculate portfolio metrics
        total_affected = sum(imp["total_affected"] for imp in portfolio_impact)
        critical_count = len([imp for imp in portfolio_impact if imp["risk_level"] == "CRITICAL"])
        high_count = len([imp for imp in portfolio_impact if imp["risk_level"] == "HIGH"])

        return {
            "change_scenarios": change_scenarios,
            "individual_impacts": portfolio_impact,
            "portfolio_metrics": {
                "total_affected_elements": total_affected,
                "critical_impacts": critical_count,
                "high_impacts": high_count,
                "overall_risk": "CRITICAL"
                if critical_count > 2
                else "HIGH"
                if high_count > 3
                else "MEDIUM"
                if (critical_count > 0 or high_count > 0)
                else "LOW",
            },
        }

    @classmethod
    def check_solution_vs_principles(cls, solution_id: int) -> Dict:
        """ENH-021: Check a solution against all active architectural principles.

        Returns:
            {
                "solution_id": int,
                "compliant": bool,
                "violations": [{"principle_id": int, "principle_name": str, "reason": str}],
                "checked_at": str (ISO 8601),
            }
        """
        from datetime import datetime as _dt

        violations = []

        try:
            from app.models.solution_models import Solution
            from app.models.motivation_extended import Principle

            solution = db.session.get(Solution, solution_id)
            if not solution:
                return {"error": "Solution not found", "solution_id": solution_id}

            # Load all mandatory/advisory active principles
            principles = Principle.query.filter(
                Principle.enforcement_status != "retired"
            ).all()

            if not principles:
                return {
                    "solution_id": solution_id,
                    "compliant": True,
                    "violations": [],
                    "warnings": ["No active principles found to check against."],
                    "checked_at": _dt.utcnow().isoformat(),
                }

            # Rule-based checks against solution fields
            for principle in principles:
                reason = cls._evaluate_principle(solution, principle)
                if reason:
                    violations.append({
                        "principle_id": principle.id,
                        "principle_name": principle.name,
                        "enforcement_level": getattr(principle, "enforcement_level", "advisory"),
                        "reason": reason,
                    })

        except Exception as exc:
            return {
                "solution_id": solution_id,
                "compliant": False,
                "violations": [],
                "error": str(exc),
                "checked_at": _dt.utcnow().isoformat(),
            }

        # Only mandatory violations count as non-compliant
        mandatory_violations = [
            v for v in violations if v.get("enforcement_level") == "mandatory"
        ]

        return {
            "solution_id": solution_id,
            "compliant": len(mandatory_violations) == 0,
            "violations": violations,
            "checked_at": _dt.utcnow().isoformat(),
        }

    @staticmethod
    def _evaluate_principle(solution, principle) -> str:
        """Return a violation reason string, or empty string if compliant."""
        name_lower = (principle.name or "").lower()
        (principle.statement or "").lower()

        # Security principle: solution must have a security_lead defined
        if "security" in name_lower and not solution.security_lead:
            return (
                f"Principle '{principle.name}' requires a security lead to be assigned. "
                "Set solution.security_lead."
            )

        # Data protection principle: must have data_protection_officer
        if "data protection" in name_lower and not solution.data_protection_officer:
            return (
                f"Principle '{principle.name}' requires a Data Protection Officer. "
                "Set solution.data_protection_officer."
            )

        # Business value: solution must have business_value
        if "business value" in name_lower and not solution.business_value:
            return (
                f"Principle '{principle.name}' requires business_value to be documented."
            )

        # Owner accountability: must have solution_owner
        if "accountability" in name_lower or "ownership" in name_lower:
            if not solution.solution_owner:
                return (
                    f"Principle '{principle.name}' requires solution_owner to be assigned."
                )

        # No violations detected
        return ""
