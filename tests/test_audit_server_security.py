"""The browser audit must exercise real CSRF enforcement, not testing bypasses."""

import sys
from types import SimpleNamespace
from threading import Thread

from flask import Flask, render_template_string, request
from flask_wtf import CSRFProtect, FlaskForm
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server


def test_audit_browser_forms_enforce_csrf(monkeypatch):
    from scripts.audit_server import create_app

    app = Flask(__name__)
    app.config.update(SECRET_KEY="audit-regression-only", WTF_CSRF_ENABLED=False)
    CSRFProtect(app)

    @app.route("/", methods=["GET", "POST"])
    def form():
        if request.method == "POST":
            return "Saved with valid token"
        return render_template_string(
            '<form method="post">{{ form.hidden_tag() }}'
            '<button>Save valid form</button></form>'
            '<form method="post"><button>Submit without token</button></form>',
            form=FlaskForm(),
        )

    monkeypatch.setitem(sys.modules, "manage", SimpleNamespace(app=app))
    audited_app = create_app()
    assert audited_app.config["WTF_CSRF_ENABLED"] is True
    server = make_server("127.0.0.1", 0, audited_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                url = f"http://127.0.0.1:{server.server_port}/"
                page.goto(url)
                with page.expect_navigation() as valid:
                    page.get_by_role("button", name="Save valid form").click()
                assert valid.value.status == 200
                assert page.get_by_text("Saved with valid token").is_visible()
                page.goto(url)
                with page.expect_navigation() as invalid:
                    page.get_by_role("button", name="Submit without token").click()
                assert invalid.value.status == 400
                assert page.get_by_text("The CSRF token is missing.").is_visible()
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_whole_product_boot_uses_csrf_enforcing_factory():
    import inspect
    from scripts.production_readiness_audit import boot

    assert '"scripts.audit_server:create_app"' in inspect.getsource(boot)
