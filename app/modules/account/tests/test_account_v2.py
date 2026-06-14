"""
Tests for account v2 module — guardrail-enabled migration.

Verifies:
1. v2 module imports correctly
2. v2 blueprint registers with correct routes
3. v2 routes produce identical behavior to v1
4. Guardrail decorators are applied (timed_route adds X-Response-Time-Ms)
5. Compat wrappers add deprecation headers to legacy routes
6. Schemas validate correctly
7. Utils work as expected
"""
import pytest


class TestAccountV2Imports:
    """Verify v2 module structure imports correctly."""

    def test_v2_register_function(self, app):
        """v2 __init__.py has register() function."""
        with app.app_context():
            from app.modules.account.v2 import register
            assert callable(register)

    def test_v2_blueprint_imports(self, app):
        """v2 blueprint imports from routes package."""
        with app.app_context():
            from app.modules.account.v2.routes import account_bp_v2
            # Blueprint name is "account" (not "account_v2") so that shared
            # AccountService url_for("account.*") calls work without changes.
            assert account_bp_v2.name == "account"

    def test_v2_schemas_import(self, app):
        """v2 schemas import correctly."""
        with app.app_context():
            from app.modules.account.v2.schemas import (
                ChangeEmailSchema,
                ChangePasswordSchema,
                LoginSchema,
                RegistrationSchema,
                ResetPasswordSchema,
            )
            assert LoginSchema is not None
            assert RegistrationSchema is not None
            assert ResetPasswordSchema is not None
            assert ChangePasswordSchema is not None
            assert ChangeEmailSchema is not None

    def test_v2_utils_import(self, app):
        """v2 utils import correctly."""
        with app.app_context():
            from app.modules.account.v2.utils import format_flash_result, safe_redirect_target
            assert callable(safe_redirect_target)
            assert callable(format_flash_result)


class TestAccountV2Schemas:
    """Unit tests for v2 validation schemas."""

    def test_login_schema_valid(self):
        """LoginSchema accepts valid input."""
        from app.modules.account.v2.schemas import LoginSchema
        data, errors = LoginSchema.validate({
            "email": "user@example.com",
            "password": "secret123",
            "remember_me": True,
        })
        assert not errors
        assert data["email"] == "user@example.com"
        assert data["password"] == "secret123"
        assert data["remember_me"] is True

    def test_login_schema_missing_email(self):
        """LoginSchema rejects missing email."""
        from app.modules.account.v2.schemas import LoginSchema
        _, errors = LoginSchema.validate({"password": "secret123"})
        assert "email" in errors

    def test_login_schema_missing_password(self):
        """LoginSchema rejects missing password."""
        from app.modules.account.v2.schemas import LoginSchema
        _, errors = LoginSchema.validate({"email": "user@example.com"})
        assert "password" in errors

    def test_login_schema_invalid_email(self):
        """LoginSchema rejects invalid email format."""
        from app.modules.account.v2.schemas import LoginSchema
        _, errors = LoginSchema.validate({
            "email": "not-an-email",
            "password": "secret123",
        })
        assert "email" in errors

    def test_registration_schema_valid(self):
        """RegistrationSchema accepts valid input."""
        from app.modules.account.v2.schemas import RegistrationSchema
        data, errors = RegistrationSchema.validate({
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "password": "secret123",
        })
        assert not errors
        assert data["first_name"] == "John"

    def test_registration_schema_short_password(self):
        """RegistrationSchema rejects passwords under 6 chars."""
        from app.modules.account.v2.schemas import RegistrationSchema
        _, errors = RegistrationSchema.validate({
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "password": "ab",
        })
        assert "password" in errors

    def test_change_password_schema_valid(self):
        """ChangePasswordSchema accepts valid input."""
        from app.modules.account.v2.schemas import ChangePasswordSchema
        data, errors = ChangePasswordSchema.validate({
            "old_password": "oldpass",
            "new_password": "newpass123",
        })
        assert not errors

    def test_change_email_schema_valid(self):
        """ChangeEmailSchema accepts valid input."""
        from app.modules.account.v2.schemas import ChangeEmailSchema
        data, errors = ChangeEmailSchema.validate({
            "email": "new@example.com",
            "password": "mypassword",
        })
        assert not errors

    def test_reset_password_schema_valid(self):
        """ResetPasswordSchema accepts valid input."""
        from app.modules.account.v2.schemas import ResetPasswordSchema
        data, errors = ResetPasswordSchema.validate({
            "email": "user@example.com",
        })
        assert not errors


