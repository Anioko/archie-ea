"""
Validation result classes for structured error reporting.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ValidationSeverity(Enum):
    """Severity level of validation issues"""

    ERROR = "error"  # Must fix, cannot import
    WARNING = "warning"  # Can import but with modifications
    INFO = "info"  # Informational only


@dataclass
class FieldValidationIssue:
    """Single validation issue for a field"""

    field_name: str
    message: str
    severity: ValidationSeverity
    original_value: Any = None
    suggested_value: Any = None
    row_number: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            "field": self.field_name,
            "message": self.message,
            "severity": self.severity.value,
            "original_value": str(self.original_value) if self.original_value is not None else None,
            "suggested_value": str(self.suggested_value)
            if self.suggested_value is not None
            else None,
            "row": self.row_number,
        }


@dataclass
class RowValidationResult:
    """Validation result for a single row"""

    row_number: int
    is_valid: bool = True
    issues: List[FieldValidationIssue] = field(default_factory=list)
    normalized_data: Dict[str, Any] = field(default_factory=dict)
    original_data: Dict[str, Any] = field(default_factory=dict)

    def add_error(
        self, field_name: str, message: str, original_value: Any = None, suggested_value: Any = None
    ):
        """Add an error issue"""
        self.issues.append(
            FieldValidationIssue(
                field_name=field_name,
                message=message,
                severity=ValidationSeverity.ERROR,
                original_value=original_value,
                suggested_value=suggested_value,
                row_number=self.row_number,
            )
        )
        self.is_valid = False

    def add_warning(
        self, field_name: str, message: str, original_value: Any = None, suggested_value: Any = None
    ):
        """Add a warning issue"""
        self.issues.append(
            FieldValidationIssue(
                field_name=field_name,
                message=message,
                severity=ValidationSeverity.WARNING,
                original_value=original_value,
                suggested_value=suggested_value,
                row_number=self.row_number,
            )
        )

    def add_info(
        self, field_name: str, message: str, original_value: Any = None, suggested_value: Any = None
    ):
        """Add an info issue"""
        self.issues.append(
            FieldValidationIssue(
                field_name=field_name,
                message=message,
                severity=ValidationSeverity.INFO,
                original_value=original_value,
                suggested_value=suggested_value,
                row_number=self.row_number,
            )
        )

    def get_errors(self) -> List[FieldValidationIssue]:
        """Get only error-level issues"""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    def get_warnings(self) -> List[FieldValidationIssue]:
        """Get only warning-level issues"""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def get_infos(self) -> List[FieldValidationIssue]:
        """Get only info-level issues"""
        return [i for i in self.issues if i.severity == ValidationSeverity.INFO]

    def to_dict(self) -> Dict:
        return {
            "row": self.row_number,
            "valid": self.is_valid,
            "error_count": len(self.get_errors()),
            "warning_count": len(self.get_warnings()),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class ImportValidationResult:
    """Complete validation result for an import operation"""

    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    rows_with_warnings: int = 0
    row_results: List[RowValidationResult] = field(default_factory=list)
    global_issues: List[FieldValidationIssue] = field(default_factory=list)
    validation_mode: str = "strict"  # "strict" or "lenient"

    @property
    def is_valid(self) -> bool:
        """Check if entire import is valid (no errors in strict mode)"""
        if self.validation_mode == "strict":
            return self.invalid_rows == 0
        return True  # Lenient mode always allows import

    @property
    def all_errors(self) -> List[FieldValidationIssue]:
        """Get all errors across all rows"""
        errors = list(self.global_issues)
        for row in self.row_results:
            errors.extend(row.get_errors())
        return errors

    @property
    def all_warnings(self) -> List[FieldValidationIssue]:
        """Get all warnings across all rows"""
        warnings = []
        for row in self.row_results:
            warnings.extend(row.get_warnings())
        return warnings

    def add_row_result(self, row_result: RowValidationResult):
        """Add a row validation result"""
        self.row_results.append(row_result)
        self.total_rows += 1
        if row_result.is_valid:
            self.valid_rows += 1
        else:
            self.invalid_rows += 1
        if row_result.get_warnings():
            self.rows_with_warnings += 1

    def add_global_error(self, field_name: str, message: str):
        """Add a global validation error (not row-specific)"""
        self.global_issues.append(
            FieldValidationIssue(
                field_name=field_name, message=message, severity=ValidationSeverity.ERROR
            )
        )

    def add_global_warning(self, field_name: str, message: str):
        """Add a global validation warning (not row-specific)"""
        self.global_issues.append(
            FieldValidationIssue(
                field_name=field_name, message=message, severity=ValidationSeverity.WARNING
            )
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON response"""
        return {
            "valid": self.is_valid,
            "mode": self.validation_mode,
            "summary": {
                "total_rows": self.total_rows,
                "valid_rows": self.valid_rows,
                "invalid_rows": self.invalid_rows,
                "rows_with_warnings": self.rows_with_warnings,
                "total_errors": len(self.all_errors),
                "total_warnings": len(self.all_warnings),
            },
            "global_issues": [i.to_dict() for i in self.global_issues],
            "row_details": [r.to_dict() for r in self.row_results[:100]],  # Limit for performance
            "errors_by_field": self._group_by_field(self.all_errors),
            "warnings_by_field": self._group_by_field(self.all_warnings),
        }

    def _group_by_field(self, issues: List[FieldValidationIssue]) -> Dict[str, List[Dict]]:
        """Group issues by field name for summary"""
        grouped: Dict[str, List[Dict]] = {}
        for issue in issues:
            if issue.field_name not in grouped:
                grouped[issue.field_name] = []
            grouped[issue.field_name].append(
                {
                    "row": issue.row_number,
                    "message": issue.message,
                    "original": str(issue.original_value)
                    if issue.original_value is not None
                    else None,
                }
            )
        return grouped

    def to_csv_report(self) -> str:
        """Generate CSV error report for download"""
        lines = ["Row,Field,Severity,Message,Original Value,Suggested Value"]
        for issue in self.all_errors + self.all_warnings:
            row = issue.row_number if issue.row_number else ""
            orig = str(issue.original_value).replace('"', '""') if issue.original_value else ""
            sugg = str(issue.suggested_value).replace('"', '""') if issue.suggested_value else ""
            msg = issue.message.replace('"', '""')
            lines.append(
                f'{row},"{issue.field_name}","{issue.severity.value}",' f'"{msg}","{orig}","{sugg}"'
            )
        return "\n".join(lines)

    def get_error_summary_text(self) -> str:
        """Get human-readable error summary"""
        if self.is_valid and not self.all_warnings:
            return "All rows validated successfully."

        parts = []
        if self.invalid_rows > 0:
            parts.append(f"{self.invalid_rows} row(s) with errors")
        if self.rows_with_warnings > 0:
            parts.append(f"{self.rows_with_warnings} row(s) with warnings")

        # Group errors by field
        error_counts = {}
        for error in self.all_errors:
            error_counts[error.field_name] = error_counts.get(error.field_name, 0) + 1

        if error_counts:
            field_summary = ", ".join(
                f"{field}: {count}"
                for field, count in sorted(error_counts.items(), key=lambda x: -x[1])[:5]
            )
            parts.append(f"Top error fields: {field_summary}")

        return ". ".join(parts)
