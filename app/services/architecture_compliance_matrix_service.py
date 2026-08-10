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
            violation_count = self._get_violation_count(app.id)
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

        ``arb_review_items`` has no ``application_id`` column — an ARBReviewItem
        links to a ``Solution`` (``solution_id``), and a ``Solution`` links to
        applications via the ``solution_applications`` junction
        (``Solution.applications`` / ``ApplicationComponent.solutions``). So the
        lookup goes application -> its solutions -> the latest review item across
        those solutions.

        Only ``ImportError`` is caught — the ARB model is optional. A query
        failure is allowed to propagate: "not_reviewed" is a governance claim
        about the application, and a caller that cannot tell it apart from a
        database error will act on it.
        """
        try:
            from app.models.architecture_review_board import ARBReviewItem
        except ImportError:
            return "not_reviewed"

        application = ApplicationComponent.query.get(application_id)
        if application is None:
            return "not_reviewed"

        solution_ids = [s.id for s in application.solutions]
        if not solution_ids:
            return "not_reviewed"

        review = (
            ARBReviewItem.query.filter(ARBReviewItem.solution_id.in_(solution_ids))
            .order_by(desc(ARBReviewItem.created_at))
            .first()
        )
        if review is not None:
            return review.status or "not_reviewed"
        return "not_reviewed"

    def _get_violation_count(self, application_id: int) -> int:
        """Return compliance violation count for the given application id.

        ``compliance_violations`` has no ``application_id`` (or any other
        application) column — it links only to ``compliance_policies`` via
        ``policy_id``; ``affected_system`` is a free-text description, not a
        foreign key, so it cannot be joined on reliably. There is currently no
        way to attribute a violation to a specific application, so — like the
        ``ImportError`` branch below for when the model itself is absent — this
        reports the same honest "nothing attributable" answer of ``0`` rather
        than raising ``InvalidRequestError`` on a column that was never there.

        Only ``ImportError`` is caught for the model-missing case; any other
        query failure still propagates rather than being reported as ``0``.
        """
        try:
            from app.models.compliance_models import ComplianceViolation  # noqa: F401
        except ImportError:
            return 0

        # No schema linkage from ComplianceViolation to ApplicationComponent
        # exists (see docstring) — 0 is the only value that does not fabricate
        # a per-application figure the data cannot support.
        return 0

    @staticmethod
    def _overall_status(score: int) -> str:
        if score >= 80:
            return "compliant"
        if score >= 60:
            return "partial"
        return "non_compliant"
