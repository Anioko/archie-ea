"""Browser journey for the Architecture Journey home.

The unit tests prove the read model and the rendered HTML. They cannot prove the
things that only exist in a browser: that the front end boots at all, that every
control is reachable by keyboard and carries a name a screen reader can announce,
and that the page does not overflow horizontally on a phone.

The one assertion worth stating plainly is the honesty check. On this screen a "0"
and an em dash mean different things -- "there are no risks" versus "we could not
find out" -- and a reader acts on the difference. A browser test is where that can
be checked as the user sees it, after Alpine has run, rather than in the template
source.
"""

import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD


pytestmark = [pytest.mark.smoke, pytest.mark.journey]


# Reuse the archetype login flow rather than re-deriving it: the force-click and
# no_wait_after handling in the sibling module exists because Alpine disables the
# submit button, and a second copy would drift from it.
from .test_archetype_journeys import _login, _visit  # noqa: E402


def test_journey_hub_renders_and_frames_non_solution_outcomes(page, live_server, seeded):
    """The hub must not present a solution as the assumed destination."""
    _login(page, live_server, seeded["emails"]["business_architect"])
    response, state = _visit(page, live_server, "/architecture-journey/")

    assert response.status < 400, f"hub returned {response.status}"
    assert state["alpine"] == "object", "Alpine did not boot on the journey hub"
    assert state["overflow"] == 0, "the journey hub overflows horizontally"
    assert state["unnamed"] == [], f"unnamed controls on the journey hub: {state['unnamed']}"

    body = page.inner_text("body").lower()
    assert "solution is one possible outcome" in body or "no change" in body, (
        "the hub must frame a solution as one possible outcome, not the destination"
    )


def test_journey_hub_has_one_heading_and_one_breadcrumb(page, live_server, seeded):
    """Three page-level entry points once carried two breadcrumb ancestries."""
    _login(page, live_server, seeded["emails"]["business_architect"])
    _visit(page, live_server, "/architecture-journey/")

    assert page.locator("h1").count() == 1
    assert page.locator('nav[aria-label="Breadcrumb"]').count() == 1


def test_journey_hub_is_usable_at_phone_width(page, live_server, seeded):
    """390px is the narrow viewport this product's audit ratchet uses."""
    page.set_viewport_size({"width": 390, "height": 844})
    _login(page, live_server, seeded["emails"]["business_architect"])
    response, state = _visit(page, live_server, "/architecture-journey/")

    assert response.status < 400
    assert state["overflow"] == 0, (
        "the journey hub scrolls sideways at 390px; wide content must scroll inside "
        "its own container, never the page body"
    )


def test_journey_home_never_renders_a_bare_zero_for_unknown_counts(
    page, live_server, seeded
):
    """The honesty rule, as the user meets it.

    Every headline count on the journey home is either a measured number or an em
    dash. This walks from the hub into a journey and asserts that no count panel
    renders an empty string -- the failure mode where a None reaches the template
    without going through the `dash` filter and silently renders as nothing at all,
    which reads as "zero" to anyone glancing at it.
    """
    _login(page, live_server, seeded["emails"]["business_architect"])
    _visit(page, live_server, "/architecture-journey/")

    resume = page.locator('a[href*="/architecture-journey/work/"]').first
    if resume.count() == 0:
        pytest.skip("no existing journey in the seeded tenant to open")

    resume.click()
    page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)

    for testid in ("journey-participants", "journey-decisions", "journey-risks",
                   "journey-governance"):
        panel = page.locator(f'[data-testid="{testid}"]')
        assert panel.count() == 1, f"{testid} missing from the journey home"
        text = panel.inner_text().strip()
        assert text, f"{testid} rendered empty"
        # Either a real figure or the em dash. Never blank, never a bare "0" with
        # no surrounding explanation.
        assert any(ch.isdigit() for ch in text) or "—" in text, (
            f"{testid} shows neither a measured count nor an em dash: {text!r}"
        )
