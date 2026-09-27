"""
Business-rule validation for ApplicationComponent imports.

Layer 3 (per-row rules) and Layer 4 (cross-record consistency).
"""

from typing import Any, Dict, List, Tuple

from .validation_result_v2 import RowValidationResult


class BusinessRuleValidator:
    """Per-row business-rule checks after field-level validation."""

    @staticmethod
    def validate_row(data: Dict[str, Any], row_result: RowValidationResult) -> None:
        """Validate cross-field business rules for a single row."""
        # No business rules defined yet — placeholder for future rules.
        pass


class CrossRecordValidator:
    """Cross-record consistency checks across all rows."""

    @staticmethod
    def validate_batch(
        normalized_data: List[Dict[str, Any]],
    ) -> List[Tuple[int, str, str]]:
        """
        Validate consistency across all records in the batch.

        Returns list of (row_number, field_name, message) for any issues found.
        """
        # No cross-record rules defined yet — placeholder for future rules.
        return []