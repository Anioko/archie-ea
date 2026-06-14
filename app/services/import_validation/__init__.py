"""
Import Validation Framework for ApplicationComponent

This module provides comprehensive data validation for application imports,
including schema validation, value normalization, and business rule enforcement.

Usage:
    from app.services.import_validation import ImportValidator

    # Create validator (mode: "strict" or "lenient")
    validator = ImportValidator(mode="strict")

    # Validate import data
    result = validator.validate(rows)

    if result.is_valid:
        # Get normalized data for import
        normalized_rows = validator.get_normalized_data(result)
        # Proceed with import...
    else:
        # Return validation errors to user
        return jsonify(result.to_dict()), 400

Validation Modes:
    - strict: Rejects rows with invalid enum values, returns errors before import
    - lenient: Normalizes values where possible, uses defaults for invalid values

Validation Layers:
    1. Structural: Data types, field lengths, required fields
    2. Enum/Value: Valid enum values with smart alias mapping
    3. Business Rules: Cross-field dependencies (e.g., dates, criticality)
    4. Cross-Record: Duplicate detection within import file
"""

from .business_rules import BusinessRuleValidator, CrossRecordValidator
from .import_validator import ImportValidator, validate_import_data
from .validation_pipeline import ValidationPipeline
from .validation_result import (
    FieldValidationIssue,
    ImportValidationResult,
    RowValidationResult,
    ValidationSeverity,
)
from .validation_schemas import (
    APPLICATION_COMPONENT_SCHEMA,
    BUSINESS_CRITICALITY_VALUES,
    COMPONENT_TYPE_VALUES,
    DEPLOYMENT_STATUS_VALUES,
    LIFECYCLE_STATUS_VALUES,
    FieldSchema,
    FieldType,
    get_alias_mapping,
    get_allowed_values,
)
from .value_normalizer import ValueNormalizer

__all__ = [
    # Main API
    "ImportValidator",
    "validate_import_data",
    # Result classes
    "ImportValidationResult",
    "RowValidationResult",
    "FieldValidationIssue",
    "ValidationSeverity",
    # Schema definitions
    "FieldSchema",
    "FieldType",
    "APPLICATION_COMPONENT_SCHEMA",
    "LIFECYCLE_STATUS_VALUES",
    "DEPLOYMENT_STATUS_VALUES",
    "COMPONENT_TYPE_VALUES",
    "BUSINESS_CRITICALITY_VALUES",
    "get_allowed_values",
    "get_alias_mapping",
    # Utility classes
    "ValueNormalizer",
    "ValidationPipeline",
    "BusinessRuleValidator",
    "CrossRecordValidator",
]
