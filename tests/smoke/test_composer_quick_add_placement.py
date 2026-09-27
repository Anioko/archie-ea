"""Quick-added Composer elements must not land stacked on top of each other.

Adversarial browser QA (10 Sep 2026) found that three consecutive Ctrl+K
quick-adds landed almost fully overlapping: `_placementFor`'s cascade step
(28px) and near-coincidence threshold (12px) were both far smaller than a
node's actual footprint (180x64, see createNode), so the cascade logic
correctly avoided exact stacking while every element still covered ~85% of
the previous one. Fixed by sizing STEP/NEAR against the real node dimensions
(composer.js `_placementFor`). This test drives three real quick-adds in a
real browser and asserts the rendered elements are actually visually
separated, not just at technically-different coordinates.
"""

import re
import uuid

import pytest
from playwright.sync_api import expect

from tests.smoke.conftest import PASSWORD

PAGE_TIMEOUT = 30000
# A quick-added node is 180x64 (composer_renderer.js createNode default).
# Two elements less than this apart on either axis visually overlap.
NODE_WIDTH = 180
NODE_HEIGHT = 64


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").click()
    page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)


def _quick_add(page, name):
    page.keyboard.press("Control+k")
    input_box = page.locator("#quick-add-input")
    expect(input_box).to_be_visible(timeout=PAGE_TIMEOUT)
    input_box.fill(name)
    # No catalog match for a fresh random name -> "Create new element" path.
    create_btn = page.get_by_role("button", name=re.compile("^Create$"))
    expect(create_btn).to_be_visible(timeout=PAGE_TIMEOUT)
    create_btn.click()


@pytest.mark.smoke
def test_quick_added_elements_do_not_overlap(browser, live_server, seeded):
    email = seeded["emails"]["solution_architect"]
    suffix = uuid.uuid4().hex[:8]

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    _login(page, live_server, email)

    page.goto(live_server + "/archimate/composer", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    expect(page.locator("nav[aria-label='Composer toolbar']")).to_be_visible(timeout=PAGE_TIMEOUT)

    for i in range(3):
        _quick_add(page, "QuickAdd %s Node %d" % (suffix, i))

    expect(page.locator(".joint-element")).to_have_count(3, timeout=PAGE_TIMEOUT)

    positions = page.locator(".joint-element").evaluate_all(
        "els => els.map(e => { const r = e.getBoundingClientRect(); return {x: r.left, y: r.top}; })"
    )
    assert len(positions) == 3

    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            dx = abs(positions[i]["x"] - positions[j]["x"])
            dy = abs(positions[i]["y"] - positions[j]["y"])
            assert dx >= NODE_WIDTH * 0.5 or dy >= NODE_HEIGHT * 0.5, (
                "quick-added elements %d and %d overlap: dx=%.0f dy=%.0f (positions=%r)"
                % (i, j, dx, dy, positions)
            )
