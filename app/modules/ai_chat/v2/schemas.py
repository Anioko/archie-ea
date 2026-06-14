"""
AI Chat v2 validation schemas.

Declarative schemas for JSON API endpoints in the AI chat module.
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


class ChatMessageSchema(Schema):
    """Schema for sending a chat message."""

    required_fields = ["message"]
    optional_fields = ["session_id", "context", "model", "temperature"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            msg = data.get("message", "")
            if isinstance(msg, str) and len(msg.strip()) == 0:
                errors.append("'message' must not be empty")
            temp = data.get("temperature")
            if temp is not None:
                try:
                    t = float(temp)
                    if not (0.0 <= t <= 2.0):
                        errors.append("Temperature must be between 0.0 and 2.0")
                except (TypeError, ValueError):
                    errors.append("Temperature must be a number")
        return errors


class DataInteractionSchema(Schema):
    """Schema for AI data interaction (CRUD via natural language)."""

    required_fields = ["query"]
    optional_fields = ["domain", "session_id", "dry_run"]


class GapDetectionSchema(Schema):
    """Schema for AI gap detection analysis."""

    required_fields = []
    optional_fields = ["scope", "domain", "threshold"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            threshold = data.get("threshold")
            if threshold is not None:
                try:
                    t = float(threshold)
                    if not (0.0 <= t <= 1.0):
                        errors.append("Threshold must be between 0.0 and 1.0")
                except (TypeError, ValueError):
                    errors.append("Threshold must be a number")
        return errors


class AIAssistanceSchema(Schema):
    """Schema for AI assistance requests."""

    required_fields = ["context_type"]
    optional_fields = ["entity_id", "question", "format"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            ctx = data.get("context_type")
            valid_types = ["application", "capability", "vendor", "architecture", "general"]
            if ctx and ctx not in valid_types:
                errors.append(f"Invalid context_type. Must be one of: {valid_types}")
        return errors


class FeedbackSchema(Schema):
    """Schema for chat feedback submission."""

    required_fields = ["message_id", "rating"]
    optional_fields = ["comment"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            rating = data.get("rating")
            if rating is not None:
                try:
                    r = int(rating)
                    if r not in (1, -1):
                        errors.append("Rating must be 1 (thumbs up) or -1 (thumbs down)")
                except (TypeError, ValueError):
                    errors.append("Rating must be an integer")
        return errors


class SessionConfigSchema(Schema):
    """Schema for configuring a chat session."""

    required_fields = []
    optional_fields = ["model", "temperature", "max_tokens", "system_prompt"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            max_tokens = data.get("max_tokens")
            if max_tokens is not None:
                try:
                    mt = int(max_tokens)
                    if mt < 1 or mt > 32000:
                        errors.append("max_tokens must be between 1 and 32000")
                except (TypeError, ValueError):
                    errors.append("max_tokens must be an integer")
        return errors
