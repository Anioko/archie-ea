"""Capture the Architecture Journey states as evidence.

Not an assertion suite -- a deliberate evidence producer. The wave's handover has to
show the principal desktop and mobile states, and a screenshot taken by the same
harness that runs the journeys is worth more than one taken by hand, because it is
reproducible and it fails loudly when the page does not load.

It still asserts the one thing that would make a screenshot worthless: that the page
actually rendered rather than redirecting to a login or an error.

Set SMOKE_SCREENSHOT_DIR to control the destination.
"""

import os
import pathlib

import pytest

from .conftest import PAGE_TIMEOUT
# Import `page` too, deliberately. pytest-playwright 0.7.2 supplies its own
# `page`/`context`/`browser` fixtures; without shadowing `page` here, the plugin's
# fixture wins, calls sync_playwright() once, and then requests `browser` -- which
# resolves to THIS repo's conftest fixture, which calls sync_playwright() a second
# time on the same thread while the first loop is parked. The result is
# "Sync API inside the asyncio loop", and it is Playwright's own loop, so
# -p no:asyncio does nothing about it.
from .test_archetype_journeys import _login, _visit, page  # noqa: F401


pytestmark = [pytest.mark.smoke, pytest.mark.journey]


VIEWPORTS = {"desktop": (1280, 900), "mobile": (390, 844)}


def _shot_dir():
    target = os.environ.get(
        "SMOKE_SCREENSHOT_DIR",
        str(pathlib.Path(__file__).resolve().parents[2] / "screenshots"),
    )
    path = pathlib.Path(target)
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.mark.parametrize("viewport", sorted(VIEWPORTS))
def test_capture_journey_hub(page, live_server, seeded, viewport):
    width, height = VIEWPORTS[viewport]
    page.set_viewport_size({"width": width, "height": height})
    _login(page, live_server, seeded["emails"]["business_architect"])

    response, state = _visit(page, live_server, "/architecture-journey/")
    assert response.status < 400, f"hub returned {response.status}; screenshot would be of an error"

    out = _shot_dir() / f"journey-hub-{viewport}.png"
    page.screenshot(path=str(out), full_page=True)
    assert out.exists() and out.stat().st_size > 0

    # Recorded alongside the image so the evidence carries its own caveats.
    print(f"[screenshot] {out} overflow={state['overflow']} unnamed={len(state['unnamed'])}")


@pytest.mark.parametrize("viewport", sorted(VIEWPORTS))
def test_capture_journey_home(page, live_server, seeded, viewport):
    """Walk into a journey and capture the home, creating one if the tenant has none."""
    width, height = VIEWPORTS[viewport]
    page.set_viewport_size({"width": width, "height": height})
    _login(page, live_server, seeded["emails"]["business_architect"])
    _visit(page, live_server, "/architecture-journey/")

    resume = page.locator('a[href*="/architecture-journey/work/"]').first
    if resume.count() == 0:
        pytest.skip(
            "no journey exists in the seeded tenant; the home cannot be captured "
            "without one and this test does not fabricate data to photograph"
        )

    resume.click()
    page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(1200)

    assert page.locator("h1").count() == 1, "the journey home must have exactly one heading"

    out = _shot_dir() / f"journey-home-{viewport}.png"
    page.screenshot(path=str(out), full_page=True)
    assert out.exists() and out.stat().st_size > 0
    print(f"[screenshot] {out}")
