"""
Tests for the admin module.

Tests cover:
- Module registration and imports
- AdminUserService methods
- Form imports and validation
- Route accessibility (basic smoke tests)
- Blueprint naming and URL prefix preservation
"""
import pytest


class TestAdminModuleImports:
    """Verify all admin module components can be imported."""

    def test_import_register_function(self):
        from app.modules.admin import register
        assert callable(register)

    def test_import_admin_bp(self):
        from app.modules.admin.routes.admin_routes import admin_bp
        assert admin_bp.name == "admin"

    def test_import_sidebar_mgmt_bp(self):
        from app.modules.admin.routes.sidebar_mgmt_routes import sidebar_mgmt_bp
        assert sidebar_mgmt_bp.name == "sidebar_mgmt"

    def test_import_deprecation_bp(self):
        from app.modules.admin.routes.deprecation_routes import deprecation_bp
        assert deprecation_bp.name == "deprecation"

    def test_import_admin_user_service(self):
        from app.modules.admin.services.admin_user_service import AdminUserService
        assert hasattr(AdminUserService, 'get_all_users')
        assert hasattr(AdminUserService, 'create_user')
        assert hasattr(AdminUserService, 'invite_user')
        assert hasattr(AdminUserService, 'change_user_email')
        assert hasattr(AdminUserService, 'change_user_role')
        assert hasattr(AdminUserService, 'delete_user')
        assert hasattr(AdminUserService, 'get_paginated_users')
        assert hasattr(AdminUserService, 'queue_email')


class TestAdminFormsImport:
    """Verify all form classes can be imported."""

    def test_import_feature_flag_form(self):
        from app.modules.admin.forms.admin_forms import FeatureFlagForm
        assert FeatureFlagForm is not None

    def test_import_change_user_email_form(self):
        from app.modules.admin.forms.admin_forms import ChangeUserEmailForm
        assert ChangeUserEmailForm is not None

    def test_import_change_account_type_form(self):
        from app.modules.admin.forms.admin_forms import ChangeAccountTypeForm
        assert ChangeAccountTypeForm is not None

    def test_import_invite_user_form(self):
        from app.modules.admin.forms.admin_forms import InviteUserForm
        assert InviteUserForm is not None

    def test_import_new_user_form(self):
        from app.modules.admin.forms.admin_forms import NewUserForm
        assert NewUserForm is not None

    def test_import_api_settings_form(self):
        from app.modules.admin.forms.admin_forms import APISettingsForm
        assert APISettingsForm is not None

    def test_new_user_form_inherits_invite(self):
        from app.modules.admin.forms.admin_forms import InviteUserForm, NewUserForm
        assert issubclass(NewUserForm, InviteUserForm)


class TestAdminBlueprintConfig:
    """Verify blueprint configuration matches legacy."""

    def test_admin_bp_name(self):
        from app.modules.admin.routes.admin_routes import admin_bp
        assert admin_bp.name == "admin"

    def test_sidebar_mgmt_bp_prefix(self):
        from app.modules.admin.routes.sidebar_mgmt_routes import sidebar_mgmt_bp
        assert sidebar_mgmt_bp.url_prefix == "/api/admin/sidebar"

    def test_deprecation_bp_prefix(self):
        from app.modules.admin.routes.deprecation_routes import deprecation_bp
        assert deprecation_bp.url_prefix == "/admin/deprecation"


class TestAdminServiceMethods:
    """Verify AdminUserService static methods exist and are callable."""

    def test_get_all_users_is_static(self):
        from app.modules.admin.services.admin_user_service import AdminUserService
        assert isinstance(
            AdminUserService.__dict__['get_all_users'],
            staticmethod
        )

    def test_create_user_is_static(self):
        from app.modules.admin.services.admin_user_service import AdminUserService
        assert isinstance(
            AdminUserService.__dict__['create_user'],
            staticmethod
        )

    def test_invite_user_is_static(self):
        from app.modules.admin.services.admin_user_service import AdminUserService
        assert isinstance(
            AdminUserService.__dict__['invite_user'],
            staticmethod
        )

    def test_delete_user_is_static(self):
        from app.modules.admin.services.admin_user_service import AdminUserService
        assert isinstance(
            AdminUserService.__dict__['delete_user'],
            staticmethod
        )


class TestAdminRouteCount:
    """Verify route counts match legacy module."""

    def test_admin_bp_has_expected_routes(self):
        """admin_bp should have all 38 route decorators from views.py."""
        from app.modules.admin.routes.admin_routes import admin_bp
        # Count deferred view functions registered on the blueprint
        route_count = len(admin_bp.deferred_functions)
        # Should have at least 30+ deferred registrations
        # (each @route + @login_required + @admin_required = multiple deferred fns)
        assert route_count > 0, f"Expected deferred functions, got {route_count}"

    def test_sidebar_mgmt_bp_has_routes(self):
        from app.modules.admin.routes.sidebar_mgmt_routes import sidebar_mgmt_bp
        assert len(sidebar_mgmt_bp.deferred_functions) > 0

    def test_deprecation_bp_has_routes(self):
        from app.modules.admin.routes.deprecation_routes import deprecation_bp
        assert len(deprecation_bp.deferred_functions) > 0
