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
            return {"distribution": {}, "total": 0}

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
            return {"pending": 0, "approved": 0, "rejected": 0, "total": 0}

    def _get_capability_coverage(self):
        """Percentage of business capabilities with at least one solution mapping."""
        try:
            from app.models.business_capabilities import BusinessCapability
            from app.models.solution_models import SolutionCapabilityMapping

            total_caps = db.session.query(db.func.count(BusinessCapability.id)).scalar() or 0
            if total_caps == 0:
                return {"total": 0, "covered": 0, "percentage": 0.0}

            covered = (
                db.session.query(db.func.count(db.distinct(SolutionCapabilityMapping.capability_id)))
                .scalar()
            ) or 0
            pct = round((covered / total_caps) * 100, 1)
            return {"total": total_caps, "covered": covered, "percentage": pct}
        except Exception as exc:
            logger.warning("Executive dashboard: capability coverage unavailable: %s", exc)
            return {"total": 0, "covered": 0, "percentage": 0.0}

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
        - Capability coverage (20%): % capabilities with solution mapping
        - Governance (10%): % ARB items resolved (approved or rejected)
        """
        scores = {}

        # Phase maturity: % of solutions in Phase C or later
        try:
            from app.models.solution_models import Solution

            total = db.session.query(db.func.count(Solution.id)).scalar() or 0
            if total > 0:
                advanced_phases = ["C", "D", "E", "F", "G", "H"]
                advanced = (
                    db.session.query(db.func.count(Solution.id))
                    .filter(Solution.adm_phase.in_(advanced_phases))
                    .scalar()
                ) or 0
                scores["phase_maturity"] = round((advanced / total) * 100, 1)
            else:
                scores["phase_maturity"] = 0.0
        except Exception:
            scores["phase_maturity"] = 0.0

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
                scores["risk_posture"] = 100.0
        except Exception:
            scores["risk_posture"] = 100.0

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
        # An organisation with no ARB activity scores 0 (governance not in use).
        try:
            from datetime import datetime, timedelta
            from app.models.architecture_review_board import ARBReviewItem

            total_arb = db.session.query(db.func.count(ARBReviewItem.id)).scalar() or 0
            if total_arb == 0:
                scores["governance"] = 0.0
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
            scores["governance"] = 0.0

        # Weighted composite
        composite = round(
            scores["phase_maturity"] * 0.4
            + scores["risk_posture"] * 0.3
            + scores["capability_coverage"] * 0.2
            + scores["governance"] * 0.1,
            1,
        )

        return {
            "composite_score": composite,
            "components": scores,
        }
