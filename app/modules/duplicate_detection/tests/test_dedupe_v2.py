"""
Tests for the duplicate_detection v2 module.

Covers:
- Module imports and blueprint structure
- Blueprint names match v1 for url_for compatibility
- Schema validation (6 schemas)
- Utility functions (confidence_level, risk_level, safe_threshold, truncate_description, aggregate_scores)
- Route coverage (unified_duplicate, ai)
- Compat wrapper infrastructure (stats tracking)
"""
import pytest


# ============================================================================
# 1. Imports
# ============================================================================


class TestDedupeV2Imports:
    """Verify all v2 submodules and blueprints are importable."""

    def test_v2_module_imports(self):
        from app.modules.duplicate_detection.v2 import register
        assert callable(register)

    def test_v2_blueprint_imports(self):
        from app.modules.duplicate_detection.v2.routes import unified_duplicate_bp_v2, ai_dedupe_bp_v2
        assert unified_duplicate_bp_v2 is not None
        assert ai_dedupe_bp_v2 is not None

    def test_unified_duplicate_bp_has_correct_name(self):
        from app.modules.duplicate_detection.v2.routes import unified_duplicate_bp_v2
        assert unified_duplicate_bp_v2.name == "unified_duplicate"

    def test_ai_dedupe_bp_has_correct_name(self):
        from app.modules.duplicate_detection.v2.routes import ai_dedupe_bp_v2
        assert ai_dedupe_bp_v2.name == "ai"


# ============================================================================
# 2. Schemas
# ============================================================================


class TestDedupeV2Schemas:
    """Test declarative validation schemas."""

    def test_detection_run_schema_valid(self):
        from app.modules.duplicate_detection.v2.schemas import DetectionRunSchema
        assert DetectionRunSchema.validate({}) == []

    def test_detection_run_schema_valid_with_strategy(self):
        from app.modules.duplicate_detection.v2.schemas import DetectionRunSchema
        assert DetectionRunSchema.validate({"strategy": "hybrid", "similarity_threshold": 0.7}) == []

    def test_detection_run_schema_invalid_strategy(self):
        from app.modules.duplicate_detection.v2.schemas import DetectionRunSchema
        errors = DetectionRunSchema.validate({"strategy": "invalid"})
        assert any("strategy" in e.lower() for e in errors)

    def test_detection_run_schema_invalid_threshold(self):
        from app.modules.duplicate_detection.v2.schemas import DetectionRunSchema
        errors = DetectionRunSchema.validate({"similarity_threshold": 2.0})
        assert any("threshold" in e.lower() for e in errors)

    def test_bulk_delete_schema_valid(self):
        from app.modules.duplicate_detection.v2.schemas import BulkDeleteSchema
        assert BulkDeleteSchema.validate({"group_selections": {"1": 2}}) == []

    def test_bulk_delete_schema_missing(self):
        from app.modules.duplicate_detection.v2.schemas import BulkDeleteSchema
        errors = BulkDeleteSchema.validate({})
        assert any("group_selections" in e for e in errors)

    def test_bulk_delete_schema_empty(self):
        from app.modules.duplicate_detection.v2.schemas import BulkDeleteSchema
        errors = BulkDeleteSchema.validate({"group_selections": {}})
        assert any("non-empty" in e for e in errors)

    def test_ai_detect_schema_valid(self):
        from app.modules.duplicate_detection.v2.schemas import AIDetectSchema
        assert AIDetectSchema.validate({"strategy": "ai_enhanced", "threshold": 0.65}) == []

    def test_ai_detect_schema_invalid_strategy(self):
        from app.modules.duplicate_detection.v2.schemas import AIDetectSchema
        errors = AIDetectSchema.validate({"strategy": "bad"})
        assert any("strategy" in e.lower() for e in errors)

    def test_feedback_schema_valid(self):
        from app.modules.duplicate_detection.v2.schemas import FeedbackSchema
        assert FeedbackSchema.validate({"duplicate_id": 1, "action": "accept", "confidence": 85}) == []

    def test_feedback_schema_missing_fields(self):
        from app.modules.duplicate_detection.v2.schemas import FeedbackSchema
        errors = FeedbackSchema.validate({})
        assert len(errors) >= 3

    def test_feedback_schema_invalid_action(self):
        from app.modules.duplicate_detection.v2.schemas import FeedbackSchema
        errors = FeedbackSchema.validate({"duplicate_id": 1, "action": "bad", "confidence": 50})
        assert any("action" in e.lower() for e in errors)

    def test_feedback_schema_invalid_confidence(self):
        from app.modules.duplicate_detection.v2.schemas import FeedbackSchema
        errors = FeedbackSchema.validate({"duplicate_id": 1, "action": "accept", "confidence": 200})
        assert any("confidence" in e.lower() for e in errors)

    def test_find_similar_schema_valid(self):
        from app.modules.duplicate_detection.v2.schemas import FindSimilarSchema
        assert FindSimilarSchema.validate({"method": "fast"}) == []

    def test_find_similar_schema_invalid_method(self):
        from app.modules.duplicate_detection.v2.schemas import FindSimilarSchema
        errors = FindSimilarSchema.validate({"method": "bad"})
        assert any("method" in e.lower() for e in errors)

    def test_simple_detection_api_schema_valid(self):
        from app.modules.duplicate_detection.v2.schemas import SimpleDetectionAPISchema
        assert SimpleDetectionAPISchema.validate({"method": "hybrid"}) == []

    def test_schema_rejects_non_dict(self):
        from app.modules.duplicate_detection.v2.schemas import DetectionRunSchema
        errors = DetectionRunSchema.validate("not a dict")
        assert any("JSON object" in e for e in errors)