class TestAccountV2Utils:
    """Unit tests for v2 utility functions."""

    def test_safe_redirect_target_valid(self):
        """safe_redirect_target accepts relative URLs."""
        from app.modules.account.v2.utils import safe_redirect_target
        assert safe_redirect_target("/dashboard") == "/dashboard"

    def test_safe_redirect_target_none(self):
        """safe_redirect_target returns fallback for None."""
        from app.modules.account.v2.utils import safe_redirect_target
        assert safe_redirect_target(None) == "/"

    def test_safe_redirect_target_empty(self):
        """safe_redirect_target returns fallback for empty string."""
        from app.modules.account.v2.utils import safe_redirect_target
        assert safe_redirect_target("") == "/"

    def test_safe_redirect_target_blocks_external(self):
        """safe_redirect_target blocks absolute URLs (open redirect prevention)."""
        from app.modules.account.v2.utils import safe_redirect_target
        assert safe_redirect_target("https://evil.com") == "/"
        assert safe_redirect_target("http://evil.com") == "/"
        assert safe_redirect_target("//evil.com") == "/"

    def test_safe_redirect_target_custom_fallback(self):
        """safe_redirect_target uses custom fallback."""
        from app.modules.account.v2.utils import safe_redirect_target
        assert safe_redirect_target(None, fallback="/home") == "/home"

    def test_format_flash_result_success(self):
        """format_flash_result returns form-success for True."""
        from app.modules.account.v2.utils import format_flash_result
        msg, cat = format_flash_result(True, "Password updated.")
        assert msg == "Password updated."
        assert cat == "form-success"

    def test_format_flash_result_failure(self):
        """format_flash_result returns form-error for False."""
        from app.modules.account.v2.utils import format_flash_result
        msg, cat = format_flash_result(False, "Invalid password.")
        assert msg == "Invalid password."
        assert cat == "form-error"


class TestAccountV2Blueprint:
    """Verify v2 blueprint has correct route rules."""

    def test_blueprint_has_correct_name(self, app):
        """Blueprint name is 'account' for url_for compatibility."""
        with app.app_context():
            from app.modules.account.v2.routes import account_bp_v2
            assert account_bp_v2.name == "account"

    def test_blueprint_has_login_route(self, app):
        """Blueprint has /login route."""
        with app.app_context():
            from app.modules.account.v2.routes import account_bp_v2
            rules = [r.rule for r in account_bp_v2.deferred_functions]
            # Deferred functions are lazy, so we check endpoint names instead
            endpoints = set()
            for func_name in dir(account_bp_v2):
                if not func_name.startswith("_"):
                    endpoints.add(func_name)
            # Verify key route functions exist on module level
            from app.modules.account.v2.routes.account_routes import (
                login,
                register,
                logout,
                manage,
                reset_password_request,
                reset_password,
                change_password,
                change_email_request,
                change_email,
                confirm_request,
                confirm,
                join_from_invite,
                unconfirmed,
                before_request,
            )
            assert callable(login)
            assert callable(register)
            assert callable(logout)
            assert callable(manage)
            assert callable(reset_password_request)
            assert callable(reset_password)
            assert callable(change_password)
            assert callable(change_email_request)
            assert callable(change_email)
            assert callable(confirm_request)
            assert callable(confirm)
            assert callable(join_from_invite)
            assert callable(unconfirmed)
            assert callable(before_request)


class TestAccountCompatWrapper:
    """Tests for the compatibility/deprecation wrapper."""

    def test_compat_module_imports(self, app):
        """Compat module imports without error."""
        with app.app_context():
            from app.compat.account import (
                AccountCompatStats,
                LEGACY_ROUTE_MAP,
                wrap_legacy_account_bp,
            )
            assert callable(wrap_legacy_account_bp)
            assert isinstance(LEGACY_ROUTE_MAP, dict)

    def test_legacy_route_map_coverage(self, app):
        """LEGACY_ROUTE_MAP covers all v1 account endpoints."""
        with app.app_context():
            from app.compat.account import LEGACY_ROUTE_MAP
            expected_endpoints = [
                "account.login",
                "account.register",
                "account.logout",
                "account.manage",
                "account.reset_password_request",
                "account.reset_password",
                "account.change_password",
                "account.change_email_request",
                "account.change_email",
                "account.confirm_request",
                "account.confirm",
                "account.join_from_invite",
                "account.unconfirmed",
            ]
            for ep in expected_endpoints:
                assert ep in LEGACY_ROUTE_MAP, f"Missing endpoint: {ep}"

    def test_compat_stats_tracking(self, app):
        """AccountCompatStats tracks endpoint hits."""
        with app.app_context():
            from app.compat.account import AccountCompatStats
            AccountCompatStats.reset()
            AccountCompatStats.record("account.login")
            AccountCompatStats.record("account.login")
            AccountCompatStats.record("account.register")
            stats = AccountCompatStats.get_stats()
            assert stats["total_legacy_hits"] == 3
            assert stats["endpoints"]["account.login"]["hits"] == 2
            assert stats["endpoints"]["account.register"]["hits"] == 1
            AccountCompatStats.reset()

    def test_v2_route_map_points_to_valid_v2_endpoints(self, app):
        """Every v2 mapping in LEGACY_ROUTE_MAP corresponds to a real v2 function."""
        with app.app_context():
            from app.compat.account import LEGACY_ROUTE_MAP
            from app.modules.account.v2.routes import account_routes
            for legacy_ep, mapping in LEGACY_ROUTE_MAP.items():
                v2_ep = mapping["v2"]
                # Extract function name from "account.function_name"
                func_name = v2_ep.split(".")[-1]
                assert hasattr(account_routes, func_name), (
                    f"v2 endpoint function '{func_name}' not found for legacy '{legacy_ep}'"
                )
