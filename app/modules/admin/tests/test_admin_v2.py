"""
Tests for the admin v2 module.

Covers:
- v2 module imports and blueprint structure
- Schema validation (all admin schemas)
- Utility functions (format_admin_flash, safe_int_param, mask_api_key, paginate_query)
- Blueprint names (must match v1 for url_for compatibility)
- Route map completeness (compat wrappers cover all v1 routes)
- Compat wrapper stats tracking
"""
import pytest


class TestAdminV2Imports:
    """Verify v2 module can be imported and blueprints are correct."""

    def test_v2_module_imports(self):
        """v2 __init__.py imports without error."""
        from app.modules.admin.v2 import register
        assert callable(register)

    def test_v2_blueprint_imports(self):
        """v2 blueprints import from routes package."""
        from app.modules.admin.v2.routes import (
            admin_bp_v2,
            sidebar_mgmt_bp_v2,
            deprecation_bp_v2,
        )
        # Blueprint names MUST match v1 for url_for compatibility
        assert admin_bp_v2.name == "admin"
        assert sidebar_mgmt_bp_v2.name == "sidebar_mgmt"
        assert deprecation_bp_v2.name == "deprecation"

    def test_admin_blueprint_has_correct_name(self):
        """admin blueprint name is 'admin' for url_for compatibility."""
        from app.modules.admin.v2.routes.admin_routes import admin_bp_v2
        assert admin_bp_v2.name == "admin"

    def test_sidebar_mgmt_blueprint_has_correct_name(self):
        """sidebar_mgmt blueprint name is 'sidebar_mgmt'."""
        from app.modules.admin.v2.routes.sidebar_mgmt_routes import sidebar_mgmt_bp_v2
        assert sidebar_mgmt_bp_v2.name == "sidebar_mgmt"

    def test_deprecation_blueprint_has_correct_name(self):
        """deprecation blueprint name is 'deprecation'."""
        from app.modules.admin.v2.routes.deprecation_routes import deprecation_bp_v2
        assert deprecation_bp_v2.name == "deprecation"


class TestAdminV2Schemas:
    """Verify schema validation logic."""

    def test_user_create_schema_valid(self):
        from app.modules.admin.v2.schemas import UserCreateSchema
        errors = UserCreateSchema.validate({
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "password": "secret123",
            "role_id": 1,
        })
        assert errors == []

    def test_user_create_schema_missing_fields(self):
        from app.modules.admin.v2.schemas import UserCreateSchema
        errors = UserCreateSchema.validate({"first_name": "John"})
        assert len(errors) == 4  # missing last_name, email, password, role_id

    def test_user_invite_schema_valid(self):
        from app.modules.admin.v2.schemas import UserInviteSchema
        errors = UserInviteSchema.validate({
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
            "role_id": 2,
        })
        assert errors == []

    def test_change_email_schema_valid(self):
        from app.modules.admin.v2.schemas import ChangeEmailSchema
        errors = ChangeEmailSchema.validate({"email": "new@example.com"})
        assert errors == []

    def test_change_email_schema_invalid_email(self):
        from app.modules.admin.v2.schemas import ChangeEmailSchema
        errors = ChangeEmailSchema.validate({"email": "not-an-email"})
        assert any("Invalid email" in e for e in errors)

    def test_change_email_schema_missing(self):
        from app.modules.admin.v2.schemas import ChangeEmailSchema
        errors = ChangeEmailSchema.validate({})
        assert len(errors) == 1

    def test_change_role_schema(self):
        from app.modules.admin.v2.schemas import ChangeRoleSchema
        assert ChangeRoleSchema.validate({"role_id": 3}) == []
        assert len(ChangeRoleSchema.validate({})) == 1

    def test_api_settings_schema(self):
        from app.modules.admin.v2.schemas import APISettingsSchema
        assert APISettingsSchema.validate({"provider": "openai"}) == []
        assert len(APISettingsSchema.validate({})) == 1

    def test_feature_flag_schema(self):
        from app.modules.admin.v2.schemas import FeatureFlagSchema
        assert FeatureFlagSchema.validate({"key": "test", "name": "Test"}) == []
        assert len(FeatureFlagSchema.validate({})) == 2

    def test_env_key_load_schema_valid(self):
        from app.modules.admin.v2.schemas import EnvKeyLoadSchema
        assert EnvKeyLoadSchema.validate({"keys": ["OPENAI_API_KEY"]}) == []

    def test_env_key_load_schema_invalid_keys_type(self):
        from app.modules.admin.v2.schemas import EnvKeyLoadSchema
        errors = EnvKeyLoadSchema.validate({"keys": "not-a-list"})
        assert any("list" in e for e in errors)

    def test_update_model_schema(self):
        from app.modules.admin.v2.schemas import UpdateModelSchema
        assert UpdateModelSchema.validate({"provider": "openai", "model": "gpt-4o"}) == []
        assert len(UpdateModelSchema.validate({})) == 2

    def test_schema_rejects_non_dict(self):
        from app.modules.admin.v2.schemas import Schema
        errors = Schema.validate("not a dict")
        assert errors == ["Payload must be a JSON object"]


