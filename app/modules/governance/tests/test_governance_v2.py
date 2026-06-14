"""
Tests for the governance v2 module.

Covers:
- v2 module imports and register function
- Schema validation (6 schemas)
- Utility functions (severity_badge, compliance_score, priority_sort_key, maturity_label, safe_page_params)
- Compat wrapper infrastructure (stats tracking)
"""
import pytest


# ============================================================================
# 1. Imports
# ============================================================================


class TestGovernanceV2Imports:
    """Verify v2 module is importable."""

    def test_v2_module_imports(self):
        from app.modules.governance.v2 import register
        assert callable(register)

    def test_v2_schemas_importable(self):
        from app.modules.governance.v2.schemas import (
            PolicyCheckSchema,
            ConsolidationEntrySchema,
            ConsolidationBulkSchema,
            CapabilityGovernanceSchema,
            PolicyCreateSchema,
            CapabilityManagementSchema,
        )
        assert callable(PolicyCheckSchema.validate)

    def test_v2_utils_importable(self):
        from app.modules.governance.v2.utils import (
            severity_badge,
            compliance_score,
            priority_sort_key,
            maturity_label,
            safe_page_params,
        )
        assert callable(severity_badge)


# ============================================================================
# 2. Schemas
# ============================================================================


class TestGovernanceV2Schemas:
    """Test declarative validation schemas."""

    def test_policy_check_schema_valid(self):
        from app.modules.governance.v2.schemas import PolicyCheckSchema
        assert PolicyCheckSchema.validate({"policy_id": 1}) == []

    def test_policy_check_schema_missing(self):
        from app.modules.governance.v2.schemas import PolicyCheckSchema
        errors = PolicyCheckSchema.validate({})
        assert any("policy_id" in e for e in errors)

    def test_consolidation_entry_schema_valid(self):
        from app.modules.governance.v2.schemas import ConsolidationEntrySchema
        assert ConsolidationEntrySchema.validate({"application_id": 1, "priority": "high"}) == []

    def test_consolidation_entry_schema_invalid_priority(self):
        from app.modules.governance.v2.schemas import ConsolidationEntrySchema
        errors = ConsolidationEntrySchema.validate({"application_id": 1, "priority": "bad"})
        assert any("priority" in e.lower() for e in errors)

    def test_consolidation_bulk_schema_valid(self):
        from app.modules.governance.v2.schemas import ConsolidationBulkSchema
        assert ConsolidationBulkSchema.validate({"application_ids": [1, 2, 3]}) == []

    def test_consolidation_bulk_schema_empty_list(self):
        from app.modules.governance.v2.schemas import ConsolidationBulkSchema
        errors = ConsolidationBulkSchema.validate({"application_ids": []})
        assert any("non-empty" in e for e in errors)

    def test_consolidation_bulk_schema_missing(self):
        from app.modules.governance.v2.schemas import ConsolidationBulkSchema
        errors = ConsolidationBulkSchema.validate({})
        assert any("application_ids" in e for e in errors)

    def test_capability_governance_schema_valid(self):
        from app.modules.governance.v2.schemas import CapabilityGovernanceSchema
        assert CapabilityGovernanceSchema.validate({"capability_id": 5}) == []

    def test_capability_governance_schema_missing(self):
        from app.modules.governance.v2.schemas import CapabilityGovernanceSchema
        errors = CapabilityGovernanceSchema.validate({})
        assert any("capability_id" in e for e in errors)

    def test_policy_create_schema_valid(self):
        from app.modules.governance.v2.schemas import PolicyCreateSchema
        assert PolicyCreateSchema.validate({"name": "Cost Policy", "policy_type": "cost"}) == []

    def test_policy_create_schema_invalid_type(self):
        from app.modules.governance.v2.schemas import PolicyCreateSchema
        errors = PolicyCreateSchema.validate({"name": "Bad", "policy_type": "bad"})
        assert any("policy_type" in e.lower() for e in errors)

    def test_policy_create_schema_invalid_severity(self):
        from app.modules.governance.v2.schemas import PolicyCreateSchema
        errors = PolicyCreateSchema.validate({"name": "X", "policy_type": "cost", "severity": "bad"})
        assert any("severity" in e.lower() for e in errors)

    def test_capability_management_schema_valid(self):
        from app.modules.governance.v2.schemas import CapabilityManagementSchema
        assert CapabilityManagementSchema.validate({"capability_id": 1, "action": "assess"}) == []

    def test_capability_management_schema_invalid_action(self):
        from app.modules.governance.v2.schemas import CapabilityManagementSchema
        errors = CapabilityManagementSchema.validate({"capability_id": 1, "action": "bad"})
        assert any("action" in e.lower() for e in errors)

    def test_schema_rejects_non_dict(self):
        from app.modules.governance.v2.schemas import PolicyCheckSchema
        errors = PolicyCheckSchema.validate("not a dict")
        assert any("JSON object" in e for e in errors)


