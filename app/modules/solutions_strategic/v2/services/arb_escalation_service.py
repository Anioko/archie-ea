"""ARB Escalation Service (AI-6).

Closes the loop on the AI architects: any finding they surface — drift,
a conformance violation, a PII/classification gap, a canonical duplicate —
can be escalated into the Architecture Review Board pipeline as a tracked
review item with one click. The AI senses; the ARB disposes.

Creates an ARBReviewItem in 'submitted' status so it enters the existing
governance pipeline (the same one the dashboard + health scorecard show).
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app import db

logger = logging.getLogger(__name__)

# finding category -> ARB review type (string values of the ReviewType enum)
_TYPE_MAP = {
    "integration": "integration_pattern",
    "clean_core": "standard_deviation",
    "technology": "architecture_change",
    "deployment": "architecture_change",
    "drift": "architecture_change",
    "rationalization": "retirement_review",
    "capability": "capability_implementation",
    "canonical": "architecture_change",
    "classification": "compliance_review",
    "lineage": "architecture_change",
    "governance": "exception_request",
    "portfolio": "architecture_change",
}
_PRIORITY_MAP = {"critical": "critical", "high": "high", "info": "low"}


class ARBEscalationService:

    @classmethod
    def escalate(
        cls,
        title: str,
        detail: str,
        category: str,
        severity: str,
        user_id: int,
        solution_id: Optional[int] = None,
        source: str = "ai_finding",
    ) -> Dict[str, Any]:
        """Create an ARB review item from an AI finding. Returns
        {success, review_number, id} or {success: False, error}."""
        from app.models.architecture_review_board import ARBReviewItem

        title = (title or "").strip()
        if not title:
            return {"success": False, "error": "A finding title is required."}

        try:
            review_number = ARBReviewItem.generate_review_number()
            item = ARBReviewItem(
                review_number=review_number,
                title=title[:255],
                description=(
                    f"{detail or ''}\n\n"
                    f"— Raised from an AI architect finding "
                    f"(category: {category or 'general'}, severity: {severity or 'info'})."
                ).strip(),
                review_type=_TYPE_MAP.get((category or "").lower(), "architecture_change"),
                priority=_PRIORITY_MAP.get((severity or "info").lower(), "medium"),
                business_impact=_PRIORITY_MAP.get((severity or "info").lower(), "medium"),
                solution_id=solution_id,
                status="submitted",
                submitter_id=user_id,
                submitted_at=datetime.utcnow(),
            )
            db.session.add(item)
            db.session.commit()
            logger.info(
                "AI finding escalated to ARB %s (category=%s, severity=%s, source=%s)",
                review_number, category, severity, source,
            )
            return {"success": True, "review_number": review_number, "id": item.id}
        except Exception as exc:  # noqa: BLE001
            logger.error("ARB escalation failed: %s", exc)
            db.session.rollback()
            return {"success": False, "error": "Could not create the ARB review item."}
