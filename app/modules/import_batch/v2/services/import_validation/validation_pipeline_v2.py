"""
Multi-layer validation pipeline for ApplicationComponent imports.
"""

from typing import Any, Dict, List, Optional

from .business_rules import BusinessRuleValidator, CrossRecordValidator
from .validation_result import (
    FieldValidationIssue,
    ImportValidationResult,
    RowValidationResult,
    ValidationSeverity,
)
from .validation_schemas import APPLICATION_COMPONENT_SCHEMA, FieldSchema, FieldType
from .value_normalizer import ValueNormalizer


class ValidationPipeline:
    """
    Multi-layer validation pipeline.

    Layer 1: Structural validation (types, lengths, required fields)
    Layer 2: Enum/value validation with smart mapping
    Layer 3: Business rules validation
    Layer 4: Cross-record consistency
    """

    def __init__(self, mode: str = "strict"):
        """
        Initialize validation pipeline.

        Args:
            mode: "strict" (reject invalid rows) or "lenient" (warn but import with defaults)
        """
        self.mode = mode
        self.schema = APPLICATION_COMPONENT_SCHEMA
        self.normalizer = ValueNormalizer()

    def validate_import(self, rows: List[Dict[str, Any]]) -> ImportValidationResult:
        """
        Validate all rows through the pipeline.

        Args:
            rows: List of row dictionaries from import file

        Returns:
            ImportValidationResult with all validation details
        """
        result = ImportValidationResult(validation_mode=self.mode)

        if not rows:
            result.add_global_warning("data", "No rows to validate")
            return result

        # Validate each row through layers 1 - 3
        for idx, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
            row_result = self._validate_row(row, idx)
            result.add_row_result(row_result)

        # Layer 4: Cross-record consistency
        cross_issues = CrossRecordValidator.validate_batch(
            [r.normalized_data for r in result.row_results]
        )
        for row_num, field_name, message in cross_issues:
            # Find the row result and add the issue
            for row_result in result.row_results:
                if row_result.row_number == row_num:
                    row_result.add_warning(field_name, message)
                    break

        return result

    def _validate_row(self, row: Dict[str, Any], row_number: int) -> RowValidationResult:
        """Validate a single row through layers 1 - 3"""
        row_result = RowValidationResult(row_number=row_number, original_data=dict(row))
        normalized_data: Dict[str, Any] = {}

        # Layer 1 & 2: Field-level validation
        for field_name, value in row.items():
            # Skip empty field names
            if not field_name or not str(field_name).strip():
                continue

            field_name_clean = str(field_name).strip()
            schema = self.schema.get(field_name_clean)

            if schema is None:
                # Unknown field - pass through without validation
                normalized_data[field_name_clean] = value
                continue

            # Normalize and validate
            normalized_value, warning = self.normalizer.normalize_value(
                value, field_name_clean, schema
            )

            # Check if normalization indicates an error
            if (
                warning
                and normalized_value is None
                and value
                and not ValueNormalizer.is_null_value(value)
            ):
                # Failed to normalize - this is an error
                if self.mode == "strict":
                    row_result.add_error(
                        field_name_clean,
                        warning,
                        original_value=value,
                        suggested_value=schema.default_value,
                    )
                    # In strict mode, use None for invalid enum values
                    normalized_value = None
                else:
                    # In lenient mode, warn and use default
                    row_result.add_warning(
                        field_name_clean,
                        warning,
                        original_value=value,
                        suggested_value=schema.default_value,
                    )
                    normalized_value = schema.default_value
            elif warning and normalized_value is not None:
                # Normalization succeeded with modification - this is a warning
                row_result.add_warning(
                    field_name_clean,
                    warning,
                    original_value=value,
                    suggested_value=normalized_value,
                )

            # Validate constraints
            self._validate_constraints(field_name_clean, normalized_value, schema, row_result)

            normalized_data[field_name_clean] = normalized_value

        # Check required fields
        self._validate_required_fields(normalized_data, row_result)

        row_result.normalized_data = normalized_data

        # Layer 3: Business rules
        BusinessRuleValidator.validate_row(normalized_data, row_result)

        return row_result

    def _validate_constraints(
        self, field_name: str, value: Any, schema: FieldSchema, row_result: RowValidationResult
    ):
        """Validate field constraints (length, range, etc.)"""
        if value is None:
            return

        # Length constraints for strings
        if schema.field_type in [FieldType.STRING, FieldType.URL, FieldType.EMAIL]:
            if isinstance(value, str):
                if schema.min_length and len(value) < schema.min_length:
                    row_result.add_error(
                        field_name,
                        f"Value too short (min {schema.min_length} characters)",
                        original_value=value,
                    )

        # Range constraints for numbers
        if schema.field_type in [FieldType.INTEGER, FieldType.FLOAT]:
            if isinstance(value, (int, float)):
                if schema.min_value is not None and value < schema.min_value:
                    row_result.add_error(
                        field_name,
                        f"Value {value} below minimum {schema.min_value}",
                        original_value=value,
                    )
                if schema.max_value is not None and value > schema.max_value:
                    row_result.add_error(
                        field_name,
                        f"Value {value} above maximum {schema.max_value}",
                        original_value=value,
                    )

    def _validate_required_fields(self, data: Dict[str, Any], row_result: RowValidationResult):
        """Validate that required fields are present"""
        for field_name, schema in self.schema.items():
            if schema.required:
                value = data.get(field_name)
                if value is None or (isinstance(value, str) and not value.strip()):
                    row_result.add_error(
                        field_name, f"Required field '{field_name}' is missing or empty"
                    )
