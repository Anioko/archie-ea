"""
Tests for the import_batch v2 module.

Covers:
- v2 module imports and register function
- Schema validation (6 schemas)
- Utility functions (allowed_file, file_size_ok, sanitize_import_error, format_job_status, safe_int_param)
- Compat wrapper infrastructure (stats tracking)
"""
import pytest


# ============================================================================
# 1. Imports
# ============================================================================


class TestImportBatchV2Imports:
    """Verify v2 module is importable."""

    def test_v2_module_imports(self):
        from app.modules.import_batch.v2 import register
        assert callable(register)

    def test_v2_schemas_importable(self):
        from app.modules.import_batch.v2.schemas import (
            CreateJobSchema,
            ApproveJobSchema,
            RejectJobSchema,
            BatchProcessSchema,
            UnifiedImportSchema,
            FieldMappingSchema,
        )
        assert callable(CreateJobSchema.validate)

    def test_v2_utils_importable(self):
        from app.modules.import_batch.v2.utils import (
            allowed_file,
            file_size_ok,
            sanitize_import_error,
            format_job_status,
            safe_int_param,
        )
        assert callable(allowed_file)


# ============================================================================
# 2. Schemas
# ============================================================================


class TestImportBatchV2Schemas:
    """Test declarative validation schemas."""

    def test_create_job_schema_valid(self):
        from app.modules.import_batch.v2.schemas import CreateJobSchema
        assert CreateJobSchema.validate({}) == []

    def test_approve_job_schema_valid(self):
        from app.modules.import_batch.v2.schemas import ApproveJobSchema
        assert ApproveJobSchema.validate({}) == []

    def test_reject_job_schema_valid(self):
        from app.modules.import_batch.v2.schemas import RejectJobSchema
        assert RejectJobSchema.validate({"reason": "Duplicate data"}) == []

    def test_reject_job_schema_missing_reason(self):
        from app.modules.import_batch.v2.schemas import RejectJobSchema
        errors = RejectJobSchema.validate({})
        assert any("reason" in e for e in errors)

    def test_batch_process_schema_valid(self):
        from app.modules.import_batch.v2.schemas import BatchProcessSchema
        assert BatchProcessSchema.validate({"job_ids": [1, 2], "batch_size": 100}) == []

    def test_batch_process_schema_invalid_job_ids(self):
        from app.modules.import_batch.v2.schemas import BatchProcessSchema
        errors = BatchProcessSchema.validate({"job_ids": "not a list"})
        assert any("list" in e for e in errors)

    def test_batch_process_schema_invalid_batch_size(self):
        from app.modules.import_batch.v2.schemas import BatchProcessSchema
        errors = BatchProcessSchema.validate({"batch_size": 99999})
        assert any("batch_size" in e for e in errors)

    def test_unified_import_schema_valid(self):
        from app.modules.import_batch.v2.schemas import UnifiedImportSchema
        assert UnifiedImportSchema.validate({"mode": "quick"}) == []

    def test_unified_import_schema_missing_mode(self):
        from app.modules.import_batch.v2.schemas import UnifiedImportSchema
        errors = UnifiedImportSchema.validate({})
        assert any("mode" in e for e in errors)

    def test_unified_import_schema_invalid_mode(self):
        from app.modules.import_batch.v2.schemas import UnifiedImportSchema
        errors = UnifiedImportSchema.validate({"mode": "bad"})
        assert any("mode" in e.lower() for e in errors)

    def test_field_mapping_schema_valid(self):
        from app.modules.import_batch.v2.schemas import FieldMappingSchema
        assert FieldMappingSchema.validate({"mappings": {"col_a": "name"}}) == []

    def test_field_mapping_schema_empty_mappings(self):
        from app.modules.import_batch.v2.schemas import FieldMappingSchema
        errors = FieldMappingSchema.validate({"mappings": {}})
        assert any("non-empty" in e for e in errors)

    def test_field_mapping_schema_missing_mappings(self):
        from app.modules.import_batch.v2.schemas import FieldMappingSchema
        errors = FieldMappingSchema.validate({})
        assert any("mappings" in e for e in errors)

    def test_schema_rejects_non_dict(self):
        from app.modules.import_batch.v2.schemas import CreateJobSchema
        errors = CreateJobSchema.validate("not a dict")
        assert any("JSON object" in e for e in errors)


