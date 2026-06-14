"""
ARB Analytics Service

Provides metrics, trends, and analytics for ARB operations including:
- Cycle time analytics (submission to decision)
- Approval rate trends
- Governance score trends
- Reviewer workload distribution
- Review type distribution
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_

from app import db
from app.models.architecture_review_board import (
    ARBAuditLog,
    ARBException,
    ARBGovernanceStandard,
    ARBReviewItem,
    ARBReviewStatus,
    ARBSession,
)

logger = logging.getLogger(__name__)


class ARBAnalyticsService:
    """
    Service for ARB metrics and analytics.
    """

    def __init__(self):
        pass

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """
        Get key metrics for the ARB dashboard.

        Returns:
            Dictionary with dashboard metrics
        """
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)

        # Total counts
        total_reviews = ARBReviewItem.query.count()
        pending_reviews = ARBReviewItem.query.filter(
            ARBReviewItem.status == ARBReviewStatus.DRAFT.value
        ).count()
        submitted_reviews = ARBReviewItem.query.filter(
            ARBReviewItem.status == ARBReviewStatus.SUBMITTED.value
        ).count()
        under_review = ARBReviewItem.query.filter(
            ARBReviewItem.status == ARBReviewStatus.UNDER_REVIEW.value
        ).count()

        # Decisions in last 30 days
        recent_decisions = ARBReviewItem.query.filter(
            ARBReviewItem.decision_date >= thirty_days_ago,
            ARBReviewItem.decision.isnot(None),
        ).all()

        approved = len([r for r in recent_decisions if r.decision == "approved"])
        rejected = len([r for r in recent_decisions if r.decision == "rejected"])
        deferred = len([r for r in recent_decisions if r.decision == "deferred"])

        # Approval rate
        decided = approved + rejected
        approval_rate = round((approved / decided * 100), 1) if decided > 0 else 0

        # Average governance score
        reviews_with_score = ARBReviewItem.query.filter(
            ARBReviewItem.overall_score.isnot(None)
        ).all()
        avg_score = (
            round(sum(r.overall_score for r in reviews_with_score) / len(reviews_with_score), 1)
            if reviews_with_score
            else 0
        )

        # Upcoming sessions
        upcoming_sessions = ARBSession.query.filter(
            ARBSession.scheduled_date >= now,
            ARBSession.status != "cancelled",
        ).count()

        # Active exceptions (handle missing columns gracefully)
        try:
            active_exceptions = ARBException.query.filter(
                ARBException.status == "approved",
                or_(
                    ARBException.expires_at.is_(None),
                    ARBException.expires_at > now,
                ),
            ).count()
        except Exception:
            db.session.rollback()
            try:
                active_exceptions = ARBException.query.filter(
                    ARBException.status == "approved",
                ).count()
            except Exception:
                db.session.rollback()
                active_exceptions = 0

        # Expiring exceptions (next 30 days)
        try:
            expiring_exceptions = ARBException.query.filter(
                ARBException.status == "approved",
                ARBException.expires_at <= now + timedelta(days=30),
                ARBException.expires_at > now,
            ).count()
        except Exception:
            db.session.rollback()
            expiring_exceptions = 0

        return {
            "total_reviews": total_reviews,
            "pending_reviews": pending_reviews,
            "submitted_reviews": submitted_reviews,
            "under_review": under_review,
            "recent_decisions": {
                "approved": approved,
                "rejected": rejected,
                "deferred": deferred,
                "total": len(recent_decisions),
            },
            "approval_rate": approval_rate,
            "avg_overall_score": avg_score,
            "upcoming_sessions": upcoming_sessions,
            "active_exceptions": active_exceptions,
            "expiring_exceptions": expiring_exceptions,
        }

    def get_cycle_time_analytics(
        self,
        period_days: int = 90,
    ) -> Dict[str, Any]:
        """
        Calculate cycle time analytics (time from submission to decision).

        Args:
            period_days: Number of days to analyze

        Returns:
            Cycle time statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)

        # Get decided reviews with both dates
        reviews = ARBReviewItem.query.filter(
            ARBReviewItem.decision_date >= cutoff,
            ARBReviewItem.decision_date.isnot(None),
            ARBReviewItem.submitted_at.isnot(None),
        ).all()

        if not reviews:
            return {
                "period_days": period_days,
                "total_reviews": 0,
                "avg_days": 0,
                "min_days": 0,
                "max_days": 0,
                "median_days": 0,
                "by_review_type": {},
                "by_priority": {},
            }

        # Calculate cycle times
        cycle_times = []
        by_type = defaultdict(list)
        by_priority = defaultdict(list)

        for review in reviews:
            days = (review.decision_date - review.submitted_at).days
            cycle_times.append(days)
            by_type[review.review_type].append(days)
            by_priority[review.priority].append(days)

        cycle_times.sort()

        # Calculate statistics
        avg_days = round(sum(cycle_times) / len(cycle_times), 1)
        min_days = min(cycle_times)
        max_days = max(cycle_times)
        median_days = cycle_times[len(cycle_times) // 2]

        # By type averages
        by_type_avg = {t: round(sum(times) / len(times), 1) for t, times in by_type.items()}

        # By priority averages
        by_priority_avg = {p: round(sum(times) / len(times), 1) for p, times in by_priority.items()}

        return {
            "period_days": period_days,
            "total_reviews": len(reviews),
            "avg_days": avg_days,
            "min_days": min_days,
            "max_days": max_days,
            "median_days": median_days,
            "by_review_type": by_type_avg,
            "by_priority": by_priority_avg,
        }

    def get_approval_trends(
        self,
        months: int = 12,
    ) -> Dict[str, Any]:
        """
        Get monthly approval rate trends.

        Args:
            months: Number of months to analyze

        Returns:
            Monthly approval trends
        """
        now = datetime.utcnow()
        trends = []

        for i in range(months - 1, -1, -1):
            # Calculate month boundaries
            month_start = now.replace(day=1) - timedelta(days=i * 30)
            month_start = month_start.replace(day=1, hour=0, minute=0, second=0)

            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1)

            # Query reviews decided in this month
            reviews = ARBReviewItem.query.filter(
                ARBReviewItem.decision_date >= month_start,
                ARBReviewItem.decision_date < month_end,
                ARBReviewItem.decision.isnot(None),
            ).all()

            approved = len([r for r in reviews if r.decision == "approved"])
            rejected = len([r for r in reviews if r.decision == "rejected"])
            deferred = len([r for r in reviews if r.decision == "deferred"])
            total = len(reviews)

            approval_rate = (
                round((approved / (approved + rejected) * 100), 1)
                if (approved + rejected) > 0
                else 0
            )

            trends.append(
                {
                    "month": month_start.strftime("%Y-%m"),
                    "month_name": month_start.strftime("%b %Y"),
                    "total": total,
                    "approved": approved,
                    "rejected": rejected,
                    "deferred": deferred,
                    "approval_rate": approval_rate,
                }
            )

        return {
            "months": months,
            "trends": trends,
        }

    def get_overall_score_trends(
        self,
        months: int = 12,
    ) -> Dict[str, Any]:
        """
        Get monthly governance score trends.

        Args:
            months: Number of months to analyze

        Returns:
            Monthly score trends
        """
        now = datetime.utcnow()
        trends = []

        for i in range(months - 1, -1, -1):
            # Calculate month boundaries
            month_start = now.replace(day=1) - timedelta(days=i * 30)
            month_start = month_start.replace(day=1, hour=0, minute=0, second=0)

            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1)

            # Query reviews with scores in this month
            reviews = ARBReviewItem.query.filter(
                ARBReviewItem.created_at >= month_start,
                ARBReviewItem.created_at < month_end,
                ARBReviewItem.overall_score.isnot(None),
            ).all()

            if reviews:
                avg_score = round(sum(r.overall_score for r in reviews) / len(reviews), 1)
                min_score = min(r.overall_score for r in reviews)
                max_score = max(r.overall_score for r in reviews)
            else:
                avg_score = 0
                min_score = 0
                max_score = 0

            trends.append(
                {
                    "month": month_start.strftime("%Y-%m"),
                    "month_name": month_start.strftime("%b %Y"),
                    "count": len(reviews),
                    "avg_score": avg_score,
                    "min_score": min_score,
                    "max_score": max_score,
                }
            )

        return {
            "months": months,
            "trends": trends,
        }

    def get_reviewer_workload(
        self,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get reviewer workload distribution.

        Args:
            period_days: Number of days to analyze

        Returns:
            Workload by reviewer
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)

        # Get reviews assigned in the period
        reviews = ARBReviewItem.query.filter(
            ARBReviewItem.updated_at >= cutoff,
        ).all()

        # Count by approver
        by_approver = defaultdict(lambda: {"assigned": 0, "decided": 0, "pending": 0})

        for review in reviews:
            if review.decided_by_id:
                approver_email = (
                    review.decided_by.email if review.decided_by else f"user_{review.decided_by_id}"
                )
                by_approver[approver_email]["assigned"] += 1

                if review.decision:
                    by_approver[approver_email]["decided"] += 1
                else:
                    by_approver[approver_email]["pending"] += 1

        # Convert to list and sort
        workload = [
            {
                "reviewer": email,
                "assigned": data["assigned"],
                "decided": data["decided"],
                "pending": data["pending"],
            }
            for email, data in by_approver.items()
        ]
        workload.sort(key=lambda x: x["assigned"], reverse=True)

        return {
            "period_days": period_days,
            "total_reviews": len(reviews),
            "reviewers": workload,
        }

    def get_review_type_distribution(
        self,
        period_days: int = 90,
    ) -> Dict[str, Any]:
        """
        Get distribution of review types.

        Args:
            period_days: Number of days to analyze

        Returns:
            Review type distribution
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)

        reviews = ARBReviewItem.query.filter(
            ARBReviewItem.created_at >= cutoff,
        ).all()

        distribution = defaultdict(int)
        for review in reviews:
            distribution[review.review_type] += 1

        # Convert to list with percentages
        total = len(reviews)
        type_data = [
            {
                "type": review_type,
                "count": count,
                "percentage": round((count / total * 100), 1) if total > 0 else 0,
            }
            for review_type, count in distribution.items()
        ]
        type_data.sort(key=lambda x: x["count"], reverse=True)

        return {
            "period_days": period_days,
            "total_reviews": total,
            "distribution": type_data,
        }

    def get_togaf_phase_distribution(
        self,
        period_days: int = 90,
    ) -> Dict[str, Any]:
        """
        Get distribution by TOGAF ADM phase.

        Args:
            period_days: Number of days to analyze

        Returns:
            TOGAF phase distribution
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)

        reviews = ARBReviewItem.query.filter(
            ARBReviewItem.created_at >= cutoff,
            ARBReviewItem.togaf_phase.isnot(None),
        ).all()

        distribution = defaultdict(int)
        for review in reviews:
            distribution[review.togaf_phase] += 1

        # Convert to list
        total = len(reviews)
        phase_data = [
            {
                "phase": phase,
                "count": count,
                "percentage": round((count / total * 100), 1) if total > 0 else 0,
            }
            for phase, count in distribution.items()
        ]
        phase_data.sort(key=lambda x: x["phase"])

        return {
            "period_days": period_days,
            "total_reviews": total,
            "distribution": phase_data,
        }

    def get_standard_compliance_summary(self) -> Dict[str, Any]:
        """
        Get compliance summary across governance standards.

        Returns:
            Standard compliance summary
        """
        standards = ARBGovernanceStandard.query.filter(
            ARBGovernanceStandard.status == "active"
        ).all()

        summary = []
        for standard in standards:
            # Count reviews referencing this standard
            # This is a simplified approach - actual implementation would
            # depend on how standards are linked to reviews

            summary.append(
                {
                    "id": standard.id,
                    "code": standard.code,
                    "name": standard.name,
                    "category": standard.category,
                    "mandatory": standard.mandatory,
                    "checklist_items": len(standard.checklist_items)
                    if standard.checklist_items
                    else 0,
                }
            )

        return {
            "total_standards": len(standards),
            "mandatory_count": len([s for s in summary if s["mandatory"]]),
            "standards": summary,
        }

    def get_exception_analytics(
        self,
        period_days: int = 365,
    ) -> Dict[str, Any]:
        """
        Get exception analytics.

        Args:
            period_days: Number of days to analyze

        Returns:
            Exception statistics
        """
        try:
            cutoff = datetime.utcnow() - timedelta(days=period_days)

            # Try with created_at filter; fall back to fetching all if column missing
            try:
                exceptions = ARBException.query.filter(
                    ARBException.created_at >= cutoff,
                ).all()
            except Exception:
                db.session.rollback()
                exceptions = ARBException.query.all()

            # By status
            by_status = defaultdict(int)
            for exc in exceptions:
                by_status[exc.status or "unknown"] += 1

            # By type
            by_type = defaultdict(int)
            for exc in exceptions:
                by_type[exc.exception_type or "unknown"] += 1

            # Approval rate
            approved = by_status.get("approved", 0)
            denied = by_status.get("denied", 0)
            decided = approved + denied
            approval_rate = round((approved / decided * 100), 1) if decided > 0 else 0

            # Average time to decision (handle missing date columns)
            avg_days = 0
            try:
                decided_exceptions = [
                    e
                    for e in exceptions
                    if e.status in ["approved", "denied"]
                    and getattr(e, "requested_at", None)
                    and (getattr(e, "approved_at", None) or getattr(e, "denied_at", None))
                ]

                if decided_exceptions:
                    total_days = sum(
                        ((e.approved_at or e.denied_at) - e.requested_at).days
                        for e in decided_exceptions
                    )
                    avg_days = round(total_days / len(decided_exceptions), 1)
            except Exception:
                avg_days = 0

            return {
                "period_days": period_days,
                "total_exceptions": len(exceptions),
                "by_status": dict(by_status),
                "by_type": dict(by_type),
                "approval_rate": approval_rate,
                "avg_days_to_decision": avg_days,
            }
        except Exception as e:
            logger.error(f"Error getting exception analytics: {e}")
            return {
                "period_days": period_days,
                "total_exceptions": 0,
                "by_status": {},
                "by_type": {},
                "approval_rate": 0,
                "avg_days_to_decision": 0,
            }

    def generate_comprehensive_report(
        self,
        period_days: int = 90,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive ARB analytics report.

        Args:
            period_days: Number of days to analyze

        Returns:
            Complete analytics report
        """
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "period_days": period_days,
        }

        # Each section is isolated so one failure doesn't crash the whole report
        sections = {
            "dashboard": lambda: self.get_dashboard_metrics(),
            "cycle_time": lambda: self.get_cycle_time_analytics(period_days),
            "approval_trends": lambda: self.get_approval_trends(12),
            "overall_scores": lambda: self.get_overall_score_trends(12),
            "reviewer_workload": lambda: self.get_reviewer_workload(period_days),
            "review_types": lambda: self.get_review_type_distribution(period_days),
            "togaf_phases": lambda: self.get_togaf_phase_distribution(period_days),
            "exceptions": lambda: self.get_exception_analytics(period_days),
            "standards": lambda: self.get_standard_compliance_summary(),
        }

        for key, func in sections.items():
            try:
                report[key] = func()
            except Exception as e:
                db.session.rollback()
                report[key] = {"error": str(e)}

        return report


# Create singleton instance
arb_analytics_service = ARBAnalyticsService()
