"""Browser journey for the Chief Architect archetype.

The workbench's entire value is that a reader can tell a measured fact from a
missing one from an AI interpretation. Every assertion here is about that
distinction surviving a real browser — which is the layer that matters, because
the server-side tests can only prove the strings were rendered, not that they
are visible, distinguishable and operable.

There is no ``chief_architect`` entry in ``ARCHETYPES``: the role exists in the
RBAC vocabulary (``transformation_room`` authorises enterprise_architect / cto /
chief_architect / platform_admin) but the smoke harness seeds
``enterprise_architect``, which holds the same access to this screen. That is the
persona used here.
"""

import os

import pytest

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import PAGE_STATE, _login, _visit, page  # noqa: F401

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

WORKBENCH = "/solutions/architect-synthesis"
PERSONA = "enterprise_architect"

#: Set to a directory to capture the desktop/mobile evidence screenshots.
SCREENSHOT_DIR = os.environ.get("SMOKE_SCREENSHOT_DIR")


def _screenshot(page, name, directory=None):
    """Capture all visible shell content at the same width, restoring the caller's viewport.

    ``full_page=True`` alone yields exactly one viewport here: the admin shell
    scrolls an inner ``overflow-auto`` element, so the document itself never
    grows past the window and Playwright has nothing extra to capture. Releasing
    the inner container's height first is what makes the page actually tall.
    """
    folder = SCREENSHOT_DIR if directory is None else directory
    if not folder:
        return
    os.makedirs(folder, exist_ok=True)
    original_viewport = page.viewport_size
    measure = """() => {
            let height = document.documentElement.scrollHeight;
            const clipped = [];
            document.querySelectorAll('*').forEach(el => {
                const s = getComputedStyle(el);
                const r = el.getBoundingClientRect();
                if ((s.overflowY === 'auto' || s.overflowY === 'scroll') &&
                    el.clientHeight > 0 && r.right > 0 && r.left < window.innerWidth &&
                    s.visibility !== 'hidden') {
                    const overflow = el.scrollHeight - el.clientHeight;
                    height = Math.max(height, window.innerHeight + overflow);
                    if (overflow > 0) clipped.push({
                        tag: el.tagName, id: el.id, overflow: overflow
                    });
                }
            });
            return {height: height, width: document.documentElement.scrollWidth, clipped: clipped};
        }"""
    # The shell pins its own height and scrolls an inner element, so growing the
    # viewport is what actually reveals the rest of the page. Allow reflow, but
    # bound this to four resizes, 24000 CSS px high and 32 million CSS pixels.
    # That leaves room above the existing phone content without unbounded growth.
    max_pixels = 32_000_000
    max_height = min(24_000, max_pixels // original_viewport["width"])
    max_resizes = 4
    try:
        content = page.evaluate(measure)
        height = original_viewport["height"]
        for _ in range(max_resizes):
            target_height = min(max(height, int(content["height"]) + 120), max_height)
            if target_height < height:
                break
            page.set_viewport_size({
                "width": original_viewport["width"], "height": target_height,
            })
            page.wait_for_timeout(600)
            height = target_height
            content = page.evaluate(measure)
            if not content["clipped"]:
                capture_height = max(height, content["height"])
                capture_width = max(original_viewport["width"], content["width"])
                if capture_height <= max_height and capture_width * capture_height <= max_pixels:
                    page.screenshot(
                        path=os.path.join(folder, name), full_page=True,
                        animations="disabled", scale="css",
                    )
                    return
                break
            if height == max_height:
                break
        raise AssertionError(
            "Incomplete expanded-content capture at %r "
            "(height limit %s, pixel limit %s, resize limit %s): %r"
            % (page.viewport_size, max_height, max_pixels, max_resizes, content)
        )
    finally:
        page.set_viewport_size(original_viewport)


def test_workbench_renders_and_boots(page, live_server, seeded):
    """The baseline: it loads, the front end boots, and nothing is unnamed."""
    _login(page, live_server, seeded["emails"][PERSONA])
    response, state = _visit(page, live_server, WORKBENCH)

    assert response is not None and response.status < 400, (
        "workbench returned HTTP %s" % (response.status if response else "no response")
    )
    assert state["alpine"] == "object", (
        "front end did not boot (window.Alpine is %s)" % state["alpine"]
    )
    assert not state["unnamed"], "unnamed controls: %s" % state["unnamed"]
    assert not page.page_errors, "uncaught page errors: %s" % page.page_errors
    _screenshot(page, "chief-architect-workbench-desktop.png")


def test_workbench_states_the_provenance_vocabulary(page, live_server, seeded):
    """A reader must never mistake an AI sentence for a measured count.

    The legend is the contract: it names all four kinds before any figure is
    shown. Asserting on visible text rather than on markup, because a badge that
    renders but is not visible communicates nothing.
    """
    _login(page, live_server, seeded["emails"][PERSONA])
    _visit(page, live_server, WORKBENCH)

    body = page.inner_text("body")
    for claim in ("Measured", "Not recorded", "Could not measure", "AI-generated"):
        assert claim in body, "provenance vocabulary missing %r" % claim
    # Compared case-insensitively: inner_text returns the CSS-transformed text,
    # and this label is `uppercase`, so it reads "HOW TO READ THIS PAGE".
    assert "how to read this page" in body.lower()


def test_ai_panel_is_badged_and_starts_empty(page, live_server, seeded):
    """Nothing on first paint may read as a generated conclusion.

    The panel renders its heading and its badge, but no briefing until the reader
    asks for one — so there is no moment where AI prose sits on the page looking
    like part of the measured posture.
    """
    _login(page, live_server, seeded["emails"][PERSONA])
    _visit(page, live_server, WORKBENCH)

    heading = page.locator("#ai-briefing-heading")
    assert heading.count() == 1
    assert heading.is_visible()

    section = page.locator("section[aria-labelledby='ai-briefing-heading']")
    assert "Advisory only" in section.inner_text()
    assert "AI-generated" in section.inner_text()

    # The result region is x-show'd off until a briefing exists.
    assert section.locator("[aria-live='polite']").count() == 1
    assert not section.locator("[aria-live='polite']").is_visible(), (
        "the AI result region is visible before any briefing was requested"
    )


def test_generate_button_is_keyboard_operable(page, live_server, seeded):
    """The one interactive control on the page must be reachable without a mouse."""
    _login(page, live_server, seeded["emails"][PERSONA])
    _visit(page, live_server, WORKBENCH)

    button = page.locator("section[aria-labelledby='ai-briefing-heading'] button")
    assert button.count() == 1
    assert button.get_attribute("type") == "button"
    button.focus()
    focused = page.evaluate("() => document.activeElement.tagName.toLowerCase()")
    assert focused == "button", "generate control did not take keyboard focus"


def test_workbench_has_one_shell_and_no_dead_drill_downs(page, live_server, seeded):
    """One <h1>, one breadcrumb, and every rendered link points somewhere real.

    Drill-down targets are resolved server-side through a guarded helper that
    yields None when the blueprint is absent, and the template then renders no
    link at all. This proves the guard works: a literal "None" or empty href in
    the markup would mean the guard leaked.
    """
    _login(page, live_server, seeded["emails"][PERSONA])
    _visit(page, live_server, WORKBENCH)

    assert page.locator("h1").count() == 1
    assert page.locator("nav[aria-label='Breadcrumb']").count() == 1

    bad = page.evaluate(
        """() => [...document.querySelectorAll('a')]
              .map(a => a.getAttribute('href'))
              .filter(h => h === null || h === '' || h === 'None' || h === '#')"""
    )
    assert not bad, "links with no real target: %s" % bad


@pytest.mark.parametrize("page", [390], indirect=True)
def test_workbench_fits_a_phone(page, live_server, seeded):
    """No horizontal overflow at 390px — the regression nothing else watches."""
    _login(page, live_server, seeded["emails"][PERSONA])
    response, state = _visit(page, live_server, WORKBENCH)

    assert response is not None and response.status < 400
    assert state["overflow"] == 0, (
        "workbench overflows its viewport by %spx at 390px wide" % state["overflow"]
    )
    _screenshot(page, "chief-architect-workbench-mobile.png")
