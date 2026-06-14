"""Enterprise Architecture Briefing Agent (AI-2).

Computes the notable EA findings from live platform data and persists a
briefing. Each finding is deterministic and sourced (Rule 11): the
gathering produces real counts/names with a page to verify; the narrative
only summarises what was found — it never invents a number.

Categories:
  drift          — programmes flagged in recent governance snapshots
  rationalization— estate disposition pressure (retire/eliminate signals)
  capability     — capabilities with no supporting application (SPOF / gap)
  governance     — clean-core below target, ARB pipeline state
  portfolio      — lifecycle posture, decommission pipeline

Severity: 'critical' | 'high' | 'info'. flagged_count counts critical+high.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List

from sqlalchemy import func

from app import db

logger = logging.getLogger(__name__)

def _n(count, singular, plural=None):
    """Big-4 copy: '3 findings' / '1 finding' — never 'finding(s)'."""
    word = singular if count == 1 else (plural or singular + "s")
    return f"{count} {word}"



def _safe(name: str, fn: Callable[[], List[Dict]], default=None):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — one bad section can't break the briefing
        logger.debug("briefing section %s unavailable: %s", name, exc)
        return default if default is not None else []


class EnterpriseBriefingService:
    """Generate and persist Enterprise-Architecture briefings."""

    RECENT_DAYS = 7

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def generate(cls, user_id: int, source: str = "manual"):
        """Compute findings, write narrative, persist an EnterpriseBriefing.
        Returns the saved row. Commits."""
        from app.models.strategic import EnterpriseBriefing

        findings: List[Dict[str, Any]] = []
        findings += _safe("drift", cls._drift_findings)
        findings += _safe("rationalization", cls._rationalization_findings)
        findings += _safe("capability", cls._capability_findings)
        findings += _safe("governance", cls._governance_findings)
        findings += _safe("portfolio", cls._portfolio_findings)

        rank = {"critical": 0, "high": 1, "info": 2}
        findings.sort(key=lambda f: rank.get(f.get("severity", "info"), 3))
        flagged = sum(1 for f in findings if f.get("severity") in ("critical", "high"))

        headline, summary = cls._narrative(findings, flagged)

        briefing = EnterpriseBriefing(
            source=source,
            generated_by_id=user_id,
            headline=headline,
            summary=summary,
            findings=findings,
            finding_count=len(findings),
            flagged_count=flagged,
        )
        db.session.add(briefing)
        db.session.commit()
        logger.info(
            "EA briefing %s generated (%d findings, %d flagged, source=%s)",
            briefing.id, len(findings), flagged, source,
        )
        return briefing

    @staticmethod
    def latest():
        from app.models.strategic import EnterpriseBriefing
        return (
            EnterpriseBriefing.query
            .order_by(EnterpriseBriefing.generated_at.desc(), EnterpriseBriefing.id.desc())
            .first()
        )

    @staticmethod
    def history(limit: int = 20):
        from app.models.strategic import EnterpriseBriefing
        return (
            EnterpriseBriefing.query
            .order_by(EnterpriseBriefing.generated_at.desc(), EnterpriseBriefing.id.desc())
            .limit(limit).all()
        )

    # ------------------------------------------------------------------ #
    # Finding gatherers (each returns a list of finding dicts)            #
    # ------------------------------------------------------------------ #

    @classmethod
    def _drift_findings(cls) -> List[Dict]:
        from app.models.strategic import ProgrammeSnapshot, StrategicInitiative

        cutoff = datetime.utcnow() - timedelta(days=cls.RECENT_DAYS)
        snaps = (
            ProgrammeSnapshot.query
            .filter(ProgrammeSnapshot.taken_at >= cutoff)
            .order_by(ProgrammeSnapshot.taken_at.desc())
            .all()
        )
        out, seen = [], set()
        for s in snaps:
            drift = s.drift or {}
            if not drift.get("flagged") or s.initiative_id in seen:
                continue
            seen.add(s.initiative_id)
            prog = db.session.get(StrategicInitiative, s.initiative_id)
            name = prog.name if prog else f"Programme {s.initiative_id}"
            out.append({
                "category": "drift",
                "severity": "high",
                "title": f"Drift detected on {name}",
                "detail": "; ".join(drift.get("reasons", [])) or "Governance snapshot flagged a change.",
                "evidence": f"Snapshot {s.id} · {s.taken_at:%d %b %Y}",
                "action_label": "Open programme cockpit",
                "action_url": f"/solutions/programmes/{s.initiative_id}",
            })
        return out

    @classmethod
    def _rationalization_findings(cls) -> List[Dict]:
        from app.models.application_rationalization import ApplicationRationalizationScore

        rows = dict(
            db.session.query(
                ApplicationRationalizationScore.rationalization_action, func.count()
            ).group_by(ApplicationRationalizationScore.rationalization_action).all()
        )
        if not rows:
            return []
        # Retire/eliminate/replace pressure = disposition that needs action
        pressure_terms = ("retire", "eliminate", "replace", "decommission")
        pressure = sum(
            n for action, n in rows.items()
            if action and any(t in action.lower() for t in pressure_terms)
        )
        total = sum(rows.values())
        out = []
        if pressure:
            out.append({
                "category": "rationalization",
                "severity": "high" if pressure >= 20 else "info",
                "title": f"{_n(pressure, 'application')} flagged for retire/replace",
                "detail": (
                    f"Of {total} scored applications, {pressure} carry a "
                    "retire, replace, or decommission disposition — candidates "
                    "for a rationalization wave."
                ),
                "evidence": "Rationalization scores (TIME / 7R)",
                "action_label": "Open rationalization",
                "action_url": "/applications/rationalization",
            })
        return out

    @classmethod
    def _capability_findings(cls) -> List[Dict]:
        from app.models.business_capabilities import BusinessCapability

        total = db.session.query(func.count(BusinessCapability.id)).scalar() or 0
        if not total:
            return []
        # Capabilities with no supporting application mapping = coverage gap
        unsupported = 0
        try:
            from app.models.application_capability import ApplicationCapabilityMapping
            supported_ids = {
                r[0] for r in db.session.query(
                    ApplicationCapabilityMapping.business_capability_id
                ).distinct().all()
            }
            all_ids = {r[0] for r in db.session.query(BusinessCapability.id).all()}
            unsupported = len(all_ids - supported_ids)
        except Exception as exc:
            logger.debug("capability mapping lookup unavailable: %s", exc)
            return []
        out = []
        if unsupported:
            pct = round(unsupported / total * 100)
            out.append({
                "category": "capability",
                "severity": "high" if pct >= 50 else "info",
                "title": f"{_n(unsupported, 'capability', 'capabilities')} ha{'s' if unsupported == 1 else 've'} no supporting application",
                "detail": (
                    f"{unsupported} of {total} business capabilities ({pct}%) "
                    "are not supported by any mapped application — coverage gaps "
                    "or single points of failure."
                ),
                "evidence": "Capability ↔ application mappings",
                "action_label": "Open capability map",
                "action_url": "/capability-map/",
            })
        return out

    @classmethod
    def _governance_findings(cls) -> List[Dict]:
        from app.models.solution_models import Solution
        from app.models.strategic import StrategicInitiative
        from app.modules.solutions_strategic.v2.services.programme_governance_service import (
            ProgrammeGovernanceService,
        )

        out = []
        programmes = (
            StrategicInitiative.query
            .filter(StrategicInitiative.initiative_type.isnot(None)).all()
        )
        for prog in programmes:
            roll = _safe(f"rollup-{prog.id}", lambda p=prog: [ProgrammeGovernanceService.rollup(p.id)], [None])
            roll = roll[0] if roll else None
            if not roll:
                continue
            fg = roll.get("fit_gap", {})
            score, target = fg.get("clean_core_score"), fg.get("clean_core_target")
            if score is not None and target and score < target:
                out.append({
                    "category": "governance",
                    "severity": "high" if (target - score) >= 20 else "info",
                    "title": f"{prog.name}: clean-core {score}% below {target}% target",
                    "detail": (
                        f"Clean-core posture is {target - score}pp under the "
                        "governance target — extension/custom pressure is "
                        "eroding the core."
                    ),
                    "evidence": "Programme fit-gap rollup",
                    "action_label": "Open fit-gap workbench",
                    "action_url": f"/solutions/programmes/{prog.id}/fit-gap",
                })
        return out

    @classmethod
    def _portfolio_findings(cls) -> List[Dict]:
        from app.models.application_portfolio import ApplicationComponent

        rows = dict(
            db.session.query(
                ApplicationComponent.lifecycle_status, func.count()
            ).group_by(ApplicationComponent.lifecycle_status).all()
        )
        total = sum(rows.values())
        if not total:
            return []
        decom = sum(
            n for st, n in rows.items()
            if st and any(t in str(st).lower() for t in ("decom", "retire", "sunset", "5."))
        )
        out = [{
            "category": "portfolio",
            "severity": "info",
            "title": f"Portfolio: {total} applications under management",
            "detail": (
                f"{_n(decom, 'application')} {'is' if decom == 1 else 'are'} in the sunset/decommission pipeline. "
                "Confirm migration plans are in place before end-of-life."
            ),
            "evidence": "Application lifecycle distribution",
            "action_label": "Open applications",
            "action_url": "/applications/",
        }]
        return out

    # ------------------------------------------------------------------ #
    # Narrative                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _narrative(findings: List[Dict], flagged: int):
        if not findings:
            return ("All clear this period", "No notable enterprise-architecture findings.")
        cats = sorted({f["category"] for f in findings})
        top = next((f for f in findings if f.get("severity") in ("critical", "high")), None)
        if top:
            headline = top["title"]
        else:
            headline = f"{_n(len(findings), 'item')} for review across {_n(len(cats), 'area')}"
        summary = (
            f"This briefing surfaces {_n(len(findings), 'finding')} "
            f"({flagged} needing attention) across {', '.join(cats)}. "
            "Each item links to the page where it can be verified and actioned. "
            "Figures are read live from the platform at generation time."
        )
        return headline[:300], summary
