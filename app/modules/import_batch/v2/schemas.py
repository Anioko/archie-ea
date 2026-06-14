"""
Import Batch v2 validation schemas.

Declarative schemas for JSON API endpoints in the import batch module.
"""


class Schema:
    """Base schema with simple field validation."""

    required_fields = []
    optional_fields = []

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = []
        if not isinstance(data, dict):
            return ["Payload must be a JSON object"]
        for field in cls.required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        return errors


class CreateJobSchema(Schema):
    """Schema for creating a batch import job (multipart form, not JSON)."""

    required_fields = []
    optional_fields = ["import_type", "description", "auto_approve"]


class ApproveJobSchema(Schema):
    """Schema for approving a batch import job."""

    required_fields = []
    optional_fields = ["notes", "approve_all"]


class RejectJobSchema(Schema):
    """Schema for rejecting a batch import job."""

    required_fields = ["reason"]
    optional_fields = []


class BatchProcessSchema(Schema):
    """Schema for triggering batch processing."""

    required_fields = []
    optional_fields = ["job_ids", "priority", "batch_size"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            job_ids = data.get("job_ids")
            if job_ids is not None and not isinstance(job_ids, list):
                errors.append("'job_ids' must be a list")
            batch_size = data.get("batch_size")
            if batch_size is not None:
                try:
                    bs = int(batch_size)
                    if bs < 1 or bs > 10000:
                        errors.append("batch_size must be between 1 and 10000")
                except (TypeError, ValueError):
                    errors.append("batch_size must be an integer")
        return errors


class UnifiedImportSchema(Schema):
    """Schema for unified import (quick or governed mode)."""

    required_fields = ["mode"]
    optional_fields = ["file_type", "mapping", "options"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            mode = data.get("mode")
            if mode not in ("quick", "governed"):
                errors.append("Invalid mode. Use: quick, governed")
        return errors


class FieldMappingSchema(Schema):
    """Schema for field mapping configuration."""

    required_fields = ["mappings"]
    optional_fields = ["skip_unmapped", "default_values"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            mappings = data.get("mappings")
            if not isinstance(mappings, dict) or len(mappings) == 0:
                errors.append("'mappings' must be a non-empty object")
        return errors
