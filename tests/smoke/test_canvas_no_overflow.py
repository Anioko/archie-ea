"""Browser smoke test: Business Model Canvas at 1440x900 — no horizontal
overflow and no box title cut mid-word.

Canvas/framework UI fix (24 Sep 2026).
"""

import re

import pytest
from playwright.sync_api import expect

from tests.smoke.conftest import PASSWORD

PAGE_TIMEOUT = 30000


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").click()
    page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)


@pytest.mark.smoke
def test_canvas_detail_no_horizontal_overflow(browser, live_server, seeded):
    """At 1440x900 the nine-box grid must fit the content width with no
    horizontal overflow and every box title must not be cut mid-word."""
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
    page = context.new_page()
    try:
        _login(page, live_server, seeded["emails"]["business_architect"])

        # Navigate to the canvas list and click the first canvas, or create one.
        index_url = live_server + "/business-model/"
        page.goto(index_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        canvas_links = page.locator('a[href*="/business-model/"]')
        if canvas_links.count() == 0:
            page.get_by_role("button", name=re.compile("New Canvas", re.I)).first.click()
            form = page.locator('[data-testid="bmc-create-form"]')
            expect(form).to_be_visible(timeout=PAGE_TIMEOUT)
            form.locator("#bmc-name").fill("Overflow Test Canvas")
            page.get_by_test_id("bmc-create-submit").click()
            page.wait_for_url(re.compile(r"/business-model/\d+$"), timeout=PAGE_TIMEOUT)
        else:
            canvas_links.first.click()
            page.wait_for_url(re.compile(r"/business-model/\d+$"), timeout=PAGE_TIMEOUT)

        # Wait for the grid to render.
        expect(page.get_by_test_id("bmc-grid")).to_be_visible(timeout=PAGE_TIMEOUT)

        # Assert no horizontal overflow on the document.
        scroll_width = page.evaluate("document.scrollingElement.scrollWidth")
        inner_width = page.evaluate("window.innerWidth")
        assert scroll_width <= inner_width, (
            f"Horizontal overflow detected: scrollWidth={scroll_width} > innerWidth={inner_width}"
        )

        # Assert every box title's scrollWidth <= clientWidth (no text cut-off).
        titles = page.locator(".bmc-box-title")
        count = titles.count()
        assert count == 9, f"Expected 9 box titles, found {count}"

        for i in range(count):
            title = titles.nth(i)
            sw_val = title.evaluate("el => el.scrollWidth")
            cw_val = title.evaluate("el => el.clientWidth")
            label = title.text_content()
            assert sw_val <= cw_val, (
                f"Box title '{label}' is cut off: scrollWidth={sw_val} > clientWidth={cw_val}"
            )
    finally:
        context.close()