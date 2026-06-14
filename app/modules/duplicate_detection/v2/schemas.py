"""
Duplicate Detection v2 validation schemas.

Declarative schemas for JSON API endpoints in the duplicate detection module.
"""


class Schema:
    """Base schema with simple field validation."""

    required_fields = []
    optional_fields = []

    @classmethod
    def validate(cls, data: dict) -> list:
        """Validate data against schema. Returns list of error strings."""
        errors = []
        if not isinstance(data, dict):
            return ["Payload must be a JSON object"]
        for field in cls.required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        return errors


class DetectionRunSchema(Schema):
    """Schema for triggering a detection run."""

    required_fields = []
    optional_fields = ["strategy", "similarity_threshold"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            strategy = data.get("strategy")
            if strategy and strategy not in ("fast", "hybrid", "enhanced"):
                errors.append("Invalid strategy. Use: fast, hybrid, enhanced")
            threshold = data.get("similarity_threshold")
            if threshold is not None:
                try:
                    t = float(threshold)
                    if not (0.0 <= t <= 1.0):
                        errors.append("Threshold must be between 0 and 1")
                except (TypeError, ValueError):
                    errors.append("Threshold must be a number")
        return errors


class BulkDeleteSchema(Schema):
    """Schema for bulk delete duplicates."""

    required_fields = ["group_selections"]
    optional_fields = []

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            gs = data.get("group_selections")
            if not isinstance(gs, dict) or len(gs) == 0:
                errors.append("group_selections must be a non-empty object")
        return errors


class AIDetectSchema(Schema):
    """Schema for AI-powered duplicate detection."""

    required_fields = []
    optional_fields = ["strategy", "threshold", "config"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            strategy = data.get("strategy")
            valid = ["ai_enhanced", "semantic_only", "business_aware"]
            if strategy and strategy not in valid:
                errors.append(f"Invalid strategy. Must be one of: {valid}")
            threshold = data.get("threshold")
            if threshold is not None:
                try:
                    t = float(threshold)
                    if not (0.0 <= t <= 1.0):
                        errors.append("Threshold must be between 0.0 and 1.0")
                except (TypeError, ValueError):
                    errors.append("Threshold must be a number")
        return errors


class FeedbackSchema(Schema):
    """Schema for user feedback on AI detection results."""

    required_fields = ["duplicate_id", "action", "confidence"]
    optional_fields = ["notes"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            action = data.get("action")
            if action not in ("accept", "reject", "modify"):
                errors.append("Invalid action. Must be one of: accept, reject, modify")
            confidence = data.get("confidence")
            if confidence is not None:
                try:
                    c = int(confidence)
                    if not (1 <= c <= 100):
                        errors.append("Confidence must be between 1 and 100")
                except (TypeError, ValueError):
                    errors.append("Confidence must be an integer")
        return errors


class FindSimilarSchema(Schema):
    """Schema for find-similar-applications endpoint."""

    required_fields = []
    optional_fields = ["method", "threshold"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            method = data.get("method")
            if method and method not in ("fast", "hybrid", "enhanced"):
                errors.append("Invalid method. Use: fast, hybrid, enhanced")
        return errors


class SimpleDetectionAPISchema(Schema):
    """Schema for simple detection API endpoint."""

    required_fields = []
    optional_fields = ["threshold", "method"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            method = data.get("method")
            if method and method not in ("fast", "hybrid", "enhanced"):
                errors.append("Invalid method. Use: fast, hybrid, enhanced")
        return errors
