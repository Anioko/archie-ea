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



def _safe(name: str, fn: Callable[[], List[Dict]], default=None, checks_run=None):
    """Run one finding gatherer, tolerating its failure, and record whether
    it actually ran — distinguishing 'ran and found nothing' from 'did not
    run' (M-02: 'evidence-grounded' must mean the checks executed)."""
    try:
        result = fn()
        if checks_run is not None:
            checks_run.append({"check": name, "ran": True, "findings": len(result)})
        return result
    except Exception as exc:  # noqa: BLE001 — one bad section can't break the briefing
        logger.debug("briefing section %s unavailable: %s", name, exc)
        if checks_run is not None:
            checks_run.append({"check": name, "ran": False, "findings": 0})
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

        checks_run: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []
        findings += _safe("drift", cls._drift_findings, checks_run=checks_run)
        findings += _safe("rationalization", cls._rationalization_findings, checks_run=checks_run)
        findings += _safe("capability", cls._capability_findings, checks_run=checks_run)
        findings += _safe("governance", cls._governance_findings, checks_run=checks_run)
        findings += _safe("portfolio", cls._portfolio_findings, checks_run=checks_run)
        findings += _safe("duplicates", cls._duplicate_element_findings, checks_run=checks_run)
        findings += _safe("orphans", cls._orphan_element_findings, checks_run=checks_run)
        findings += _safe("descriptions", cls._missing_description_findings, checks_run=checks_run)
        findings += _safe("solutions", cls._solution_hygiene_findings, checks_run=checks_run)
        findings += _safe("stale_reviews", cls._stale_review_findings, checks_run=checks_run)

        rank = {"critical": 0, "high": 1, "info": 2}
        findings.sort(key=lambda f: rank.get(f.get("severity", "info"), 3))
        flagged = sum(1 for f in findings if f.get("severity") in ("critical", "high"))

        headline, summary = cls._narrative(findings, flagged, checks_run)

        briefing = EnterpriseBriefing(
            source=source,
            generated_by_id=user_id,
            headline=headline,
            summary=summary,
            findings=findings,
            finding_count=len(findings),
            flagged_count=flagged,
            checks_run=checks_run,
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

    @classmethod
    def _duplicate_element_findings(cls) -> List[Dict]:
        """Elements sharing the same name — the drift/rationalization checks
        above never look at the ArchiMate catalogue at all, so an estate can
        be riddled with duplicate names and still report 'all clear'. Exact
        (case/whitespace-insensitive) name match; the Data Steward's semantic
        engine (DataStewardshipReviewer) catches non-identical synonyms and
        is scoped to DataObjects — this is the estate-wide, exact-match net."""
        from app.models.archimate_core import ArchiMateElement

        rows = db.session.query(ArchiMateElement.id, ArchiMateElement.name).all()
        groups: Dict[str, List[int]] = {}
        for eid, name in rows:
            key = (name or "").strip().lower()
            if not key:
                continue
            groups.setdefault(key, []).append(eid)
        dupe_groups = {k: v for k, v in groups.items() if len(v) > 1}
        if not dupe_groups:
            return []
        total_elements = sum(len(v) for v in dupe_groups.values())
        worst = sorted(dupe_groups.items(), key=lambda kv: -len(kv[1]))[:5]
        return [{
            "category": "duplicates",
            "severity": "high" if len(dupe_groups) >= 5 else "info",
            "title": f"{_n(len(dupe_groups), 'duplicate name group')} across {_n(total_elements, 'ArchiMate element')}",
            "detail": (
                "These elements share an identical name and are likely the same "
                "concept modelled twice: "
                + ", ".join(f'"{k}" ({len(v)})' for k, v in worst)
                + (f" and {len(dupe_groups) - len(worst)} more" if len(dupe_groups) > len(worst) else "")
                + ". Duplicate elements fragment traceability and inflate impact analysis."
            ),
            "evidence": "ArchiMate element catalogue · exact name match, case-insensitive",
            "action_label": "Open element catalogue",
            "action_url": "/architecture/dashboard",
        }]

    @classmethod
    def _orphan_element_findings(cls) -> List[Dict]:
        """Elements with no relationship in either direction — unconnected to
        the rest of the model, so nothing reasons about their impact."""
        from app.models.archimate_core import ArchiMateElement, ArchiMateRelationship

        total = db.session.query(func.count(ArchiMateElement.id)).scalar() or 0
        if not total:
            return []
        connected_ids = set()
        for src, tgt in db.session.query(
            ArchiMateRelationship.source_id, ArchiMateRelationship.target_id
        ).all():
            if src is not None:
                connected_ids.add(src)
            if tgt is not None:
                connected_ids.add(tgt)
        all_ids = {i for (i,) in db.session.query(ArchiMateElement.id).all()}
        orphans = len(all_ids - connected_ids)
        if not orphans:
            return []
        pct = round(orphans / total * 100)
        return [{
            "category": "orphans",
            "severity": "high" if pct >= 40 else "info",
            "title": f"{_n(orphans, 'element')} ha{'s' if orphans == 1 else 've'} no relationships",
            "detail": (
                f"{orphans} of {total} ArchiMate elements ({pct}%) have no incoming "
                "or outgoing relationship — they are modelled but disconnected from "
                "the rest of the architecture, so impact analysis cannot trace them."
            ),
            "evidence": "ArchiMate relationships · element id absent from source_id/target_id",
            "action_label": "Open element catalogue",
            "action_url": "/architecture/dashboard",
        }]

    @classmethod
    def _missing_description_findings(cls) -> List[Dict]:
        from app.models.archimate_core import ArchiMateElement

        total = db.session.query(func.count(ArchiMateElement.id)).scalar() or 0
        if not total:
            return []
        missing = db.session.query(func.count(ArchiMateElement.id)).filter(
            db.or_(ArchiMateElement.description.is_(None), ArchiMateElement.description == "")
        ).scalar() or 0
        if not missing:
            return []
        pct = round(missing / total * 100)
        return [{
            "category": "descriptions",
            "severity": "info",
            "title": f"{_n(missing, 'element')} ha{'s' if missing == 1 else 've'} no description",
            "detail": (
                f"{missing} of {total} ArchiMate elements ({pct}%) carry no "
                "description — a review board cannot assess intent from a bare name."
            ),
            "evidence": "ArchiMate element catalogue · description is null/empty",
            "action_label": "Open element catalogue",
            "action_url": "/architecture/dashboard",
        }]

    @classmethod
    def _solution_hygiene_findings(cls) -> List[Dict]:
        """Empty solutions and solutions sharing a name — both invisible to
        the conformance/decision checks, which only run once content exists."""
        from app.models.solution_models import Solution, SolutionArchiMateElement

        out = []
        solutions = Solution.query.all()
        if not solutions:
            return out

        elements_by_solution = dict(
            db.session.query(
                SolutionArchiMateElement.solution_id, func.count(SolutionArchiMateElement.id)
            ).group_by(SolutionArchiMateElement.solution_id).all()
        )
        empty = [s for s in solutions if not elements_by_solution.get(s.id)]
        if empty:
            pct = round(len(empty) / len(solutions) * 100)
            out.append({
                "category": "solutions",
                "severity": "high" if pct >= 50 else "info",
                "title": f"{_n(len(empty), 'solution')} ha{'s' if len(empty) == 1 else 've'} no architecture content",
                "detail": (
                    f"{len(empty)} of {len(solutions)} solutions ({pct}%) have no "
                    "ArchiMate elements linked — they cannot be conformance-reviewed "
                    "and should not be counted toward portfolio health as if clean: "
                    + ", ".join(f'"{s.name}"' for s in empty[:8])
                    + ("…" if len(empty) > 8 else "")
                    + "."
                ),
                "evidence": "Solution ↔ ArchiMate element links · count = 0",
                "action_label": "Open solutions",
                "action_url": "/solutions/",
            })

        name_groups: Dict[str, List[str]] = {}
        for s in solutions:
            key = (s.name or "").strip().lower()
            if not key:
                continue
            name_groups.setdefault(key, []).append(s.name)
        dupes = {k: v for k, v in name_groups.items() if len(v) > 1}
        if dupes:
            first_name = next(iter(dupes.values()))[0]
            out.append({
                "category": "solutions",
                "severity": "high",
                "title": f"{_n(len(dupes), 'pair of solutions')} share a name",
                "detail": (
                    f'{_n(sum(len(v) for v in dupes.values()), "solution")} across '
                    f"{len(dupes)} name collision(s), e.g. \"{first_name}\" — reviewers "
                    "and ARB submissions cannot disambiguate which solution is meant."
                ),
                "evidence": "Solution catalogue · exact name match, case-insensitive",
                "action_label": "Open solutions",
                "action_url": "/solutions/",
            })
        return out

    @classmethod
    def _stale_review_findings(cls) -> List[Dict]:
        """ARB reviews submitted but not decided within the governance SLA
        target (21 days — see ProgrammeGovernanceService/M-08's SLA display)."""
        from app.models.architecture_review_board import ARBReviewItem

        sla_days = 21
        cutoff = datetime.utcnow() - timedelta(days=sla_days)
        stale = (
            ARBReviewItem.query
            .filter(ARBReviewItem.status == "submitted")
            .filter(ARBReviewItem.submitted_at.isnot(None))
            .filter(ARBReviewItem.submitted_at < cutoff)
            .all()
        )
        if not stale:
            return []
        return [{
            "category": "governance",
            "severity": "high" if len(stale) >= 3 else "info",
            "title": f"{_n(len(stale), 'ARB review')} pending past the {sla_days}-day SLA",
            "detail": (
                ", ".join(f'"{r.title}" ({r.review_number})' for r in stale[:6])
                + (f" and {len(stale) - 6} more" if len(stale) > 6 else "")
                + f" have been submitted for over {sla_days} days with no decision recorded."
            ),
            "evidence": f"ARB review items · status=submitted, submitted_at < now-{sla_days}d",
            "action_label": "Open ARB queue",
            "action_url": "/arb/",
        }]

    # ------------------------------------------------------------------ #
    # Narrative                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _narrative(findings: List[Dict], flagged: int, checks_run: List[Dict] = None):
        checks_run = checks_run or []
        ran = sum(1 for c in checks_run if c.get("ran"))
        failed = sum(1 for c in checks_run if not c.get("ran"))
        if not findings:
            if failed:
                # "All clear" must mean every check executed and found nothing —
                # not that some checks silently didn't run (M-02).
                return (
                    f"{ran} of {len(checks_run)} checks ran clean; {failed} did not run",
                    f"{ran} checks executed and found nothing to flag. {failed} check(s) "
                    "could not run (see logs) — this is not the same as 'all clear' and "
                    "should not be read as a clean estate.",
                )
            return (
                "All clear this period",
                f"All {ran} checks ran and found no notable enterprise-architecture findings.",
            )
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
