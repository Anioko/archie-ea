"""A real Chromium navigation failure must not disappear from census results.

The HTTP boundary is controlled; login and screen selection avoid the database.
The actual measurement loop and release assertion execute unchanged.
"""
import pytest
from contextlib import nullcontext
from playwright.sync_api import sync_playwright

from tests.smoke import test_interaction_reality as census


@pytest.fixture(scope="module")
def census_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.mark.parametrize("status", [200, 403, 404, 500])
def test_required_screen_http_outcome_is_not_silently_omitted(monkeypatch, census_browser, status):
    original_context = census_browser.new_context

    def context(**kwargs):
        ctx = original_context(**kwargs)
        ctx.route("http://census.test/**", lambda route: route.fulfill(
            status=status, content_type="text/html", body="<h1>Unavailable</h1>"))
        return ctx

    monkeypatch.setattr(census_browser, "new_context", context)
    monkeypatch.setattr(census, "_login", lambda *args: None)
    monkeypatch.setattr(census, "_screens_for", lambda *args: ["/required-screen"])
    monkeypatch.setattr(census, "_load_baseline", lambda: {})
    monkeypatch.setattr(census, "WRITE_BASELINE", False)
    outcome = nullcontext() if status == 200 else pytest.raises(AssertionError, match="required-screen")
    with outcome:
        census.test_controls_are_wired_and_modals_are_clean(
            "platform_admin", "http://census.test",
            {"emails": {"platform_admin": "qa@example.invalid"}}, census_browser)
