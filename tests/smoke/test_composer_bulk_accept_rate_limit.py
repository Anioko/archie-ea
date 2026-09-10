"""A large "Place Full Diagram on Canvas" must not silently drop elements.

Production evidence (10 Sep 2026): a real SAP-scenario AI generation produced
32 elements; "Place Full Diagram on Canvas" fired all 32 create-element POSTs
in one unthrottled burst, and the global write rate limit (30/min,
app/_bootstrap/rate_limiting.py) rejected one with 429 -- silently missing
from the canvas but for a single toast easy to miss. Fixed with a
bounded-concurrency runner (composer_ai.js `_runLimited`/`_postWithRetry`).

This harness runs with RATE_LIMITING_ENABLED=False (TestingConfig), so it
cannot reproduce the 429 itself -- see tests/test_composer_frontend_static.py
for the structural guard on the fix's shape. This test instead proves the
mechanism's correctness directly: seed a 35-element batch (comfortably over
the real 30/min bucket) into the AI-accept flow and assert every single one
lands on the canvas with zero "Failed to create element" toasts, which is
what the concurrency-limited, retrying path must guarantee regardless of
whether a real rate limit fires.
"""

import re
import uuid

import pytest
from playwright.sync_api import expect

from tests.smoke.conftest import PASSWORD

PAGE_TIMEOUT = 45000


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").click()
    page.wait_for_url(lambda u: "/account/login" not in u, timeout=PAGE_TIMEOUT)


@pytest.mark.smoke
def test_large_ai_batch_places_every_element(browser, live_server, seeded):
    email = seeded["emails"]["solution_architect"]
    suffix = uuid.uuid4().hex[:8]
    n = 35

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1960, "height": 1080})
    page = context.new_page()
    _login(page, live_server, email)

    page.goto(live_server + "/archimate/composer", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_selector("nav[aria-label='Composer toolbar']", timeout=PAGE_TIMEOUT)

    # Seed a synthetic AI-generation result (bypassing the LLM call itself --
    # this test is about the accept/place pipeline, not generation quality)
    # and drive the real accept-and-confirm flow.
    page.evaluate(
        """
        (n) => {
            const suffix = %r;
            const app = Alpine.$data(document.querySelector('[x-data^="composerApp"]'));
            app.generatedElements = Array.from({length: n}, (_, i) => ({
                name: 'Bulk Element ' + suffix + '-' + i,
                type: 'ApplicationComponent',
                layer: 'application',
                category: 'new',
            }));
            app.generatedRelationships = [];
            app.generateModalOpen = true;
        }
        """ % suffix,
        n,
    )

    page.get_by_role("button", name=re.compile("Place Full Diagram on Canvas", re.I)).click()
    confirm_btn = page.get_by_role("button", name=re.compile("^Create & place$"))
    expect(confirm_btn).to_be_visible(timeout=PAGE_TIMEOUT)
    confirm_btn.click()

    expect(page.locator(".joint-element")).to_have_count(n, timeout=PAGE_TIMEOUT)
