"""Governance Gate Service — hard enforcement of completeness thresholds.

Checks whether a solution passes a named governance gate (e.g. "arb_submission")
by verifying motivation-layer entity counts, decision counts, and risk mitigations.

Part of GOV-03.  Entity counts are queried directly from the motivation-layer
models (SolutionDriver, SolutionGoal, SolutionRisk) rather than from ArchiMate
blueprint section scores, which require architecture model elements that most
solutions don't have at submission time.

Falls back to hardcoded defaults if no DB configuration exists for a gate.
"""

import logging

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Default gate definitions (used when no GovernanceGate row exists in DB)
# --------------------------------------------------------------------------- #
DEFAULT_GATES = {
    "arb_submission": {
        "description": "Architecture Review Board submission gate",
        # Section completeness checks require ArchiMate elements — not checked by default.
        # Use the GovernanceGate DB table to enable section checks if needed.
        "required_sections": [],
        "min_completeness": 60,
        # Architecture decisions are optional — architects add them progressively.
        "required_decisions_count": 0,
        "require_risk_mitigations": False,
        # Minimum motivation-layer entities — achievable through the normal UI flow.
        "min_entity_counts": {
            "drivers": 1,
            "goals": 1,
            "risks": 1,
        },
    },
}


def check_gate(solution_id, gate_name):
    """Check if a solution passes a governance gate.

    Args:
        solution_id: The solution to check.
        gate_name: The gate to evaluate (e.g. "arb_submission").

    Returns:
        dict with keys:
            passed (bool): True if the solution meets all gate requirements.
            failures (list[dict]): Each failure has keys:
                check (str), required, actual, reason (str).
            gate_name (str): Echo back the gate name.
    """
    gate_config = _load_gate_config(gate_name)
    if gate_config is None:
        return {
            "passed": False,
            "failures": [
                {
                    "check": "gate_config",
                    "required": gate_name,
                    "actual": None,
                    "reason": f"Unknown governance gate: {gate_name}",
                }
            ],
            "gate_name": gate_name,
        }

    if not gate_config.get("enabled", True):
        # Gate is disabled — always passes
        return {"passed": True, "failures": [], "gate_name": gate_name}

    failures = []

    # 1. Section completeness checks (only when required_sections is non-empty)
    _check_section_completeness(solution_id, gate_config, failures)

    # 2. Architecture decision count
    _check_decisions(solution_id, gate_config, failures)

    # 3. Risk mitigations
    _check_risk_mitigations(solution_id, gate_config, failures)

    # 4. Motivation-layer entity minimums
    _check_entity_minimums(solution_id, gate_config, failures)

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "gate_name": gate_name,
    }


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _load_gate_config(gate_name):
    """Load gate configuration from DB, falling back to hardcoded defaults."""
    try:
        from app.models.governance_gates import GovernanceGate

        gate = GovernanceGate.query.filter_by(gate_name=gate_name).first()
        if gate:
            return {
                "required_sections": gate.required_sections or [],
                "min_completeness": gate.min_completeness or 60,
                "required_decisions_count": gate.required_decisions_count or 0,
                "require_risk_mitigations": gate.require_risk_mitigations or False,
                "enabled": gate.enabled if gate.enabled is not None else True,
            }
    except Exception:
        logger.debug("GovernanceGate table not available, using defaults", exc_info=True)

    # Fall back to hardcoded defaults
    default = DEFAULT_GATES.get(gate_name)
    if default:
        return {
            "required_sections": default["required_sections"],
            "min_completeness": default["min_completeness"],
            "required_decisions_count": default["required_decisions_count"],
            "require_risk_mitigations": default["require_risk_mitigations"],
            "min_entity_counts": default.get("min_entity_counts", {}),
            "enabled": True,
        }

    return None


def _check_section_completeness(solution_id, gate_config, failures):
    """Verify that required sections meet the minimum completeness threshold."""
    required_sections = gate_config.get("required_sections", [])
    min_pct = gate_config.get("min_completeness", 60)

    if not required_sections:
        return

    try:
        from app.modules.solutions_strategic.v2.services.blueprint_completeness_service import (
            BlueprintCompletenessService,
            SECTION_TITLES,
        )

        svc = BlueprintCompletenessService()
        all_scores = svc.score_all(solution_id)

        for section_id in required_sections:
            scores = all_scores.get(section_id, {})
            overall = scores.get("overall", 0) if isinstance(scores, dict) else 0
            if overall < min_pct:
                title = SECTION_TITLES.get(section_id, section_id)
                failures.append(
                    {
                        "check": "section_completeness",
                        "required": min_pct,
                        "actual": overall,
                        "reason": f"{title}: {overall}% complete (minimum {min_pct}% required)",
                    }
                )
    except Exception:
        logger.exception("Failed to check section completeness for solution %s", solution_id)
        failures.append(
            {
                "check": "section_completeness",
                "required": min_pct,
                "actual": None,
                "reason": "Unable to compute section completeness scores",
            }
        )