# ============================================================================
# 3. Utils
# ============================================================================


class TestImportBatchV2Utils:
    """Test utility helper functions."""

    def test_allowed_file_csv(self):
        from app.modules.import_batch.v2.utils import allowed_file
        assert allowed_file("data.csv") is True

    def test_allowed_file_xlsx(self):
        from app.modules.import_batch.v2.utils import allowed_file
        assert allowed_file("data.xlsx") is True

    def test_allowed_file_json(self):
        from app.modules.import_batch.v2.utils import allowed_file
        assert allowed_file("data.json") is True

    def test_allowed_file_rejected(self):
        from app.modules.import_batch.v2.utils import allowed_file
        assert allowed_file("data.exe") is False

    def test_allowed_file_no_extension(self):
        from app.modules.import_batch.v2.utils import allowed_file
        assert allowed_file("noext") is False

    def test_allowed_file_empty(self):
        from app.modules.import_batch.v2.utils import allowed_file
        assert allowed_file("") is False

    def test_file_size_ok_within_limit(self):
        from app.modules.import_batch.v2.utils import file_size_ok
        assert file_size_ok(1024) is True

    def test_file_size_ok_over_limit(self):
        from app.modules.import_batch.v2.utils import file_size_ok
        assert file_size_ok(100 * 1024 * 1024) is False

    def test_file_size_ok_none(self):
        from app.modules.import_batch.v2.utils import file_size_ok
        assert file_size_ok(None) is True

    def test_sanitize_import_error_strips_paths(self):
        from app.modules.import_batch.v2.utils import sanitize_import_error
        result = sanitize_import_error(Exception("Error at C:\\Users\\test\\file.py line 5"))
        assert "C:\\" not in result
        assert "[path]" in result

    def test_sanitize_import_error_truncates(self):
        from app.modules.import_batch.v2.utils import sanitize_import_error
        result = sanitize_import_error(Exception("x" * 1000))
        assert len(result) <= 500

    def test_format_job_status_pending(self):
        from app.modules.import_batch.v2.utils import format_job_status
        result = format_job_status("pending")
        assert result["label"] == "Pending"
        assert "yellow" in result["css_class"]

    def test_format_job_status_completed(self):
        from app.modules.import_batch.v2.utils import format_job_status
        result = format_job_status("completed")
        assert result["label"] == "Completed"
        assert "green" in result["css_class"]

    def test_format_job_status_unknown(self):
        from app.modules.import_batch.v2.utils import format_job_status
        result = format_job_status("custom_status")
        assert result["label"] == "Custom_Status"

    def test_safe_int_param_normal(self):
        from app.modules.import_batch.v2.utils import safe_int_param
        assert safe_int_param(5) == 5

    def test_safe_int_param_clamp_high(self):
        from app.modules.import_batch.v2.utils import safe_int_param
        assert safe_int_param(99999) == 10000

    def test_safe_int_param_clamp_low(self):
        from app.modules.import_batch.v2.utils import safe_int_param
        assert safe_int_param(0) == 1

    def test_safe_int_param_invalid(self):
        from app.modules.import_batch.v2.utils import safe_int_param
        assert safe_int_param("abc", default=10) == 10


# ============================================================================
# 4. Compat Wrappers
# ============================================================================


class TestImportBatchCompatWrappers:
    """Test compatibility wrapper infrastructure."""

    def test_compat_module_imports(self):
        from app.compat.import_batch import (
            ImportBatchCompatStats,
            wrap_legacy_import_batch_bp,
        )
        assert callable(wrap_legacy_import_batch_bp)

    def test_compat_stats_tracking(self):
        from app.compat.import_batch import ImportBatchCompatStats
        ImportBatchCompatStats.reset()
        ImportBatchCompatStats.record("batch_import_api.create_job")
        ImportBatchCompatStats.record("batch_import_api.create_job")
        ImportBatchCompatStats.record("batch_import_view.dashboard")
        stats = ImportBatchCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 3
        assert stats["endpoints"]["batch_import_api.create_job"]["hits"] == 2

    def test_compat_stats_reset(self):
        from app.compat.import_batch import ImportBatchCompatStats
        ImportBatchCompatStats.record("test")
        ImportBatchCompatStats.reset()
        stats = ImportBatchCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 0
