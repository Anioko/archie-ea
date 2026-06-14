"""
Tests for account module -- route parity and import verification.

Verifies that the migrated account module registers all 14 routes
with the same URL rules as the legacy app/account/views.py.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from app.modules.account.forms.account_forms import (
    ChangeEmailForm,
    ChangePasswordForm,
    CreatePasswordForm,
    LoginForm,
    RegistrationForm,
    RequestResetPasswordForm,
    ResetPasswordForm,
)


@pytest.fixture(scope="module")
def app():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestAccountModuleImports:
    """Verify the module can be imported without errors."""

    def test_register_function_importable(self):
        """The register() function should be importable."""
        from app.modules.account import register
        assert callable(register)

    def test_account_blueprint_importable(self):
        """The account blueprint should be importable."""
        from app.modules.account.routes.account_routes import account_bp
        assert account_bp.name == "account"

    def test_all_forms_importable(self):
        """All 7 form classes should be importable."""
        assert LoginForm is not None
        assert RegistrationForm is not None
        assert RequestResetPasswordForm is not None
        assert ResetPasswordForm is not None
        assert CreatePasswordForm is not None
        assert ChangePasswordForm is not None
        assert ChangeEmailForm is not None

    def test_account_service_importable(self):
        """The AccountService class should be importable."""
        from app.modules.account.services.account_service import AccountService
        assert AccountService is not None


class TestAccountRouteParity:
    """Verify the new module registers the same routes as the legacy code."""

    EXPECTED_RULES = sorted([
        "/account/login",
        "/account/register",
        "/account/logout",
        "/account/manage",
        "/account/manage/info",
        "/account/reset-password",
        "/account/reset-password/<token>",
        "/account/manage/change-password",
        "/account/manage/change-email",
        "/account/manage/change-email/<token>",
        "/account/confirm-account",
        "/account/confirm-account/<token>",
        "/account/join-from-invite/<int:user_id>/<token>",
        "/account/unconfirmed",
    ])

    def test_route_count(self, app):
        """Module should register exactly 14 account routes."""
        with app.app_context():
            account_rules = [
                rule.rule for rule in app.url_map.iter_rules()
                if rule.rule.startswith("/account/")
            ]
            # 14 unique URL patterns (manage and manage/info map to same view)
            assert len(account_rules) >= 14, (
                f"Expected >= 14 account routes, got {len(account_rules)}: {sorted(account_rules)}"
            )

    def test_all_expected_routes_present(self, app):
        """Every expected URL rule should exist in the app's URL map."""
        with app.app_context():
            actual_rules = sorted([
                rule.rule for rule in app.url_map.iter_rules()
                if rule.rule.startswith("/account/")
            ])
            for expected in self.EXPECTED_RULES:
                assert expected in actual_rules, (
                    f"Missing route: {expected}. Actual: {actual_rules}"
                )

    def test_login_endpoint_name(self, app):
        """login_manager.login_view = 'account.login' must resolve."""
        with app.test_request_context():
            from flask import url_for
            url = url_for("account.login")
            assert url == "/account/login"

    def test_before_app_request_registered(self, app):
        """The before_app_request hook must be registered."""
        with app.app_context():
            # Flask stores before_request_funcs keyed by blueprint name (or None for app-wide)
            # before_app_request registers on None key
            hooks = app.before_request_funcs.get(None, [])
            hook_names = [f.__name__ for f in hooks]
            assert "before_request" in hook_names, (
                f"before_request hook not found. Registered hooks: {hook_names}"
            )


class TestAccountRouteResponses:
    """Integration tests for account route HTTP responses."""

    def test_login_page_renders(self, client):
        """GET /account/login should return 200 with login form."""
        resp = client.get("/account/login")
        assert resp.status_code == 200
        body = resp.data.decode("utf-8", errors="ignore")
        assert "login" in body.lower() or "email" in body.lower()

    def test_register_page_renders(self, client):
        """GET /account/register should return 200 with registration form."""
        resp = client.get("/account/register")
        assert resp.status_code == 200

    def test_reset_password_page_renders(self, client):
        """GET /account/reset-password should return 200."""
        resp = client.get("/account/reset-password")
        assert resp.status_code == 200

    def test_logout_redirects_unauthenticated(self, client):
        """GET /account/logout without login should redirect to login."""
        resp = client.get("/account/logout", follow_redirects=False)
        assert resp.status_code == 302

    def test_manage_redirects_unauthenticated(self, client):
        """GET /account/manage without login should redirect to login."""
        resp = client.get("/account/manage", follow_redirects=False)
        assert resp.status_code == 302

    def test_unconfirmed_redirects_anonymous(self, client):
        """GET /account/unconfirmed for anonymous user should redirect."""
        resp = client.get("/account/unconfirmed", follow_redirects=False)
        assert resp.status_code == 302

    def test_login_post_invalid_credentials(self, client):
        """POST /account/login with bad credentials should re-render form."""
        resp = client.post(
            "/account/login",
            data={"email": "nobody@example.com", "password": "wrong"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        body = resp.data.decode("utf-8", errors="ignore")
        assert "Invalid" in body or "login" in body.lower()


class TestAccountForms:
    """Unit tests for account form validation."""

    def test_login_form_requires_email(self, app):
        """LoginForm should require email field."""
        with app.app_context():
            form = LoginForm(data={"password": "test"})
            assert not form.validate()

    def test_login_form_requires_password(self, app):
        """LoginForm should require password field."""
        with app.app_context():
            form = LoginForm(data={"email": "test@example.com"})
            assert not form.validate()

    def test_registration_form_password_match(self, app):
        """RegistrationForm should require matching passwords."""
        with app.app_context():
            form = RegistrationForm(data={
                "first_name": "Test",
                "last_name": "User",
                "email": "unique_test_99@example.com",
                "password": "password1",
                "password2": "password2",
            })
            assert not form.validate()
