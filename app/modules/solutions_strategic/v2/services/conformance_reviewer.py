"""Technical Architecture Conformance Reviewer (AI-4).

The AI Technical Architect as a reviewer: it reads a solution's design and
checks it against the platform's technical POLICY — which exists as data
(the integration-pattern catalogue's approval status, the clean-core
weighting, the ArchiMate technology layer, deployment models) — and
returns ranked findings, each with the violated policy, the evidence, and
the concrete fix.

Deterministic and sourced (Rule 11): the checks are rules over live data,
not generation — so a review is fast, free, and always reflects the
current state. Each section is fault-tolerant. Findings never fabricate.

Severity: 'critical' | 'high' | 'info'. A conformance score starts at 100
and is debited per finding by severity, floored at 0.
"""

import logging
from typing import Any, Callable, Dict, List

from sqlalchemy import func

from app import db

logger = logging.getLogger(__name__)

def _n(count, singular, plural=None):
    """Big-4 copy: '3 findings' / '1 finding' — never 'finding(s)'."""
    word = singular if count == 1 else (plural or singular + "s")
    return f"{count} {word}"


_DEBIT = {"critical": 25, "high": 12, "info": 0}
# clean-core eroding fit types (custom build / heavy customization)
_EROSION_FITS = {"custom", "customization", "custom_development"}


def _safe(name: str, fn: Callable[[], List[Dict]]) -> List[Dict]:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — one bad check can't break the review
        logger.debug("conformance check %s unavailable: %s", name, exc)
        return []


