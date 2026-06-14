"""
Tests for the ai_chat v2 module.

Covers:
- v2 module imports and register function
- Schema validation (6 schemas)
- Utility functions (truncate_message, sanitize_user_input, format_ai_response, safe_temperature, detect_intent)
- Compat wrapper infrastructure (stats tracking)
"""
import pytest


# ============================================================================
# 1. Imports
# ============================================================================


class TestAIChatV2Imports:
    """Verify v2 module is importable."""

    def test_v2_module_imports(self):
        from app.modules.ai_chat.v2 import register
        assert callable(register)

    def test_v2_schemas_importable(self):
        from app.modules.ai_chat.v2.schemas import (
            ChatMessageSchema,
            DataInteractionSchema,
            GapDetectionSchema,
            AIAssistanceSchema,
            FeedbackSchema,
            SessionConfigSchema,
        )
        assert callable(ChatMessageSchema.validate)

    def test_v2_utils_importable(self):
        from app.modules.ai_chat.v2.utils import (
            truncate_message,
            sanitize_user_input,
            format_ai_response,
            safe_temperature,
            detect_intent,
        )
        assert callable(truncate_message)


# ============================================================================
# 2. Schemas
# ============================================================================


class TestAIChatV2Schemas:
    """Test declarative validation schemas."""

    def test_chat_message_schema_valid(self):
        from app.modules.ai_chat.v2.schemas import ChatMessageSchema
        assert ChatMessageSchema.validate({"message": "Hello"}) == []

    def test_chat_message_schema_missing(self):
        from app.modules.ai_chat.v2.schemas import ChatMessageSchema
        errors = ChatMessageSchema.validate({})
        assert any("message" in e for e in errors)

    def test_chat_message_schema_empty(self):
        from app.modules.ai_chat.v2.schemas import ChatMessageSchema
        errors = ChatMessageSchema.validate({"message": "   "})
        assert any("empty" in e for e in errors)

    def test_chat_message_schema_invalid_temp(self):
        from app.modules.ai_chat.v2.schemas import ChatMessageSchema
        errors = ChatMessageSchema.validate({"message": "Hi", "temperature": 5.0})
        assert any("temperature" in e.lower() for e in errors)

    def test_data_interaction_schema_valid(self):
        from app.modules.ai_chat.v2.schemas import DataInteractionSchema
        assert DataInteractionSchema.validate({"query": "List all apps"}) == []

    def test_data_interaction_schema_missing(self):
        from app.modules.ai_chat.v2.schemas import DataInteractionSchema
        errors = DataInteractionSchema.validate({})
        assert any("query" in e for e in errors)

    def test_gap_detection_schema_valid(self):
        from app.modules.ai_chat.v2.schemas import GapDetectionSchema
        assert GapDetectionSchema.validate({"threshold": 0.5}) == []

    def test_gap_detection_schema_invalid_threshold(self):
        from app.modules.ai_chat.v2.schemas import GapDetectionSchema
        errors = GapDetectionSchema.validate({"threshold": 2.0})
        assert any("threshold" in e.lower() for e in errors)

    def test_ai_assistance_schema_valid(self):
        from app.modules.ai_chat.v2.schemas import AIAssistanceSchema
        assert AIAssistanceSchema.validate({"context_type": "application"}) == []

    def test_ai_assistance_schema_invalid_type(self):
        from app.modules.ai_chat.v2.schemas import AIAssistanceSchema
        errors = AIAssistanceSchema.validate({"context_type": "bad"})
        assert any("context_type" in e.lower() for e in errors)

    def test_feedback_schema_valid(self):
        from app.modules.ai_chat.v2.schemas import FeedbackSchema
        assert FeedbackSchema.validate({"message_id": "abc", "rating": 1}) == []

    def test_feedback_schema_invalid_rating(self):
        from app.modules.ai_chat.v2.schemas import FeedbackSchema
        errors = FeedbackSchema.validate({"message_id": "abc", "rating": 5})
        assert any("rating" in e.lower() for e in errors)

    def test_session_config_schema_valid(self):
        from app.modules.ai_chat.v2.schemas import SessionConfigSchema
        assert SessionConfigSchema.validate({"model": "gpt-4", "max_tokens": 4096}) == []

    def test_session_config_schema_invalid_max_tokens(self):
        from app.modules.ai_chat.v2.schemas import SessionConfigSchema
        errors = SessionConfigSchema.validate({"max_tokens": 99999})
        assert any("max_tokens" in e for e in errors)

    def test_schema_rejects_non_dict(self):
        from app.modules.ai_chat.v2.schemas import ChatMessageSchema
        errors = ChatMessageSchema.validate("not a dict")
        assert any("JSON object" in e for e in errors)