def _check_decisions(solution_id, gate_config, failures):
    """Verify that the solution has the required number of approved decisions."""
    required_count = gate_config.get("required_decisions_count", 0)
    if required_count <= 0:
        return

    try:
        from app.models.architecture_decision import ArchitectureDecision

        approved_count = (
            ArchitectureDecision.query.filter_by(solution_id=solution_id, status="approved").count()
        )
        if approved_count < required_count:
            failures.append(
                {
                    "check": "approved_decisions",
                    "required": required_count,
                    "actual": approved_count,
                    "reason": f"{approved_count} approved decision(s) (minimum {required_count} required)",
                }
            )
    except Exception:
        logger.debug("ArchitectureDecision table not available", exc_info=True)
        failures.append(
            {
                "check": "approved_decisions",
                "required": required_count,
                "actual": 0,
                "reason": "Unable to query architecture decisions",
            }
        )


def _check_risk_mitigations(solution_id, gate_config, failures):
    """Verify that all critical/high risks have mitigation plans."""
    if not gate_config.get("require_risk_mitigations", False):
        return

    try:
        from app.models.solution_lifecycle_models import SolutionRisk

        critical_risks = SolutionRisk.query.filter(
            SolutionRisk.solution_id == solution_id,
            SolutionRisk.impact.in_(["critical", "high"]),
            SolutionRisk.status != "closed",
        ).all()

        unmitigated = [r for r in critical_risks if not r.mitigation or not r.mitigation.strip()]
        if unmitigated:
            failures.append(
                {
                    "check": "risk_mitigations",
                    "required": "all critical/high risks mitigated",
                    "actual": f"{len(unmitigated)} unmitigated",
                    "reason": f"{len(unmitigated)} critical/high risk(s) without mitigation plans",
                }
            )
    except Exception:
        logger.debug("SolutionRisk table not available", exc_info=True)
        # Don't fail if the table doesn't exist — gate still passes on this dimension


def _check_entity_minimums(solution_id, gate_config, failures):
    """Verify that the solution has minimum motivation-layer entity counts.

    Checks drivers, goals, and risks — all created through the standard
    blueprint UI without requiring ArchiMate model elements.
    """
    minimums = gate_config.get("min_entity_counts", {})
    if not minimums:
        return

    try:
        from app.models.solution_architect_models import (
            SolutionAnalysisSession,
            SolutionDriver,
            SolutionGoal,
            SolutionProblemDefinition,
        )
        from app.models.solution_lifecycle_models import SolutionRisk
        from app.models.solution_models import Solution

        # SolutionProblemDefinition links to solutions via
        # Solution.analysis_session_id → SolutionAnalysisSession → problem_definition
        pd_id = None
        solution_obj = Solution.query.get(solution_id)
        if solution_obj and solution_obj.analysis_session_id:
            session_obj = SolutionAnalysisSession.query.get(solution_obj.analysis_session_id)
            if session_obj and session_obj.problem_definition:
                pd_id = session_obj.problem_definition.id

        actual_counts = {
            "drivers": SolutionDriver.query.filter_by(problem_id=pd_id).count() if pd_id else 0,
            "goals": SolutionGoal.query.filter_by(problem_id=pd_id).count() if pd_id else 0,
            "risks": SolutionRisk.query.filter_by(solution_id=solution_id).count(),
        }

        labels = {"drivers": "driver(s)", "goals": "goal(s)", "risks": "risk(s)"}
        for entity_type, min_count in minimums.items():
            actual = actual_counts.get(entity_type, 0)
            if actual < min_count:
                label = labels.get(entity_type, entity_type)
                failures.append(
                    {
                        "check": f"min_{entity_type}",
                        "required": min_count,
                        "actual": actual,
                        "reason": (
                            f"Solution needs at least {min_count} {label} "
                            f"(found {actual}). Add them via the Strategic Context section."
                        ),
                    }
                )
    except Exception:
        logger.exception("Failed to check entity minimums for solution %s", solution_id)