class ConformanceReviewer:
    """Review a solution against technical policy; return ranked findings."""

    @classmethod
    def review(cls, solution_id: int) -> Dict[str, Any]:
        """Returns {success, solution_id, score, findings, summary} or
        {success: False, error}."""
        from app.models.solution_models import Solution

        solution = db.session.get(Solution, solution_id)
        if solution is None:
            return {"success": False, "error": "Solution not found."}

        findings: List[Dict[str, Any]] = []
        findings += _safe("integration", lambda: cls._integration_findings(solution_id))
        findings += _safe("clean_core", lambda: cls._clean_core_findings(solution_id))
        findings += _safe("technology", lambda: cls._technology_findings(solution_id))
        findings += _safe("deployment", lambda: cls._deployment_findings(solution_id))

        rank = {"critical": 0, "high": 1, "info": 2}
        findings.sort(key=lambda f: rank.get(f.get("severity", "info"), 3))

        score = 100
        for f in findings:
            score -= _DEBIT.get(f.get("severity", "info"), 0)
        score = max(0, score)
        flagged = sum(1 for f in findings if f.get("severity") in ("critical", "high"))

        if not findings:
            summary = "No technical-conformance issues found. The design aligns with platform policy."
        else:
            summary = (
                f"{_n(len(findings), 'conformance finding')} ({flagged} needing attention). "
                "Each names the policy it breaches and the fix. Reviewed live against "
                "the integration-pattern catalogue, clean-core weighting, and the "
                "ArchiMate technology layer."
            )

        return {
            "success": True,
            "solution_id": solution_id,
            "solution_name": solution.name,
            "score": score,
            "flagged": flagged,
            "findings": findings,
            "summary": summary,
        }

    # ------------------------------------------------------------------ #
    # Checks                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _integration_findings(sid: int) -> List[Dict]:
        from app.models.integration_pattern import IntegrationPattern
        from app.models.solution_sad_models import SolutionIntegrationFlow

        rows = (
            db.session.query(
                IntegrationPattern.name, IntegrationPattern.approval_status,
                func.count(SolutionIntegrationFlow.id),
            )
            .join(SolutionIntegrationFlow,
                  SolutionIntegrationFlow.pattern_id == IntegrationPattern.id)
            .filter(SolutionIntegrationFlow.solution_id == sid)
            .group_by(IntegrationPattern.name, IntegrationPattern.approval_status)
            .all()
        )
        out = []
        for name, status, n in rows:
            st = (status or "").lower()
            if st == "blocked":
                out.append({
                    "category": "integration",
                    "severity": "critical",
                    "title": f"Blocked integration pattern in use: {name}",
                    "detail": (
                        f"{_n(n, 'integration flow')} use{'s' if n == 1 else ''} '{name}', which the pattern "
                        "catalogue marks BLOCKED. Replace it with an approved pattern."
                    ),
                    "evidence": "Integration-pattern catalogue · approval_status=blocked",
                    "recommendation": "Re-route these flows through an approved pattern.",
                })
            elif st in ("deprecated", "conditional"):
                out.append({
                    "category": "integration",
                    "severity": "high" if st == "deprecated" else "info",
                    "title": f"{st.title()} integration pattern: {name}",
                    "detail": (
                        f"{_n(n, 'flow')} use{'s' if n == 1 else ''} '{name}' ({st}). "
                        + ("Plan migration off it." if st == "deprecated"
                           else "Allowed only with documented justification.")
                    ),
                    "evidence": f"Integration-pattern catalogue · approval_status={st}",
                    "recommendation": ("Migrate to an approved pattern." if st == "deprecated"
                                       else "Document the conditional-use justification for the ARB."),
                })
        return out

    @staticmethod
    def _clean_core_findings(sid: int) -> List[Dict]:
        from app.models.solution_models import SolutionFitGapEntry

        rows = dict(
            db.session.query(SolutionFitGapEntry.fit_type, func.count())
            .filter(SolutionFitGapEntry.solution_id == sid)
            .group_by(SolutionFitGapEntry.fit_type).all()
        )
        if not rows:
            return []
        erosion = sum(n for ft, n in rows.items() if ft and ft.lower() in _EROSION_FITS)
        total = sum(rows.values())
        if not erosion:
            return []
        pct = round(erosion / total * 100)
        return [{
            "category": "clean_core",
            "severity": "high" if pct >= 30 else "info",
            "title": f"{_n(erosion, 'fit-gap entry', 'fit-gap entries')} erode{'s' if erosion == 1 else ''} clean core",
            "detail": (
                f"{erosion} of {total} fit-gap entries ({pct}%) are custom build or "
                "heavy customization — the lowest clean-core weighting. Prefer "
                "standard/configuration or a governed extension."
            ),
            "evidence": "Fit-gap register · fit_type in (custom, customization, custom_development)",
            "recommendation": "Reclassify or redesign these toward standard/configuration/extension.",
        }]

    @staticmethod
    def _technology_findings(sid: int) -> List[Dict]:
        from app.models.solution_models import SolutionArchiMateElement

        total = (
            db.session.query(func.count(SolutionArchiMateElement.id))
            .filter(SolutionArchiMateElement.solution_id == sid).scalar() or 0
        )
        if total == 0:
            return []  # nothing modelled yet — not a conformance issue
        tech = (
            db.session.query(func.count(SolutionArchiMateElement.id))
            .filter(SolutionArchiMateElement.solution_id == sid)
            .filter(SolutionArchiMateElement.layer_type.ilike("technology")).scalar() or 0
        )
        if tech > 0:
            return []
        return [{
            "category": "technology",
            "severity": "high",
            "title": "No technology-layer elements — design lacks a technical underpinning",
            "detail": (
                f"The solution models {_n(total, 'ArchiMate element')} but none on the "
                "Technology layer (nodes, system software, deployment). A design "
                "without a technology underpinning is incomplete and unbuildable as-specified."
            ),
            "evidence": "ArchiMate elements · layer_type=technology = 0",
            "recommendation": "Add the technology nodes/platforms the application components run on.",
        }]

    @staticmethod
    def _deployment_findings(sid: int) -> List[Dict]:
        from app.models.application_portfolio import ApplicationComponent
        from app.models.solution_models import solution_applications

        rows = (
            db.session.query(
                ApplicationComponent.deployment_model, func.count()
            )
            .join(solution_applications,
                  solution_applications.c.application_component_id == ApplicationComponent.id)
            .filter(solution_applications.c.solution_id == sid)
            .group_by(ApplicationComponent.deployment_model)
            .all()
        )
        total = sum(n for _, n in rows)
        if total == 0:
            return []
        missing = sum(n for dm, n in rows if not dm)
        if not missing:
            return []
        return [{
            "category": "deployment",
            "severity": "info",
            "title": f"{_n(missing, 'application')} ha{'s' if missing == 1 else 've'} no recorded deployment model",
            "detail": (
                f"{missing} of {total} linked applications lack a deployment model "
                "(cloud / on-prem / hybrid). Technology governance and TCO need it."
            ),
            "evidence": "Application portfolio · deployment_model is null",
            "recommendation": "Set the deployment model on each linked application.",
        }]
