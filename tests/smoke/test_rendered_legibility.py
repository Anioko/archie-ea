"""Can a person read the screen? Nothing else in this repository asks.

Written 31 Aug 2026, after the owner sent a screenshot of this product's own
sidebar in its collapsed state: several destinations behind what looked like the
same glyph, and labels clipped to "All mo..." and "Bui...". Seventy gates were
green over it.

They were green because every one of them reads SOURCE. `design-tokens` checks
the colours are tokens. `dead-interactions` checks the link fires.
`template-syntax` checks it parses. The axe-core audit checks WCAG rules, and
passes a link whose accessible name comes from the very text that is visually
clipped -- the DOM is correct, the rendered pixel is unusable, and axe has no
opinion about the difference.

So this file exists to do the one thing the estate could not: open the page in a
browser, put it in the state a user actually leaves it in, and measure what is
legible. Three checks, each corresponding to the screenshot:

    clipped without a tooltip   "All mo..." with no way to discover the rest
    unlabelled when collapsed   an icon rail where nothing says what an icon is
    one icon, many destinations eight entries that become the same button

The collapsed sidebar is the state under test because it is sticky: it is stored
in `$store.sidebar.collapsed` and survives navigation, so a user who collapses it
once sees every subsequent page this way. A default-state-only check would never
have found this, which is the general lesson -- the defaults are the states
nobody ships broken.

These are ratcheted against rendered_legibility_baseline.json rather than
asserted at zero, for the same reason the static ratchets exist: the debt is
real, it is being paid down, and a gate that fails on day one gets disabled.
"""

import json
import os

import pytest

from .conftest import ARCHETYPES, PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "rendered_legibility_baseline.json")

# Where every persona lands, and therefore the screen they see most.
LANDING = "/dashboard/overview"

# Text is measured as clipped when its content is wider than its box. A pixel of
# slack absorbs sub-pixel layout rounding, which otherwise reports every element.
CLIP_SLACK = 2

MEASURE = """() => {
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  };
  const named = (el) => {
    // What survives the visible text being hidden or clipped.
    const a = el.closest('a,button') || el;
    return !!(a.getAttribute('title') || a.getAttribute('aria-label')
              || a.getAttribute('aria-labelledby'));
  };

  // 1. Text clipped by its own box, with nothing offering the full string.
  const clipped = [];
  for (const el of document.querySelectorAll('nav a, nav span, aside a, aside span')) {
    if (!visible(el)) continue;
    const text = (el.textContent || '').trim();
    if (!text) continue;
    if (el.scrollWidth > el.clientWidth + SLACK && !named(el)) {
      clipped.push(text.slice(0, 40));
    }
  }

  // 2. Icon-only controls in the nav with no accessible name at all.
  const unlabelled = [];
  for (const a of document.querySelectorAll('nav a, aside a')) {
    if (!visible(a)) continue;
    const text = (a.textContent || '').trim();
    const showsText = text.length > 0 && a.scrollWidth <= a.clientWidth + SLACK;
    if (!showsText && !named(a)) {
      unlabelled.push(a.getAttribute('href') || '(no href)');
    }
  }

  // 3. One icon serving several destinations in the same rendered menu.
  const byIcon = {};
  for (const a of document.querySelectorAll('nav a, aside a')) {
    if (!visible(a)) continue;
    const icon = a.querySelector('[data-lucide]');
    if (!icon) continue;
    const key = icon.getAttribute('data-lucide');
    const href = a.getAttribute('href') || '(no href)';
    (byIcon[key] = byIcon[key] || new Set()).add(href);
  }
  const ambiguous = [];
  for (const [icon, hrefs] of Object.entries(byIcon)) {
    if (hrefs.size > 1) ambiguous.push(icon + ' -> ' + hrefs.size + ' destinations');
  }

  return {clipped, unlabelled, ambiguous};
}"""


def _load_baseline():
    try:
        with open(BASELINE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _login(page, base, email):
    """Sign in the way a user does. Mirrors tests/smoke/test_archetype_journeys.py."""
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", force=True, no_wait_after=True)
    except TypeError:
        page.locator("#submit").dispatch_event("click")
    page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)


def _collapse_sidebar(page):
    """Put the rail in the state the screenshot was taken in.

    Setting the Alpine store directly rather than hunting for the toggle: the
    control moves between templates, and what is under test is the COLLAPSED
    RENDERING, not the button that gets you there (dead-interactions already
    covers the button).
    """
    page.evaluate(
        "() => { if (window.Alpine && Alpine.store('sidebar')) "
        "{ Alpine.store('sidebar').collapsed = true; } }"
    )
    page.wait_for_timeout(400)  # let the width transition settle before measuring


@pytest.mark.parametrize("archetype", ARCHETYPES)
def test_the_collapsed_sidebar_stays_readable(archetype, live_server, seeded, browser):
    """Every persona, in the state they leave the sidebar in."""
    base = live_server
    page = browser.new_page()
    try:
        _login(page, base, seeded["emails"][archetype])
        page.goto(base + LANDING, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        _collapse_sidebar(page)

        result = page.evaluate(MEASURE.replace("SLACK", str(CLIP_SLACK)))
    finally:
        page.close()

    if os.environ.get("SMOKE_WRITE_LEGIBILITY_BASELINE") == "1":
        # Capture the current truth so the ratchet starts from a measurement
        # rather than a guess. Never set in CI -- that would make the gate
        # rewrite its own baseline and pass forever.
        current = _load_baseline()
        current[archetype] = {k: len(v) for k, v in result.items()}
        with open(BASELINE_PATH, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=2, sort_keys=True)
            fh.write(chr(10))
        pytest.skip("baseline captured for %s: %s" % (archetype, current[archetype]))

    baseline = _load_baseline().get(archetype, {})
    for kind, message in (
        ("clipped", "text clipped with no title or aria-label offering the full string"),
        ("unlabelled", "nav links showing no text and carrying no accessible name"),
        ("ambiguous", "icons serving more than one destination in the same menu"),
    ):
        found = result[kind]
        allowed = baseline.get(kind, 0)
        assert len(found) <= allowed, (
            "%s: %d %s (baseline %d).\n"
            "Collapsed, this is what the user is looking at:\n  %s"
            % (archetype, len(found), message, allowed, "\n  ".join(str(f) for f in found[:12]))
        )