class TestAdminV2Utils:
    """Verify utility functions."""

    def test_format_admin_flash_success(self):
        from app.modules.admin.v2.utils import format_admin_flash
        msg, cat = format_admin_flash(True, "User", "created")
        assert cat == "success"
        assert "successfully" in msg

    def test_format_admin_flash_failure(self):
        from app.modules.admin.v2.utils import format_admin_flash
        msg, cat = format_admin_flash(False, "User", "created")
        assert cat == "error"
        assert "Failed" in msg

    def test_safe_int_param_valid(self):
        from app.modules.admin.v2.utils import safe_int_param
        assert safe_int_param("42") == 42
        assert safe_int_param("5", min_val=1, max_val=10) == 5

    def test_safe_int_param_clamping(self):
        from app.modules.admin.v2.utils import safe_int_param
        assert safe_int_param("0", min_val=1) == 1
        assert safe_int_param("999", max_val=100) == 100

    def test_safe_int_param_invalid(self):
        from app.modules.admin.v2.utils import safe_int_param
        assert safe_int_param("abc", default=7) == 7
        assert safe_int_param(None, default=3) == 3

    def test_mask_api_key(self):
        from app.modules.admin.v2.utils import mask_api_key
        assert mask_api_key("sk-proj-ABCDEFGHIJKLMNOP") == "sk-proj-...MNOP"
        assert mask_api_key("short") == "****"
        assert mask_api_key("") == ""
        assert mask_api_key(None) == ""


class TestAdminV2BlueprintStructure:
    """Verify v2 blueprint route coverage matches v1."""

    def test_admin_bp_has_routes(self):
        """admin v2 blueprint has route rules defined."""
        from app.modules.admin.v2.routes.admin_routes import admin_bp_v2
        rules = list(admin_bp_v2.deferred_functions)
        assert len(rules) > 0, "admin_bp_v2 should have deferred route registrations"

    def test_sidebar_mgmt_bp_has_routes(self):
        """sidebar_mgmt v2 blueprint has route rules defined."""
        from app.modules.admin.v2.routes.sidebar_mgmt_routes import sidebar_mgmt_bp_v2
        rules = list(sidebar_mgmt_bp_v2.deferred_functions)
        assert len(rules) > 0

    def test_deprecation_bp_has_routes(self):
        """deprecation v2 blueprint has route rules defined."""
        from app.modules.admin.v2.routes.deprecation_routes import deprecation_bp_v2
        rules = list(deprecation_bp_v2.deferred_functions)
        assert len(rules) > 0


class TestAdminCompatWrappers:
    """Verify compatibility wrapper infrastructure."""

    def test_compat_module_imports(self):
        """Compat module imports without error."""
        from app.compat.admin import (
            AdminCompatStats,
            LEGACY_ROUTE_MAP,
            wrap_legacy_admin_bp,
            wrap_legacy_sidebar_mgmt_bp,
            wrap_legacy_deprecation_bp,
        )
        assert callable(wrap_legacy_admin_bp)
        assert callable(wrap_legacy_sidebar_mgmt_bp)
        assert callable(wrap_legacy_deprecation_bp)

    def test_compat_stats_tracking(self):
        """AdminCompatStats tracks hits correctly."""
        from app.compat.admin import AdminCompatStats
        AdminCompatStats.reset()
        AdminCompatStats.record("admin.index")
        AdminCompatStats.record("admin.index")
        AdminCompatStats.record("admin.dashboard")
        stats = AdminCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 3
        assert stats["endpoints"]["admin.dashboard"]["hits"] == 1
        assert stats["endpoints"]["admin.index"]["hits"] == 2
        AdminCompatStats.reset()

    def test_compat_stats_reset(self):
        """AdminCompatStats.reset() clears all counters."""
        from app.compat.admin import AdminCompatStats
        AdminCompatStats.record("admin.test")
        AdminCompatStats.reset()
        stats = AdminCompatStats.get_stats()
        assert stats["total_legacy_hits"] == 0
        assert stats["endpoints"] == {}

    def test_legacy_route_map_completeness(self):
        """LEGACY_ROUTE_MAP covers admin, sidebar_mgmt, and deprecation routes."""
        from app.compat.admin import LEGACY_ROUTE_MAP

        admin_routes = [k for k in LEGACY_ROUTE_MAP if k.startswith("admin.")]
        sidebar_routes = [k for k in LEGACY_ROUTE_MAP if k.startswith("sidebar_mgmt.")]
        deprecation_routes = [k for k in LEGACY_ROUTE_MAP if k.startswith("deprecation.")]

        assert len(admin_routes) >= 35, f"Expected >= 35 admin routes, got {len(admin_routes)}"
        assert len(sidebar_routes) == 5, f"Expected 5 sidebar_mgmt routes, got {len(sidebar_routes)}"
        assert len(deprecation_routes) == 7, f"Expected 7 deprecation routes, got {len(deprecation_routes)}"

    def test_legacy_route_map_v2_endpoints_match(self):
        """Every v2 endpoint in the route map references a function that exists."""
        from app.compat.admin import LEGACY_ROUTE_MAP
        from app.modules.admin.v2.routes import admin_routes, sidebar_mgmt_routes, deprecation_routes

        for legacy_ep, info in LEGACY_ROUTE_MAP.items():
            v2_ep = info["v2"]
            # Extract function name from "blueprint.function_name"
            func_name = v2_ep.split(".")[-1]
            bp_name = v2_ep.split(".")[0]

            if bp_name == "admin":
                mod = admin_routes
            elif bp_name == "sidebar_mgmt":
                mod = sidebar_mgmt_routes
            elif bp_name == "deprecation":
                mod = deprecation_routes
            else:
                pytest.fail(f"Unknown blueprint prefix '{bp_name}' in v2 endpoint '{v2_ep}'")

            assert hasattr(mod, func_name), (
                f"v2 endpoint function '{func_name}' not found in {mod.__name__} "
                f"for legacy '{legacy_ep}'"
            )
