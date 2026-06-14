"""Chief Architect synthesis (AI-7).

The meta-agent: instead of running each AI architect separately, it
assembles ONE board-ready packet per solution — the technical-conformance
verdict, the recommended decision (ADR), and a portfolio-wide synthesis —
so a review board sees the whole picture in a single view.

Pure orchestration over the existing reviewers (Conformance, Options
Advisor) + the solution context; deterministic and sourced.
"""

import logging
from typing import Any, Dict, List

from sqlalchemy import func

from app import db

logger = logging.getLogger(__name__)

def _n(count, singular, plural=None):
    """Big-4 copy: '3 findings' / '1 finding' — never 'finding(s)'."""
    word = singular if count == 1 else (plural or singular + "s")
    return f"{count} {word}"



class ChiefArchitectService:

    @classmethod
    def solution_packet(cls, solution_id: int) -> Dict[str, Any]:
        """One board-ready packet for a solution: conformance + decision +
        a synthesised verdict."""
        from app.models.solution_models import Solution
        from app.modules.solutions_strategic.v2.services.conformance_reviewer import (
            ConformanceReviewer,
        )
        from app.modules.solutions_strategic.v2.services.solution_options_advisor import (
            SolutionOptionsAdvisor,
        )

        solution = db.session.get(Solution, solution_id)
        if solution is None:
            return {"success": False, "error": "Solution not found."}

        conformance = ConformanceReviewer.review(solution_id)
        latest_adr = SolutionOptionsAdvisor.latest(solution_id)
        adr = SolutionOptionsAdvisor.to_dict(latest_adr) if latest_adr else None

        score = conformance.get("score", 0) if conformance.get("success") else None
        flagged = conformance.get("flagged", 0) if conformance.get("success") else 0
        has_decision = adr is not None
        decision_accepted = bool(adr and adr.get("status") == "accepted")

        # synthesised board verdict
        if score is None:
            verdict, tone = "Not yet reviewable", "info"
        elif flagged == 0 and decision_accepted:
            verdict, tone = "Ready for the board", "good"
        elif flagged == 0 and has_decision:
            verdict, tone = "Conformant — decision pending acceptance", "info"
        elif flagged == 0:
            verdict, tone = "Conformant — no decision recorded yet", "info"
        elif flagged and decision_accepted:
            verdict, tone = f"Decision made, but {_n(flagged, 'conformance issue')} to resolve", "warn"
        else:
            verdict, tone = f"{_n(flagged, 'conformance issue')} — not board-ready", "warn"

        readiness = cls._readiness(solution, conformance, adr)

        return {
            "success": True,
            "solution": {"id": solution.id, "name": solution.name,
                         "adm_phase": solution.adm_phase or "A",
                         "governance_status": getattr(solution, "governance_status", "draft")},
            "verdict": verdict,
            "tone": tone,
            "conformance": {
                "score": score,
                "flagged": flagged,
                "findings": conformance.get("findings", []) if conformance.get("success") else [],
            },
            "decision": adr,
            "readiness": readiness,
        }

    @staticmethod
    def _readiness(solution, conformance, adr) -> List[Dict[str, Any]]:
        """The board-readiness checklist — what's in place, what's missing."""
        items = [
            {"label": "Owner assigned", "ok": bool(getattr(solution, "solution_owner", None))},
            {"label": "Technical lead assigned", "ok": bool(getattr(solution, "technical_lead", None))},
            {"label": "Recommended decision (ADR)", "ok": adr is not None},
            {"label": "Decision accepted", "ok": bool(adr and adr.get("status") == "accepted")},
            {"label": "No high/critical conformance issues",
             "ok": conformance.get("success") and conformance.get("flagged", 1) == 0},
        ]
        return items

    @classmethod
    def portfolio_synthesis(cls) -> Dict[str, Any]:
        """Estate-wide synthesis: average conformance, decisions made, the
        solutions most in need of attention. Bounded to real solutions."""
        from app.models.solution_models import Solution
        from app.modules.solutions_strategic.v2.services.conformance_reviewer import (
            ConformanceReviewer,
        )

        # Real solutions only: a board-room synthesis must never showcase E2E
        # artifacts. The weekly AutoTest purge can lag, so exclude the known
        # test-name signatures here as defense-in-depth.
        solutions = (
            Solution.query
            .filter(
                ~Solution.name.like("J%-AutoTest-%"),
                ~Solution.name.like("ZZ %"),
                ~Solution.name.like("Untitled Solution%"),
            )
            .order_by(Solution.id.desc())
            .limit(60).all()
        )
        scored, flagged_total, worst = [], 0, []
        for s in solutions:
            try:
                r = ConformanceReviewer.review(s.id)
            except Exception:  # noqa: BLE001
                continue
            if not r.get("success"):
                continue
            scored.append(r["score"])
            flagged_total += r.get("flagged", 0)
            if r.get("flagged"):
                worst.append({"id": s.id, "name": s.name,
                              "score": r["score"], "flagged": r["flagged"]})
        worst.sort(key=lambda x: (x["score"], -x["flagged"]))
        avg = round(sum(scored) / len(scored)) if scored else None

        from app.models.architecture_review_board import ARBReviewItem
        decided = db.session.query(func.count(ARBReviewItem.id)).filter(
            ARBReviewItem.decision.isnot(None)
        ).scalar() or 0
        in_pipeline = db.session.query(func.count(ARBReviewItem.id)).filter(
            ARBReviewItem.status == "submitted"
        ).scalar() or 0

        return {
            "success": True,
            "solutions_reviewed": len(scored),
            "avg_conformance": avg,
            "flagged_total": flagged_total,
            "worst": worst[:5],
            "decisions_made": decided,
            "in_pipeline": in_pipeline,
        }
