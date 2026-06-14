"""
Intent Classifier Service (ENT-083)

Classifies user messages for governance/ARB intent using weighted keyword
scoring. No LLM call — fast, deterministic, zero external dependencies.

When ARB intent is detected and a solution context is available, auto-fetches
phase gate validation and ARB readiness data so the downstream LLM prompt
can reference real governance status.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Weighted keyword groups — scores: high=3, medium=2, low=1
# Threshold: total score >= 3 triggers ARB intent
# ---------------------------------------------------------------------------
_ARB_KEYWORDS: Dict[str, List[str]] = {
    "high": [
        "arb",
        "architecture review board",
        "governance review",
        "gate check",
        "phase gate",
        "readiness check",
        "arb submission",
        "arb review",
        "submit to arb",
        "arb readiness",
    ],
    "medium": [
        "ready for review",
        "governance",
        "board meeting",
        "approval",
        "submit for review",
        "compliance check",
        "sign-off",
        "sign off",
        "architecture board",
        "governance gate",
        "review board",
    ],
    "low": [
        "ready",
        "review",
        "assess",
        "evaluate readiness",
        "prepared",
        "meeting prep",
        "board",
        "compliant",
        "checklist",
    ],
}

_WEIGHT_MAP = {"high": 3, "medium": 2, "low": 1}
_THRESHOLD = 3


class IntentClassifierService:
    """Classifies user messages for governance/ARB intent without an extra
    LLM call.  Uses keyword scoring with weighted terms for fast, reliable
    detection."""

    def __init__(self) -> None:
        # Pre-compile regex patterns for each keyword (word-boundary aware)
        self._patterns: List[tuple] = []  # (compiled_re, weight, original_term)
        for tier, terms in _ARB_KEYWORDS.items():
            weight = _WEIGHT_MAP[tier]
            for term in terms:
                # Escape the term and wrap with word boundaries so partial
                # matches inside unrelated words are avoided.
                pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
                self._patterns.append((pattern, weight, term))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_intent(self, message: str) -> Dict[str, Any]:
        """Score *message* against ARB keyword groups.

        Returns::

            {
                "is_arb_intent": bool,
                "confidence": float,   # 0.0 – 1.0
                "score": int,
                "matched_terms": [str, ...],
            }
        """
        if not message:
            return {
                "is_arb_intent": False,
                "confidence": 0.0,
                "score": 0,
                "matched_terms": [],
            }

        score = 0
        matched_terms: List[str] = []

        for pattern, weight, term in self._patterns:
            if pattern.search(message):
                score += weight
                matched_terms.append(term)

        # Normalise confidence to [0, 1].  A score of 9 (three high-weight
        # matches) maps to 1.0; anything at or above 9 is capped.
        max_practical_score = 9
        confidence = min(score / max_practical_score, 1.0)

        return {
            "is_arb_intent": score >= _THRESHOLD,
            "confidence": round(confidence, 2),
            "score": score,
            "matched_terms": matched_terms,
        }

    def get_arb_context(self, solution_id: int) -> Dict[str, Any]:
        """Fetch phase-gate validation and ARB readiness for *solution_id*.

        Returns a dict suitable for injection into the LLM system prompt::

            {
                "solution_name": str,
                "current_phase": str,
                "phase_gate": {"valid": bool, "errors": [...], "warnings": [...]},
                "arb_readiness": {"can_submit": bool, "checks": [...]},
            }

        On any error (missing model, DB issue) returns an empty dict so the
        caller can safely skip augmentation.
        """
        try:
            from app.models.solution_models import Solution
        except Exception:
            logger.debug("IntentClassifier: Solution model not available")
            return {}

        try:
            solution = Solution.query.get(solution_id)
            if not solution:
                logger.debug("IntentClassifier: solution %s not found", solution_id)
                return {}

            current_phase = getattr(solution, "adm_phase", None) or "A"
            phase_gate = solution.validate_phase_gate(current_phase)
            arb_readiness = solution.arb_readiness

            return {
                "solution_name": solution.name,
                "solution_id": solution.id,
                "current_phase": current_phase,
                "phase_gate": phase_gate,
                "arb_readiness": arb_readiness,
            }
        except Exception as exc:
            logger.warning("IntentClassifier: error fetching ARB context: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Prompt augmentation helper
    # ------------------------------------------------------------------

    def build_arb_prompt_supplement(self, arb_context: Dict[str, Any]) -> str:
        """Turn *arb_context* (from :meth:`get_arb_context`) into a
        human-readable supplement that can be appended to the LLM system
        prompt."""
        if not arb_context:
            return ""

        lines = [
            "\n--- ARB / Governance Context (auto-detected) ---",
            f"Solution: {arb_context.get('solution_name', 'Unknown')} "
            f"(ID {arb_context.get('solution_id', '?')})",
            f"Current ADM Phase: {arb_context.get('current_phase', '?')}",
        ]

        # Phase gate
        pg = arb_context.get("phase_gate", {})
        gate_status = "PASSED" if pg.get("valid") else "FAILED"
        lines.append(f"Phase Gate Status: {gate_status}")
        for err in pg.get("errors", []):
            lines.append(f"  [ERROR] {err}")
        for warn in pg.get("warnings", []):
            lines.append(f"  [WARNING] {warn}")

        # ARB readiness
        ar = arb_context.get("arb_readiness", {})
        can_submit = ar.get("can_submit", False)
        lines.append(f"ARB Submission Ready: {'Yes' if can_submit else 'No'}")
        for check in ar.get("checks", []):
            status = "PASS" if check.get("passed") else "FAIL"
            req = " (required)" if check.get("required") else ""
            lines.append(f"  [{status}] {check.get('label', '?')}{req}")

        lines.append("--- End ARB Context ---\n")
        return "\n".join(lines)
