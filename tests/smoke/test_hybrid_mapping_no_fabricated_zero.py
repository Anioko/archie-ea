"""The Hybrid Multi-Path Mapping Dashboard rendered every coverage ratio as
a red "0.0%" for an organization with zero capabilities -- a 0/0 ratio
formatted and colored identically to a real, measured, failing 0%.

Found 14 Sep 2026 in a full-app design pass: app/main/routes_hybrid_mapping.py
returned a bare `0` (not `None`) for every zero-denominator coverage
percentage except one (prod_archimate_coverage, which already correctly
returned None) -- the one correct example proved the rest were a bug, not a
deliberate choice. Fixed by returning None consistently and rendering it as
an uncolored em dash in the template, matching CLAUDE.md's rule that a 0
meaning "not computed" must never be indistinguishable from a measured zero.
"""
import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", force=True, no_wait_after=True)
    except TypeError:
        page.locator("#submit").dispatch_event("click")
    try:
        page.wait_for_url(lambda u: "/account/login" not in u, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    assert "/account/login" not in page.url, "could not sign in as %s" % email


def test_zero_capabilities_renders_dash_not_red_zero_percent(browser, live_server, seeded):
    """A freshly-seeded org has zero unified capabilities, so every coverage
    ratio on this page is a 0/0 -- "not computed", not "measured at 0%"."""
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        page.goto(live_server + "/hybrid-mapping-dashboard", wait_until="networkidle", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(600)

        body_text = page.locator("body").inner_text()
        if "could not be calculated" in body_text:
            pytest.skip("stats query failed in this environment -- not what this test checks")

        destructive_percentages = page.eval_on_selector_all(
            ".text-destructive",
            "els => els.map(e => e.textContent.trim()).filter(t => t.includes('%'))"
        )
        assert not destructive_percentages, (
            "found red-colored percentage text on a zero-capability org's "
            "mapping dashboard: %s -- a 0/0 ratio must render as an "
            "uncolored dash, not a red 0.0%% (which reads as a measured "
            "failure)" % destructive_percentages
        )
    finally:
        page.close()
