"""An Enterprise Architect uses "Generate with AI" on the programme wizard,
then completes and submits the wizard with the pre-filled values.

Opt-in, deterministic AI transport qualification (SMOKE_AI_PROTOCOL_STUB=1),
matching the convention in test_ai_protocol_journeys.py: this proves the real
request/response protocol end to end (route -> ProgrammeSetupService.
ai_prefill_programme -> LLMService -> real HTTP call -> JSON parse -> field
pre-fill -> wizard submit -> a real StrategicInitiative-backed programme),
not model reasoning quality - the reply is the fixed PROGRAMME_PREFILL
scenario, not a live model. Without the stub, the same panel is exercised
manually against a real provider (see CLAUDE.md AI/ML architect gate).
"""

import pytest
from playwright.sync_api import expect

from .ai_protocol_stub import PROGRAMME_PREFILL
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


def test_ai_prefill_populates_wizard_and_programme_is_created(
    browser, live_server, seeded, required_protocol
):
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    email = seeded["emails"]["enterprise_architect"]

    _login(page, live_server, email)
    page.goto(live_server + "/solutions/new-programme", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_selector('[data-testid="step-intent"]', timeout=PAGE_TIMEOUT)

    page.locator('[data-testid="ai-prefill-open"]').click()
    description = page.locator('[data-testid="ai-prefill-description"]')
    expect(description).to_be_visible(timeout=PAGE_TIMEOUT)
    description.fill(PROGRAMME_PREFILL["prompt"])

    with page.expect_response(
        lambda r: r.url.endswith("/solutions/new-programme/ai-prefill") and r.request.method == "POST",
        timeout=PAGE_TIMEOUT,
    ) as resp_info:
        page.locator('[data-testid="ai-prefill-generate"]').click()
    assert resp_info.value.status < 400, "AI prefill request failed: %d" % resp_info.value.status

    expect(page.locator('[data-testid="ai-prefill-applied"]')).to_be_visible(timeout=PAGE_TIMEOUT)

    assert page.locator('[data-testid="field-name"]').input_value() == "CI Fixture: CRM Consolidation"
    assert "Consolidate four regional CRM" in page.locator('[data-testid="field-objective"]').input_value()

    page.locator('[data-testid="wizard-next"]').click()

    owner_search = page.locator('[data-testid="field-owner"]')
    owner_search.click()
    owner_search.fill(email.split("@")[0])
    page.wait_for_timeout(600)
    first_owner = page.locator("#owner-results button").first
    expect(first_owner).to_be_visible(timeout=PAGE_TIMEOUT)
    first_owner.click()
    page.locator('[data-testid="field-target-date-reason"]').fill("Not yet scheduled")
    page.locator('[data-testid="wizard-next"]').click()

    assert "Sales" in page.locator('[data-testid="field-business-units"]').input_value()
    page.locator('[data-testid="wizard-next"]').click()

    assert page.locator('[data-testid="field-outcome"]').input_value() == "One CRM platform serving every region."
    page.locator('[data-testid="wizard-next"]').click()

    assert page.locator('[data-testid="field-metric-name"]').input_value() == "Number of CRM instances"
    assert page.locator('[data-testid="field-target-value"]').input_value() == "1"
    page.wait_for_timeout(300)
    page.locator('[data-testid="wizard-next"]').click()

    submit_btn = page.locator('[data-testid="wizard-submit"]')
    expect(submit_btn).to_be_enabled(timeout=PAGE_TIMEOUT)
    with page.expect_response(
        lambda r: r.url.endswith("/solutions/create-programme") and r.request.method == "POST",
        timeout=PAGE_TIMEOUT,
    ) as create_resp:
        submit_btn.click()
    assert create_resp.value.status < 400, "Programme creation failed: %d" % create_resp.value.status

    page.wait_for_url(lambda url: "/solutions/programmes/" in url, timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(500)
    context.close()
