"""
Main import validator class - public API for validation framework.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.modules.import_batch.v2.services.import_validation.validation_pipeline_v2 import ValidationPipeline
from app.modules.import_batch.v2.services.import_validation.validation_result_v2 import (
    ImportValidationResult,
    RowValidationResult,
)
from app.modules.import_batch.v2.services.import_validation.validation_schemas_v2 import (
    APPLICATION_COMPONENT_SCHEMA,
    BUSINESS_CRITICALITY_VALUES,
    COMPONENT_TYPE_VALUES,
    DEPLOYMENT_STATUS_VALUES,
    LIFECYCLE_STATUS_VALUES,
    get_allowed_values,
)


class ImportValidator:
    """
    Main validator for ApplicationComponent imports.

    Usage:
        validator = ImportValidator(mode="strict")
        result = validator.validate(rows)

        if result.is_valid:
            # Proceed with import using result.get_normalized_data()
            normalized_rows = validator.get_normalized_data(result)
        else:
            # Return errors to user
            return result.to_dict()
    """

    def __init__(self, mode: str = "strict"):
        """
        Initialize validator.

        Args:
            mode: "strict" - reject rows with invalid enum values
                  "lenient" - warn but import with default values
        """
        if mode not in ["strict", "lenient"]:
            raise ValueError("mode must be 'strict' or 'lenient'")

        self.mode = mode
        self.pipeline = ValidationPipeline(mode=mode)

    def validate(self, rows: List[Dict[str, Any]]) -> ImportValidationResult:
        """
        Validate all import rows.

        Args:
            rows: List of row dictionaries from parsed import file

        Returns:
            ImportValidationResult with validation details
        """
        return self.pipeline.validate_import(rows)

    def validate_single_row(
        self, row: Dict[str, Any], row_number: int = 1
    ) -> Tuple[bool, Dict[str, Any], List[Dict]]:
        """
        Validate a single row (useful for streaming validation).

        Args:
            row: Row dictionary
            row_number: Row number for error reporting

        Returns:
            Tuple of (is_valid, normalized_data, issues_list)
        """
        row_result = self.pipeline._validate_row(row, row_number)

        return (
            row_result.is_valid,
            row_result.normalized_data,
            [issue.to_dict() for issue in row_result.issues],
        )

    def get_normalized_data(self, result: ImportValidationResult) -> List[Dict[str, Any]]:
        """
        Extract normalized data from validation result.

        In lenient mode, includes all rows.
        In strict mode, only includes valid rows.

        Returns:
            List of normalized row dictionaries
        """
        if self.mode == "lenient":
            return [row.normalized_data for row in result.row_results]
        else:
            return [row.normalized_data for row in result.row_results if row.is_valid]

    def get_all_normalized_data(self, result: ImportValidationResult) -> List[Dict[str, Any]]:
        """
        Extract all normalized data regardless of validation status.
        Useful for previewing data before import decision.

        Returns:
            List of all normalized row dictionaries
        """
        return [row.normalized_data for row in result.row_results]

    @staticmethod
    def get_valid_enum_values(field_name: str) -> Optional[List[str]]:
        """Get valid enum values for a field"""
        return get_allowed_values(field_name)

    @staticmethod
    def get_field_schema_info() -> Dict[str, Dict]:
        """Get schema information for all fields (useful for frontend)"""
        info = {}
        for name, schema in APPLICATION_COMPONENT_SCHEMA.items():
            info[name] = {
                "type": schema.field_type.value,
                "required": schema.required,
                "max_length": schema.max_length,
                "allowed_values": schema.allowed_values,
                "default": schema.default_value,
                "description": schema.description,
            }
        return info

    @staticmethod
    def get_enum_fields() -> Dict[str, List[str]]:
        """Get all enum fields and their valid values"""
        return {
            "lifecycle_status": LIFECYCLE_STATUS_VALUES,
            "deployment_status": DEPLOYMENT_STATUS_VALUES,
            "component_type": COMPONENT_TYPE_VALUES,
            "business_criticality": BUSINESS_CRITICALITY_VALUES,
        }


def validate_import_data(
    rows: List[Dict[str, Any]], mode: str = "lenient"
) -> Tuple[bool, List[Dict[str, Any]], Dict]:
    """
    Convenience function for validating import data.

    Args:
        rows: List of row dictionaries
        mode: "strict" or "lenient"

    Returns:
        Tuple of (is_valid, normalized_rows, validation_details)
    """
    validator = ImportValidator(mode=mode)
    result = validator.validate(rows)

    normalized_rows = validator.get_normalized_data(result)

    return (result.is_valid, normalized_rows, result.to_dict())