# ============================================================================
# 3. Utils
# ============================================================================


class TestGovernanceV2Utils:
    """Test utility helper functions."""

    def test_severity_badge_info(self):
        from app.modules.governance.v2.utils import severity_badge
        result = severity_badge("info")
        assert result["label"] == "Info"
        assert "blue" in result["css_class"]

    def test_severity_badge_warning(self):
        from app.modules.governance.v2.utils import severity_badge
        result = severity_badge("warning")
        assert result["label"] == "Warning"
        assert "yellow" in result["css_class"]

    def test_severity_badge_critical(self):
        from app.modules.governance.v2.utils import severity_badge
        result = severity_badge("critical")
        assert result["label"] == "Critical"
        assert "red" in result["css_class"]

    def test_severity_badge_unknown(self):
        from app.modules.governance.v2.utils import severity_badge
        result = severity_badge("custom")
        assert result["label"] == "Custom"

    def test_compliance_score_no_violations(self):
        from app.modules.governance.v2.utils import compliance_score
        assert compliance_score(0, 10) == 100.0

    def test_compliance_score_some_violations(self):
        from app.modules.governance.v2.utils import compliance_score
        assert compliance_score(3, 10) == 70.0

    def test_compliance_score_no_checks(self):
        from app.modules.governance.v2.utils import compliance_score
        assert compliance_score(0, 0) == 100.0

    def test_priority_sort_key(self):
        from app.modules.governance.v2.utils import priority_sort_key
        assert priority_sort_key("critical") < priority_sort_key("high")
        assert priority_sort_key("high") < priority_sort_key("medium")
        assert priority_sort_key("medium") < priority_sort_key("low")

    def test_priority_sort_key_unknown(self):
        from app.modules.governance.v2.utils import priority_sort_key
        assert priority_sort_key("unknown") == 99

    def test_maturity_label_known(self):
        from app.modules.governance.v2.utils import maturity_label
        assert maturity_label(1) == "Initial"
        assert maturity_label(5) == "Optimizing"

    def test_maturity_label_unknown(self):
        from app.modules.governance.v2.utils import maturity_label
        assert maturity_label(99) == "Level 99"

    def test_safe_page_params_normal(self):
        from app.modules.governance.v2.utils import safe_page_params
        assert safe_page_params(2, 25) == (2, 25)

    def test_safe_page_params_invalid(self):
        from app.modules.governance.v2.utils import safe_page_params
        assert safe_page_params("abc", "xyz") == (1, 20)

    def test_safe_page_params_clamp(self):
        from app.modules.governance.v2.utils import safe_page_params
        p, pp = safe_page_params(0, 500, max_per_page=50)
        assert p == 1
        assert pp == 50


# ============================================================================
# 4. Compat Wrappers
# ============================================================================


class TestGovernanceCompatWrappers:
    """Test compatibility wrapper infrastructure."""

    def test_compat_module_imports(self):
        from app.compat.governance import (
            GovernanceCompatStats,
            wrap_legacy_governance_bp,
        )
        assert callable(wrap_legacy_governance_bp)

    def test_compat_stats_tracking(self):
        from app.compat.governance import GovernanceCompatStats
        GovernanceCompatStats.reset()
        GovernanceCompatStats.record("consolidation_list.index")
        GovernanceCompatStats.record("consolidation_list.index")
        GovernanceCompatStats.record("policy_monitoring.dashboard")
        stats = GovernanceCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 3
        assert stats["endpoints"]["consolidation_list.index"]["hits"] == 2

    def test_compat_stats_reset(self):
        from app.compat.governance import GovernanceCompatStats
        GovernanceCompatStats.record("test")
        GovernanceCompatStats.reset()
        stats = GovernanceCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 0