# ============================================================================
# 3. Utils
# ============================================================================


class TestAIChatV2Utils:
    """Test utility helper functions."""

    def test_truncate_message_short(self):
        from app.modules.ai_chat.v2.utils import truncate_message
        assert truncate_message("short") == "short"

    def test_truncate_message_long(self):
        from app.modules.ai_chat.v2.utils import truncate_message
        result = truncate_message("a" * 200, max_len=100)
        assert len(result) == 103
        assert result.endswith("...")

    def test_truncate_message_empty(self):
        from app.modules.ai_chat.v2.utils import truncate_message
        assert truncate_message("") == ""

    def test_sanitize_user_input_normal(self):
        from app.modules.ai_chat.v2.utils import sanitize_user_input
        assert sanitize_user_input("Hello world") == "Hello world"

    def test_sanitize_user_input_control_chars(self):
        from app.modules.ai_chat.v2.utils import sanitize_user_input
        result = sanitize_user_input("Hello\x00\x01world")
        assert "\x00" not in result
        assert "Hello" in result

    def test_sanitize_user_input_whitespace(self):
        from app.modules.ai_chat.v2.utils import sanitize_user_input
        result = sanitize_user_input("  Hello     world  ")
        assert result == "Hello  world"

    def test_format_ai_response(self):
        from app.modules.ai_chat.v2.utils import format_ai_response
        result = format_ai_response({"success": True, "response": "Hi", "model": "gpt-4"})
        assert result["success"] is True
        assert result["message"] == "Hi"
        assert result["model"] == "gpt-4"

    def test_format_ai_response_defaults(self):
        from app.modules.ai_chat.v2.utils import format_ai_response
        result = format_ai_response({})
        assert result["success"] is False
        assert result["model"] == "unknown"

    def test_safe_temperature_normal(self):
        from app.modules.ai_chat.v2.utils import safe_temperature
        assert safe_temperature(0.7) == 0.7

    def test_safe_temperature_clamped(self):
        from app.modules.ai_chat.v2.utils import safe_temperature
        assert safe_temperature(5.0) == 2.0
        assert safe_temperature(-1.0) == 0.0

    def test_safe_temperature_invalid(self):
        from app.modules.ai_chat.v2.utils import safe_temperature
        assert safe_temperature("abc") == 0.7

    def test_detect_intent_create(self):
        from app.modules.ai_chat.v2.utils import detect_intent
        assert detect_intent("Create a new application") == "create"

    def test_detect_intent_update(self):
        from app.modules.ai_chat.v2.utils import detect_intent
        assert detect_intent("Update the vendor name") == "update"

    def test_detect_intent_delete(self):
        from app.modules.ai_chat.v2.utils import detect_intent
        assert detect_intent("Delete this record") == "delete"

    def test_detect_intent_query(self):
        from app.modules.ai_chat.v2.utils import detect_intent
        assert detect_intent("Show me all vendors") == "query"

    def test_detect_intent_analyze(self):
        from app.modules.ai_chat.v2.utils import detect_intent
        assert detect_intent("Analyze the portfolio") == "analyze"

    def test_detect_intent_general(self):
        from app.modules.ai_chat.v2.utils import detect_intent
        assert detect_intent("Hello there") == "general"


# ============================================================================
# 4. Compat Wrappers
# ============================================================================


class TestAIChatCompatWrappers:
    """Test compatibility wrapper infrastructure."""

    def test_compat_module_imports(self):
        from app.compat.ai_chat import (
            AIChatCompatStats,
            wrap_legacy_ai_chat_bp,
        )
        assert callable(wrap_legacy_ai_chat_bp)

    def test_compat_stats_tracking(self):
        from app.compat.ai_chat import AIChatCompatStats
        AIChatCompatStats.reset()
        AIChatCompatStats.record("unified_ai_chat.chat")
        AIChatCompatStats.record("unified_ai_chat.chat")
        AIChatCompatStats.record("ai_data_interaction.query")
        stats = AIChatCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 3
        assert stats["endpoints"]["unified_ai_chat.chat"]["hits"] == 2

    def test_compat_stats_reset(self):
        from app.compat.ai_chat import AIChatCompatStats
        AIChatCompatStats.record("test")
        AIChatCompatStats.reset()
        stats = AIChatCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 0
