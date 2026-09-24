"""The old /product-roadmap URL redirects to the new single Roadmaps page.

This test confirms that the legacy URL still gets a real user to the working
Roadmaps page rather than a dead end - that the redirect chain resolves to a
page that actually renders and boots its front end.

The page's primary write action (dragging an epic between Now/Next/Later) is
tested in the capability-roadmap journey; this file only needs to prove the
redirect lands somewhere real.
"""

import pytest

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


def test_product_roadmap_redirect_lands_on_working_page(browser, live_server, seeded):
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    email = seeded["emails"]["solution_architect"]

    _login(page, live_server, email)

    # Request the old URL and follow redirect to the new page
    page.goto(live_server + "/product-roadmap", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(1500)

    # Confirm we landed on the capability roadmap page
    assert "/capability-roadmap" in page.url, "did not redirect to capability-roadmap page"

    # Confirm the page's root element is present
    assert page.is_visible("#capability-roadmap-app"), "capability-roadmap-app element not found or not visible"

    # Confirm Alpine frontend booted
    alpine_state = page.evaluate("() => typeof window.Alpine")
    assert alpine_state == "object", "window.Alpine is not defined - frontend did not boot"

    context.close()
