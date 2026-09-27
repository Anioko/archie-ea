"""A Business Architect uses "Generate with AI" on the New Business Case
modal, then creates the case with the pre-filled title/description.

Opt-in, deterministic AI transport qualification (SMOKE_AI_PROTOCOL_STUB=1),
matching test_ai_protocol_journeys.py's convention: proves the real
route -> generate_case_seed -> LLMService -> real HTTP call -> JSON parse ->
field pre-fill -> create path, using the fixed CASE_SEED scenario rather than
a live model.
"""

import pytest
from playwright.sync_api import expect

from .ai_protocol_stub import CASE_SEED
from .conftest import PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey, pytest.mark.ai_protocol]


@pytest.fixture(scope="session")
def required_protocol(ai_protocol_stub):
    if ai_protocol_stub is None:
        pytest.fail("This journey requires explicit SMOKE_AI_PROTOCOL_STUB=1; this is not a skipped qualification")
    return ai_protocol_stub


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


def test_ai_prefill_populates_new_case_modal_and_case_is_created(
    browser, live_server, seeded, required_protocol
):
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    email = seeded["emails"]["business_architect"]

    _login(page, live_server, email)
    page.goto(live_server + "/business-case/", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(500)

    page.evaluate("Platform.modal.open('bc-create-modal')")
    seed_description = page.locator("#bc-seed-description")
    expect(seed_description).to_be_visible(timeout=PAGE_TIMEOUT)
    seed_description.fill(CASE_SEED["prompt"])

    with page.expect_response(
        lambda r: r.url.endswith("/business-case/ai-prefill") and r.request.method == "POST",
        timeout=PAGE_TIMEOUT,
    ) as resp_info:
        page.locator('[data-testid="bc-seed-generate"]').click()
    assert resp_info.value.status < 400, "AI prefill request failed: %d" % resp_info.value.status

    expect(page.locator('[data-testid="bc-seed-applied"]')).to_be_visible(timeout=PAGE_TIMEOUT)

    title_value = page.locator("#bc-title").input_value()
    description_value = page.locator("#bc-description").input_value()
    assert title_value == "CI Fixture: Consolidate Regional CRM Instances"
    assert "duplicate licence costs" in description_value

    with page.expect_response(
        lambda r: "/business-case/create" in r.url and r.request.method == "POST",
        timeout=PAGE_TIMEOUT,
    ) as create_resp:
        page.locator('[data-testid="bc-create-submit"]').click()
    assert create_resp.value.status < 400, "Business case creation failed: %d" % create_resp.value.status

    page.wait_for_url(lambda url: "/business-case/" in url and url.rstrip("/") != live_server + "/business-case", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(500)
    assert title_value in page.title(), "case title %r not in page title %r" % (title_value, page.title())
    context.close()
