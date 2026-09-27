"""A Platform Admin creates a real framework configuration and it persists.

/framework-config/'s primary write action: the "New Configuration" card opens
a modal (id=create-framework-config), POSTs to
/api/framework-config/configurations (app/api/framework_config.py::
create_configuration, @login_required only - no persona-specific guard), and
the dashboard reloads and lists it in the "recent configurations" table
(server-rendered Jinja text, not an editable-field value).

Task-completion shape per test_composer_custom_properties.py: create -> leave
the page (a real reload, not just closing the modal) -> confirm it is still
listed, fetched fresh from the server.

Replaces /framework-config/'s entry in test_uncovered_modules_boot.py's
MODULES dict.
"""

import uuid

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", no_wait_after=True)
    except TypeError:
        page.locator("#submit").click()
    try:
        page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    page.wait_for_timeout(800)
    assert "/account/login" not in page.url, "could not sign in as %s" % email


def test_create_framework_config_survives_reload(browser, live_server, seeded):
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    page.on("pageerror", lambda e: print("PAGEERROR:", e))
    page.on("console", lambda m: print("CONSOLE[%s]: %s" % (m.type, m.text)) if m.type == "error" else None)

    email = seeded["emails"]["platform_admin"]
    name = "SmkConfig %s" % uuid.uuid4().hex[:8]
    code = "SMK-%s" % uuid.uuid4().hex[:8].upper()

    _login(page, live_server, email)
    page.goto(live_server + "/framework-config/", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(1000)

    page.get_by_role("button", name="Open", exact=True).first.click()
    name_input = page.locator("#cfc-name")
    expect(name_input).to_be_visible(timeout=PAGE_TIMEOUT)
    name_input.fill(name)
    page.locator("#cfc-code").fill(code)

    with page.expect_response(
        lambda r: r.url.endswith("/api/framework-config/configurations") and r.request.method == "POST",
        timeout=PAGE_TIMEOUT,
    ) as resp_info:
        page.get_by_label("Submit", exact=True).click()
    # 201 Created is the correct status for this POST (see create_configuration
    # in app/api/framework_config.py) - accept both rather than assume 200.
    assert resp_info.value.status in (200, 201), (
        "configuration creation POST failed: %d" % resp_info.value.status)
    page.wait_for_timeout(1200)

    # Leave the page for real - a fresh navigation - so the "recent
    # configurations" table must be re-rendered from the server, not from
    # whatever the modal's own JS left in the DOM.
    page.goto(live_server + "/framework-config/", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(1000)

    expect(page.locator("text=%s" % name).first).to_be_visible(timeout=PAGE_TIMEOUT)
    expect(page.locator("text=%s" % code).first).to_be_visible(timeout=PAGE_TIMEOUT)

    context.close()