# ============================================================================
# 3. Utils
# ============================================================================


class TestDedupeV2Utils:
    """Test utility helper functions."""

    def test_confidence_level_high(self):
        from app.modules.duplicate_detection.v2.utils import confidence_level
        assert confidence_level(0.9) == "high"

    def test_confidence_level_medium(self):
        from app.modules.duplicate_detection.v2.utils import confidence_level
        assert confidence_level(0.7) == "medium"

    def test_confidence_level_low(self):
        from app.modules.duplicate_detection.v2.utils import confidence_level
        assert confidence_level(0.3) == "low"

    def test_risk_level_high(self):
        from app.modules.duplicate_detection.v2.utils import risk_level
        assert risk_level(15, 0) == "high"

    def test_risk_level_high_users(self):
        from app.modules.duplicate_detection.v2.utils import risk_level
        assert risk_level(0, 600) == "high"

    def test_risk_level_medium(self):
        from app.modules.duplicate_detection.v2.utils import risk_level
        assert risk_level(7, 0) == "medium"

    def test_risk_level_low(self):
        from app.modules.duplicate_detection.v2.utils import risk_level
        assert risk_level(2, 50) == "low"

    def test_safe_threshold_normal(self):
        from app.modules.duplicate_detection.v2.utils import safe_threshold
        assert safe_threshold(0.7) == 0.7

    def test_safe_threshold_clamped_high(self):
        from app.modules.duplicate_detection.v2.utils import safe_threshold
        assert safe_threshold(2.0) == 1.0

    def test_safe_threshold_clamped_low(self):
        from app.modules.duplicate_detection.v2.utils import safe_threshold
        assert safe_threshold(-0.5) == 0.0

    def test_safe_threshold_invalid(self):
        from app.modules.duplicate_detection.v2.utils import safe_threshold
        assert safe_threshold("abc") == 0.5

    def test_truncate_description_short(self):
        from app.modules.duplicate_detection.v2.utils import truncate_description
        assert truncate_description("short") == "short"

    def test_truncate_description_long(self):
        from app.modules.duplicate_detection.v2.utils import truncate_description
        result = truncate_description("a" * 200, max_len=100)
        assert len(result) == 103  # 100 + "..."
        assert result.endswith("...")

    def test_truncate_description_none(self):
        from app.modules.duplicate_detection.v2.utils import truncate_description
        assert truncate_description(None) is None

    def test_aggregate_scores_normal(self):
        from app.modules.duplicate_detection.v2.utils import aggregate_scores
        result = aggregate_scores([0.9, 0.7, 0.4])
        assert result["distribution"]["high"] == 1
        assert result["distribution"]["medium"] == 1
        assert result["distribution"]["low"] == 1
        assert result["min_confidence"] == 0.4
        assert result["max_confidence"] == 0.9

    def test_aggregate_scores_empty(self):
        from app.modules.duplicate_detection.v2.utils import aggregate_scores
        result = aggregate_scores([])
        assert result["avg_confidence"] == 0
        assert result["distribution"]["high"] == 0


# ============================================================================
# 4. Blueprint Structure
# ============================================================================


class TestDedupeV2BlueprintStructure:
    """Verify blueprints have routes registered."""

    def test_unified_duplicate_bp_has_routes(self):
        from app.modules.duplicate_detection.v2.routes import unified_duplicate_bp_v2
        assert len(unified_duplicate_bp_v2.deferred_functions) >= 30

    def test_ai_dedupe_bp_has_routes(self):
        from app.modules.duplicate_detection.v2.routes import ai_dedupe_bp_v2
        assert len(ai_dedupe_bp_v2.deferred_functions) >= 8


# ============================================================================
# 5. Compat Wrappers
# ============================================================================


class TestDedupeCompatWrappers:
    """Test compatibility wrapper infrastructure."""

    def test_compat_module_imports(self):
        from app.compat.duplicate_detection import (
            DedupeCompatStats,
            wrap_legacy_dedupe_bp,
        )
        assert callable(wrap_legacy_dedupe_bp)

    def test_compat_stats_tracking(self):
        from app.compat.duplicate_detection import DedupeCompatStats
        DedupeCompatStats.reset()
        DedupeCompatStats.record("unified_duplicate.simple_dashboard")
        DedupeCompatStats.record("unified_duplicate.simple_dashboard")
        DedupeCompatStats.record("unified_duplicate.enterprise_dashboard")
        stats = DedupeCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 3
        assert stats["endpoints"]["unified_duplicate.simple_dashboard"]["hits"] == 2

    def test_compat_stats_reset(self):
        from app.compat.duplicate_detection import DedupeCompatStats
        DedupeCompatStats.record("test")
        DedupeCompatStats.reset()
        stats = DedupeCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 0
