"""
Admin v2 validation schemas.

Declarative schemas for JSON API endpoints in the admin module.
Used for request payload validation on API-style routes.
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


class UserCreateSchema(Schema):
    """Schema for admin user creation (JSON API variant)."""

    required_fields = ["first_name", "last_name", "email", "password", "role_id"]
    optional_fields = []


class UserInviteSchema(Schema):
    """Schema for admin user invitation (JSON API variant)."""

    required_fields = ["first_name", "last_name", "email", "role_id"]
    optional_fields = []


class ChangeEmailSchema(Schema):
    """Schema for admin-initiated email change."""

    required_fields = ["email"]
    optional_fields = []

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors and data.get("email"):
            if "@" not in data["email"]:
                errors.append("Invalid email format")
        return errors


class ChangeRoleSchema(Schema):
    """Schema for admin-initiated role change."""

    required_fields = ["role_id"]
    optional_fields = []


class APISettingsSchema(Schema):
    """Schema for API settings creation/update."""

    required_fields = ["provider"]
    optional_fields = [
        "api_key", "enabled", "default_model", "max_tokens",
        "temperature", "jira_url", "jira_email", "hf_model_id",
        "hf_endpoint_url", "custom_endpoint_url", "custom_auth_method",
        "custom_headers",
    ]


class FeatureFlagSchema(Schema):
    """Schema for feature flag creation/update."""

    required_fields = ["key", "name"]
    optional_fields = [
        "description", "feature_type", "state", "enabled",
        "sidebar_label", "sidebar_icon", "routes", "parent_id",
        "sort_order",
    ]


class FeatureFlagToggleSchema(Schema):
    """Schema for feature flag toggle (no fields required — toggle is implicit)."""

    required_fields = []
    optional_fields = []


class SeedTriggerSchema(Schema):
    """Schema for seed trigger."""

    required_fields = []
    optional_fields = ["force"]


class EnvKeyLoadSchema(Schema):
    """Schema for loading environment API keys."""

    required_fields = ["keys"]
    optional_fields = ["update_existing"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors and data.get("keys"):
            if not isinstance(data["keys"], list):
                errors.append("'keys' must be a list of env var names")
        return errors


class UpdateModelSchema(Schema):
    """Schema for quick-updating a provider's default model."""

    required_fields = ["provider", "model"]
    optional_fields = []
