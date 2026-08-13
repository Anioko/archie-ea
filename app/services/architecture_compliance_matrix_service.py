"""AG-002: Architecture Compliance Matrix service.

Computes a per-application compliance scorecard using:
- ARBReviewItem status (latest review per application)
- ComplianceViolation count (per application)
- Scoring: approved=100, pending=50, rejected=0, conditional=75, default=60

All access is via ORM — no raw SQL.
"""
import logging
from typing import Dict, List

from sqlalchemy import desc

from app.models.application_portfolio import ApplicationComponent

logger = logging.getLogger(__name__)

_SCORE_MAP: Dict[str, int] = {
    "approved": 100,
    "pending": 50,
    "rejected": 0,
    "conditional": 75,
}


class ArchitectureComplianceMatrixService:
    """Computes the compliance matrix for all ApplicationComponent rows.

    No raw SQL. Missing optional models are handled with try/except ImportError.
    """

    def compute_compliance_matrix(self) -> List[Dict]:
        """Return one compliance dict per ApplicationComponent.

        Each dict contains:
            app_id, app_name, arb_review_status, compliance_score,
            violation_count, overall_status

        overall_status: score >= 80 → "compliant", >= 60 → "partial",
                        else "non_compliant"
        """
        try:
            apps = ApplicationComponent.query.order_by(ApplicationComponent.name).all()
        except Exception as exc:
            logger.warning("compute_compliance_matrix: failed to query apps: %s", exc)
            return []

        result: List[Dict] = []
        for app in apps:
            arb_status = self._get_arb_review_status(app.id)
            compliance_score = _SCORE_MAP.get(arb_status, 60)
            violation_count = self._get_violation_count(app.name)
            overall_status = self._overall_status(compliance_score)

            result.append(
                {
                    "app_id": app.id,
                    "app_name": app.name,
                    "arb_review_status": arb_status,
                    "compliance_score": compliance_score,
                    "violation_count": violation_count,
                    "overall_status": overall_status,
                }
            )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_arb_review_status(self, application_id: int) -> str:
        """Return the latest ARB review status for the given application id.

        Only ``ImportError`` is caught — the ARB model is optional. A query
        failure is allowed to propagate: "not_reviewed" is a governance claim
        about the application, and a caller that cannot tell it apart from a
        database error will act on it.
        """
        try:
            from app.models.architecture_review_board import ARBReviewItem
            from app.models.solution_models import Solution, solution_applications
        except ImportError:
            return "not_reviewed"

        # arb_review_items has no application_id column; reviews reach an
        # application via solution_id -> solution_applications junction.
        review = (
            ARBReviewItem.query.join(Solution, ARBReviewItem.solution_id == Solution.id)
            .join(
                solution_applications,
                solution_applications.c.solution_id == Solution.id,
            )
            .filter(
                solution_applications.c.application_component_id == application_id
            )
            .order_by(desc(ARBReviewItem.created_at))
            .first()
        )
        if review is not None:
            return review.status or "not_reviewed"
        return "not_reviewed"

    def _get_violation_count(self, application_name: str) -> int:
        """Return compliance violation count for the given application name.

        ``compliance_violations`` records its target only as the free-text
        ``affected_system`` column, so the match is by name.

        Only ``ImportError`` is caught — the compliance model is optional. A
        query failure propagates rather than being reported as ``0``, which the
        Phase G compliance matrix would publish as "no violations".
        """
        try:
            from app.models.compliance_models import ComplianceViolation
        except ImportError:
            return 0

        return ComplianceViolation.query.filter(
            ComplianceViolation.affected_system == application_name
        ).count()

    @staticmethod
    def _overall_status(score: int) -> str:
        if score >= 80:
            return "compliant"
        if score >= 60:
            return "partial"
        return "non_compliant"
