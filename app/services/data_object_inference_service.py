"""
DataObjectInferenceService

Infers canonical DataObject entries from ArchiMate data-related elements
and persists missing entries with keyword-based classification.
"""

import logging
from typing import Dict

from app import db
from app.models.archimate_core import ArchiMateElement
from app.models.models import DataObject

logger = logging.getLogger(__name__)

_CLASSIFICATION_RULES = [
    ({"financial", "payment", "finance", "billing", "invoice", "revenue"}, "confidential"),
    ({"personal", "hr", "employee", "staff", "payroll", "identity", "pii"}, "restricted"),
]
_DEFAULT_CLASSIFICATION = "internal"


def _infer_classification(name: str) -> str:
    """Return data_classification inferred from keywords in *name*."""
    lower = name.lower()
    for keywords, classification in _CLASSIFICATION_RULES:
        if any(kw in lower for kw in keywords):
            return classification
    return _DEFAULT_CLASSIFICATION


def infer_data_objects(dry_run: bool = False) -> Dict[str, int]:
    """
    Infer DataObject entries from ArchiMate elements whose type contains 'Data'.

    For each matching element check whether a DataObject with the same name
    already exists.  If not, create one with keyword-derived data_classification.

    Args:
        dry_run: When True, compute counts but do not write to the database.

    Returns:
        dict with keys 'inserted', 'skipped', 'total_processed'.
    """
    elements = (
        ArchiMateElement.query
        .filter(ArchiMateElement.type.ilike("%Data%"))
        .all()
    )

    # Build a set of existing DataObject names for O(1) lookup
    existing_names = {
        row[0].lower()
        for row in db.session.query(DataObject.name).all()
        if row[0]
    }

    inserted = 0
    skipped = 0

    for element in elements:
        if not element.name:
            skipped += 1
            continue

        if element.name.lower() in existing_names:
            skipped += 1
            continue

        classification = _infer_classification(element.name)

        if not dry_run:
            data_obj = DataObject(
                name=element.name,
                data_classification=classification,
                archimate_element_id=element.id,
            )
            db.session.add(data_obj)
            existing_names.add(element.name.lower())

        inserted += 1

    if not dry_run and inserted > 0:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("Failed to commit inferred DataObjects")
            raise

    total_processed = inserted + skipped
    logger.info(
        "infer_data_objects complete: inserted=%d skipped=%d total=%d dry_run=%s",
        inserted,
        skipped,
        total_processed,
        dry_run,
    )
    return {"inserted": inserted, "skipped": skipped, "total_processed": total_processed}
