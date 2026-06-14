"""
Dashboard v2 validation schemas.

Declarative schemas for JSON API endpoints in the dashboard module.
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


class RationalizationScoreSchema(Schema):
    """Schema for triggering rationalization score calculation."""

    required_fields = []
    optional_fields = ["force_recalculate"]


class PortfolioAnalysisSchema(Schema):
    """Schema for portfolio duplicate analysis."""

    required_fields = []
    optional_fields = ["threshold", "force_reanalysis"]


class OptionsAnalysisSchema(Schema):
    """Schema for migration options analysis."""

    required_fields = ["options"]
    optional_fields = ["requirements", "session_id"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors and "options" in data:
            if not isinstance(data["options"], list):
                errors.append("'options' must be a list")
            elif len(data["options"]) == 0:
                errors.append("At least one option is required")
        return errors


class ScoringConfigurationSchema(Schema):
    """Schema for creating/updating scoring configurations."""

    required_fields = ["name"]
    optional_fields = [
        "description", "scope_type", "scope_entity_id", "scope_entity_type",
        "technical_health_weight", "business_value_weight",
        "cost_efficiency_weight", "vendor_risk_weight",
        "eliminate_threshold", "migrate_technical_threshold",
        "migrate_business_threshold", "invest_business_threshold",
        "invest_technical_threshold", "tolerate_min_threshold",
        "is_default",
    ]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            weights = [
                data.get("technical_health_weight", 30),
                data.get("business_value_weight", 35),
                data.get("cost_efficiency_weight", 25),
                data.get("vendor_risk_weight", 10),
            ]
            if sum(weights) != 100:
                errors.append(f"Weights must sum to 100, got {sum(weights)}")
        return errors


class WeightValidationSchema(Schema):
    """Schema for weight validation endpoint."""

    required_fields = []
    optional_fields = [
        "technical_health_weight", "business_value_weight",
        "cost_efficiency_weight", "vendor_risk_weight",
    ]


class AssessmentSubmissionSchema(Schema):
    """Schema for rationalization assessment submission."""

    required_fields = ["application_id"]
    optional_fields = ["responses"]


class OnboardingSchema(Schema):
    """Schema for application onboarding."""

    required_fields = ["name"]
    optional_fields = [
        "description", "type", "lifecycle_status", "annual_cost",
    ]


class ConflictResolutionSchema(Schema):
    """Schema for resolving validation conflicts."""

    required_fields = ["field", "value", "source"]
    optional_fields = ["notes"]


class DashboardGenerationSchema(Schema):
    """Schema for dashboard generation from schema."""

    required_fields = ["model"]
    optional_fields = ["columns", "metrics", "charts"]


class ConsolidationRecommendationSchema(Schema):
    """Schema for generating consolidation recommendations."""

    required_fields = []
    optional_fields = ["min_similarity", "max_recommendations"]
