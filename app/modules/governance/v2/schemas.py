"""
Governance v2 validation schemas.

Declarative schemas for JSON API endpoints in the governance module.
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


class PolicyCheckSchema(Schema):
    """Schema for running a governance policy check."""

    required_fields = ["policy_id"]
    optional_fields = ["scope", "dry_run"]


class ConsolidationEntrySchema(Schema):
    """Schema for adding an entry to the consolidation list."""

    required_fields = ["application_id"]
    optional_fields = ["priority", "source_type", "source_group_id", "notes"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            priority = data.get("priority")
            if priority and priority not in ("low", "medium", "high", "critical"):
                errors.append("Invalid priority. Use: low, medium, high, critical")
        return errors


class ConsolidationBulkSchema(Schema):
    """Schema for bulk consolidation operations."""

    required_fields = ["application_ids"]
    optional_fields = ["action", "priority"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            ids = data.get("application_ids")
            if not isinstance(ids, list) or len(ids) == 0:
                errors.append("'application_ids' must be a non-empty list")
        return errors


class CapabilityGovernanceSchema(Schema):
    """Schema for capability governance operations."""

    required_fields = ["capability_id"]
    optional_fields = ["action", "notes", "maturity_target"]


class PolicyCreateSchema(Schema):
    """Schema for creating a governance policy."""

    required_fields = ["name", "policy_type"]
    optional_fields = ["description", "severity", "threshold", "enabled"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            policy_type = data.get("policy_type")
            if policy_type and policy_type not in ("compliance", "cost", "risk", "architecture", "custom"):
                errors.append("Invalid policy_type. Use: compliance, cost, risk, architecture, custom")
            severity = data.get("severity")
            if severity and severity not in ("info", "warning", "critical"):
                errors.append("Invalid severity. Use: info, warning, critical")
        return errors


class CapabilityManagementSchema(Schema):
    """Schema for capability management operations."""

    required_fields = ["capability_id", "action"]
    optional_fields = ["target_maturity", "owner", "notes"]

    @classmethod
    def validate(cls, data: dict) -> list:
        errors = super().validate(data)
        if not errors:
            action = data.get("action")
            if action and action not in ("assess", "update", "retire", "promote"):
                errors.append("Invalid action. Use: assess, update, retire, promote")
        return errors
