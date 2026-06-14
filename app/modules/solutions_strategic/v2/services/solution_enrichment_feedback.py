"""Solution Enrichment Feedback Service (BPP-015).

Closes the flywheel: when an SA accepts element suggestions, the
underlying ArchiMate relationships are promoted to the enterprise
graph.  Rejections are logged for model calibration.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from app import db
from app.models.archimate_core import ArchiMateRelationship

logger = logging.getLogger(__name__)


class SolutionEnrichmentFeedback:
    """Promote SA-confirmed relationships to the enterprise ArchiMate graph."""

    def on_suggestions_accepted(
        self,
        solution_id: int,
        accepted_elements: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """Promote relationships implied by accepted suggestions.

        For each accepted element that has a ``relationship_type`` and a
        related element (the element it was connected to in the suggestion
        reason), check whether an ``ArchiMateRelationship`` already exists
        between them.  If not, create it with ``source='user_confirmed'``.

        Args:
            solution_id: The solution whose suggestions were accepted.
            accepted_elements: List of accepted suggestion dicts, each
                containing at least ``element_id`` and optionally
                ``relationship_type`` and ``related_element_id``.

        Returns:
            Stats dict: ``{promoted, skipped_existing, errors}``.
        """
        promoted = 0
        skipped = 0
        errors = 0

        for item in accepted_elements:
            element_id = item.get("element_id")
            rel_type = item.get("relationship_type")
            related_id = item.get("related_element_id")

            if not element_id or not rel_type or not related_id:
                continue

            try:
                # Check if relationship already exists
                existing = ArchiMateRelationship.query.filter_by(
                    source_id=related_id,
                    target_id=element_id,
                    type=rel_type,
                ).first()

                if existing:
                    skipped += 1
                    continue

                # Also check reverse direction
                existing_rev = ArchiMateRelationship.query.filter_by(
                    source_id=element_id,
                    target_id=related_id,
                    type=rel_type,
                ).first()

                if existing_rev:
                    skipped += 1
                    continue

                # Create the relationship
                new_rel = ArchiMateRelationship(
                    source_id=related_id,
                    target_id=element_id,
                    type=rel_type,
                )
                db.session.add(new_rel)
                promoted += 1

            except Exception as e:
                logger.error(
                    "Error promoting relationship %s->%s (%s): %s",
                    related_id, element_id, rel_type, e,
                )
                errors += 1

        if promoted > 0:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error("Failed to commit promoted relationships: %s", e)
                errors += promoted
                promoted = 0

        # Log to audit trail
        self._log_audit(
            solution_id, "suggestions_accepted",
            {"promoted": promoted, "skipped": skipped, "errors": errors},
        )

        logger.info(
            "Enrichment feedback for solution %d: "
            "promoted=%d, skipped=%d, errors=%d",
            solution_id, promoted, skipped, errors,
        )
        return {"promoted": promoted, "skipped_existing": skipped, "errors": errors}

    def on_suggestions_rejected(
        self,
        solution_id: int,
        rejected_elements: List[Dict[str, Any]],
    ) -> None:
        """Log rejections for model calibration (no DB changes).

        Args:
            solution_id: The solution whose suggestions were rejected.
            rejected_elements: List of rejected suggestion dicts.
        """
        self._log_audit(
            solution_id, "suggestions_rejected",
            {"count": len(rejected_elements)},
        )
        logger.info(
            "Enrichment feedback: %d suggestions rejected for solution %d",
            len(rejected_elements), solution_id,
        )

    def _log_audit(self, solution_id: int, action: str, details: dict) -> None:
        """Append to the guardrail audit log."""
        import json
        import os

        log_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__)
                )))
            ))),
            "docs", "guardrail_audit_log.jsonl",
        )
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": f"relationship_{action}",
            "source": "suggestion_acceptance",
            "solution_id": solution_id,
            **details,
        }
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.debug("Could not write audit log: %s", e)
