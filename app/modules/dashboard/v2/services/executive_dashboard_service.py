"""Executive dashboard service — aggregates existing analytics for CTO/CIO view.

Queries real data from Solution, SolutionRisk, ARBReviewItem,
BusinessCapability, SolutionCapabilityMapping, ApplicationComponent,
VendorOrganization, and ArchiMateElement models.
"""

import logging

from app import db

logger = logging.getLogger(__name__)


class ExecutiveDashboardService:
    """Aggregates cross-domain metrics into a single executive summary."""

    def get_executive_summary(self):
        """Return all executive KPIs in a single dict."""
        return {
            "architecture_health": self._get_health_score(),
            "programme_progress": self._get_phase_distribution(),
            "risk_posture": self._get_risk_summary(),
            "pending_decisions": self._get_arb_pending(),
            "capability_coverage": self._get_capability_coverage(),
            "portfolio_stats": self._get_portfolio_stats(),
        }

    # ------------------------------------------------------------------
    # Private metric methods
    # ------------------------------------------------------------------

    def _get_phase_distribution(self):
        """Count solutions per TOGAF ADM phase (A-H)."""
        try:
            from app.models.solution_models import Solution

            rows = (
                db.session.query(
                    Solution.adm_phase, db.func.count(Solution.id)
                )
                .group_by(Solution.adm_phase)
                .all()
            )
            distribution = {}
            total = 0
            for phase, count in rows:
                label = phase or "Unknown"
                distribution[label] = count
                total += count
            return {"distribution": distribution, "total": total}
        except Exception as exc:
            logger.warning("Executive dashboard: phase distribution unavailable: %s", exc)
            return {"distribution": {}, "total": None}  # honest: totals not computed on error

    def _get_risk_summary(self):
        """Aggregate open risks by impact severity."""
        try:
            from app.models.solution_lifecycle_models import SolutionRisk

            rows = (
                db.session.query(
                    SolutionRisk.impact, db.func.count(SolutionRisk.id)
                )
                .filter(SolutionRisk.status == "open")
                .group_by(SolutionRisk.impact)
                .all()
            )
            counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            total = 0
            for impact, count in rows:
                key = (impact or "medium").lower()
                counts[key] = counts.get(key, 0) + count
                total += count
            return {"counts": counts, "total": total}
        except Exception as exc:
            logger.warning("Executive dashboard: risk summary unavailable: %s", exc)
            return {"counts": {"critical": 0, "high": 0, "medium": 0, "low": 0}, "total": 0}

    def _get_arb_pending(self):
        """Count ARB review items by status."""
        try:
            from app.models.architecture_review_board import ARBReviewItem

            rows = (
                db.session.query(
                    ARBReviewItem.status, db.func.count(ARBReviewItem.id)
                )
                .group_by(ARBReviewItem.status)
                .all()
            )
            by_status = {}
            for status, count in rows:
                by_status[status or "unknown"] = count

            pending = by_status.get("draft", 0) + by_status.get("submitted", 0) + by_status.get("pending", 0)
            return {
                "pending": pending,
                "approved": by_status.get("approved", 0),
                "rejected": by_status.get("rejected", 0),
                "total": sum(by_status.values()),
            }
        except Exception as exc:
            logger.warning("Executive dashboard: ARB pending unavailable: %s", exc)
            return {"pending": None, "approved": None, "rejected": None, "total": None}  # honest: ARB counts not computed on error

    def _get_capability_coverage(self):
        """Percentage of L1 business capabilities with at least one mapped
        application.

        4 Sep 2026: this used to independently count capabilities with a
        SolutionCapabilityMapping row (a much sparser relationship than
        applications), disagreeing live with the CTO-tab hero panel's
        identically-labelled, identically-weighted "Capability Coverage"
        component (100% vs 0% observed on the same page). Now calls the same
        shared computation the hero uses — see capability_coverage.py.
        """
        try:
            from app.modules.dashboard.v2.services.capability_coverage import (
                compute_l1_capability_coverage,
            )

            return compute_l1_capability_coverage()
        except Exception as exc:
            # Counts are None, not 0: the query failed, so nothing is known about
            # the capability set. Returning zeros would render as a measured
            # "0 capabilities, 0% covered".
            logger.warning("Executive dashboard: capability coverage unavailable: %s", exc)
            return {"total": None, "covered": None, "percentage": None}

    def _get_portfolio_stats(self):
        """Counts for solutions, applications, vendors, ArchiMate elements."""
        stats = {"solutions": 0, "applications": 0, "vendors": 0, "archimate_elements": 0}
        try:
            from app.models.solution_models import Solution

            stats["solutions"] = db.session.query(db.func.count(Solution.id)).scalar() or 0
        except Exception as exc:
            logger.warning("Executive dashboard: solution count unavailable: %s", exc)

        try:
            from app.models.application_portfolio import ApplicationComponent

            stats["applications"] = db.session.query(db.func.count(ApplicationComponent.id)).scalar() or 0
        except Exception as exc:
            logger.warning("Executive dashboard: application count unavailable: %s", exc)

        try:
            from app.models.vendor.vendor_organization import VendorOrganization

            stats["vendors"] = db.session.query(db.func.count(VendorOrganization.id)).scalar() or 0
        except Exception as exc:
            logger.warning("Executive dashboard: vendor count unavailable: %s", exc)

        try:
            from app.models.archimate_core import ArchiMateElement

            stats["archimate_elements"] = db.session.query(db.func.count(ArchiMateElement.id)).scalar() or 0
        except Exception as exc:
            logger.warning("Executive dashboard: ArchiMate count unavailable: %s", exc)

        return stats

    def _get_health_score(self):
        """Compute a composite architecture health score (0-100).

        Weighted average of:
        - Phase maturity (40%): % of solutions past Phase B
        - Risk posture (30%): inverse of high/critical risk ratio
        - Capability coverage (20%): % L1 capabilities with application mapping
        - Governance (10%): ARB presence, timeliness and approval rate

        A component is ``None`` when it could not be measured — the query failed,
        or there is nothing to measure yet. It is deliberately not zero, and for
        risk posture emphatically not 100: this method used to answer a database
        failure with ``risk_posture = 100.0``, reporting a *perfect* enterprise
        risk posture at exactly the moment it knew least. Per CLAUDE.md a value
        the system does not have must reach the UI as ``None`` (rendered as an em
        dash), because a plausible number is indistinguishable from a measured
        one and the reader acts on it.

        The composite is re-weighted over whichever components are available, and
        is itself ``None`` when none of them are.
        """
        scores = {}

        # Phase maturity: % of solutions in Phase C or later.
        # Only recorded, valid phases supply a denominator. NULL/invalid phase
        # does not mean Phase A, nor a measured failure to progress past Phase B.
        # Match the scorecard/pipeline's normalization of imported phase values.
        try:
            from app.models.solution_models import Solution

            phase = db.func.upper(db.func.trim(Solution.adm_phase))
            total = (
                db.session.query(db.func.count(Solution.id))
                .filter(phase.in_(list("ABCDEFGH")))
                .scalar()
            ) or 0
            if total > 0:
                advanced_phases = ["C", "D", "E", "F", "G", "H"]
                advanced = (
                    db.session.query(db.func.count(Solution.id))
                    .filter(phase.in_(advanced_phases))
                    .scalar()
                ) or 0
                scores["phase_maturity"] = round((advanced / total) * 100, 1)
            else:
                scores["phase_maturity"] = None
        except Exception:
            logger.exception("health score: phase maturity could not be measured")
            scores["phase_maturity"] = None

        # Risk posture: fewer high/critical is better
        try:
            from app.models.solution_lifecycle_models import SolutionRisk

            total_risks = (
                db.session.query(db.func.count(SolutionRisk.id))
                .filter(SolutionRisk.status == "open")
                .scalar()
            ) or 0
            if total_risks > 0:
                severe = (
                    db.session.query(db.func.count(SolutionRisk.id))
                    .filter(
                        SolutionRisk.status == "open",
                        SolutionRisk.impact.in_(["critical", "high"]),
                    )
                    .scalar()
                ) or 0
                scores["risk_posture"] = round((1 - severe / total_risks) * 100, 1)
            else:
                # No open risks recorded is not the same as a clean risk posture.
                # On a new or unpopulated tenant it means nobody has captured any
                # risk yet, and scoring that 100 tells a CTO the opposite.
                scores["risk_posture"] = None
        except Exception:
            logger.exception("health score: risk posture could not be measured")
            scores["risk_posture"] = None

        # Capability coverage
        cap = self._get_capability_coverage()
        scores["capability_coverage"] = cap["percentage"]

        # Governance: ARB throughput score
        #
        # Old formula: resolved/total punished platforms that actively used
        # the ARB — a queue of pending items (which is healthy) scored 0%.
        #
        # New formula measures three things:
        #   - Presence: ARB process is being used at all (50 pts baseline if any item exists)
        #   - Timeliness: resolved items as % of items older than 30 days (pending > 30d = overdue)
        #   - Approval rate: approved / resolved (healthy governance approves most things)
        #
        # An organisation with an active, up-to-date ARB queue scores near 100.
        # An organisation with stale unresolved items scores lower.
        # No ARB activity leaves no denominator to measure governance against.
        try:
            from datetime import datetime, timedelta
            from app.models.architecture_review_board import ARBReviewItem

            total_arb = db.session.query(db.func.count(ARBReviewItem.id)).scalar() or 0
            if total_arb == 0:
                scores["governance"] = None
            else:
                resolved = (
                    db.session.query(db.func.count(ARBReviewItem.id))
                    .filter(ARBReviewItem.status.in_(["approved", "rejected"]))
                    .scalar()
                ) or 0

                cutoff = datetime.utcnow() - timedelta(days=30)
                overdue = (
                    db.session.query(db.func.count(ARBReviewItem.id))
                    .filter(
                        ARBReviewItem.status.notin_(["approved", "rejected"]),
                        ARBReviewItem.created_at < cutoff,
                    )
                    .scalar()
                ) or 0
                pending = total_arb - resolved

                # Timeliness: what fraction of pending items are NOT overdue?
                timeliness = (1 - overdue / pending) if pending > 0 else 1.0

                # Approval rate among resolved (low rejection rate is normal/healthy)
                approved = (
                    db.session.query(db.func.count(ARBReviewItem.id))
                    .filter(ARBReviewItem.status == "approved")
                    .scalar()
                ) or 0
                approval_rate = (approved / resolved) if resolved > 0 else 0.5

                # Composite: presence (fixed 40) + timeliness (40) + approval_rate (20)
                gov_score = 40 + round(timeliness * 40) + round(approval_rate * 20)
                scores["governance"] = min(100.0, float(gov_score))
        except Exception:
            logger.exception("health score: governance could not be measured")
            scores["governance"] = None

        # Weighted composite over the components that could actually be measured,
        # with the weights renormalised across them. Averaging a missing component
        # in as zero would drag the headline score down for a reason the reader
        # cannot see; treating the whole composite as unavailable when one part is
        # missing would hide the three that are known.
        weights = {
            "phase_maturity": 0.4,
            "risk_posture": 0.3,
            "capability_coverage": 0.2,
            "governance": 0.1,
        }
        available = {k: w for k, w in weights.items() if scores.get(k) is not None}
        total_weight = sum(available.values())
        composite = (
            round(sum(scores[k] * w for k, w in available.items()) / total_weight, 1)
            if total_weight
            else None
        )

        return {
            "composite_score": composite,
            "components": scores,
            # Names the components that could not be measured, so the UI can say
            # which part of the score is missing rather than silently showing a
            # number derived from less than it appears.
            "unavailable_components": sorted(k for k in weights if scores.get(k) is None),
        }
