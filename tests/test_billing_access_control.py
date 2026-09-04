"""Billing requests must enforce administrator permission before service calls."""

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin, login_user


def _billing_test_app(monkeypatch, administrator):
    from app.modules.admin import billing_routes

    class User(UserMixin):
        id = "billing-test"
        organization = None

        def can(self, permission):
            return administrator

    app = Flask(__name__)
    app.secret_key = "isolated-billing-test"
    login = LoginManager(app)
    login.user_loader(lambda user_id: User())
    app.register_blueprint(billing_routes.billing_bp, url_prefix="/admin/billing")
    monkeypatch.setattr(billing_routes, "render_template", lambda *args, **kwargs: "Billing")

    @app.route("/test-entry")
    def test_entry():
        login_user(User())
        return '<a href="/admin/billing/">Billing</a>'

    return app


@pytest.mark.parametrize("method,path,admin_status", [
    ("GET", "/admin/billing/", 200),
    ("POST", "/admin/billing/upgrade", 400),
    ("GET", "/admin/billing/portal", 302),
])
@pytest.mark.parametrize("administrator", [False, True])
def test_billing_requires_administrator(monkeypatch, method, path, admin_status, administrator):
    app = _billing_test_app(monkeypatch, administrator)
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "billing-test"
        session["_fresh"] = True
    response = client.open(path, method=method)
    assert response.status_code == (admin_status if administrator else 403)


@pytest.mark.parametrize("administrator", [False, True])
def test_browser_billing_navigation_enforces_permission(monkeypatch, administrator):
    from threading import Thread
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server

    app = _billing_test_app(monkeypatch, administrator)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{server.server_port}/test-entry")
                with page.expect_navigation() as navigation:
                    page.get_by_role("link", name="Billing", exact=True).click()
                assert navigation.value.status == (200 if administrator else 403)
                assert page.locator("body").inner_text().strip().startswith(
                    "Billing" if administrator else "Forbidden"
                )
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
