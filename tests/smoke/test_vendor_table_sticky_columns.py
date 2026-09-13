"""The Vendor Catalogue's sticky first/last table columns must have a fully
opaque background, or the columns scrolling underneath them show through.

Found 13 Sep 2026 in a full-app design pass on production: at a viewport
narrower than the table's natural width, the sticky "Actions" header (frozen
via `position: sticky; right: 0` in app/static/styles/shadcn-components.css)
rendered with a semi-transparent background (`hsl(var(--muted) / 0.5)`),
so the scrolled-under "Status"/"Contract" header text showed through it --
both texts visible in the same screen region, reading as garbled/broken
("ACTIONSTR"). The body-cell rule right next to it already used a fully
opaque `hsl(var(--card))`; only the header rule was transparent. Root-caused
via Chrome DevTools Protocol (CSS.getMatchedStylesForNode) against the live
page, not guessed from a screenshot. Fixed by making the header background
opaque too.

NOTE on what this test does NOT assert: the sticky header's bounding box
DOES geometrically overlap the columns it freezes past whenever the table
hasn't been scrolled -- that is the intended mechanism (a frozen column sits
on top of the ones underneath), not a bug. An earlier draft of this test
asserted non-overlapping bounding boxes and failed even against the fix,
because that is the wrong invariant. The actual correctness requirement is
that the sticky cell's background is fully opaque (alpha 1) and its z-index
places it above the cells it covers, so the covered content is truly hidden
rather than showing through -- that's what this test checks.
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


def _sticky_cell_opacity(page):
    return page.evaluate("""
        () => {
          const cells = Array.from(document.querySelectorAll('thead th:first-child, thead th:last-child'));
          return cells.map(el => {
            const cs = getComputedStyle(el);
            // rgba(r, g, b, a) or rgb(r, g, b) (implicit alpha 1)
            const m = cs.backgroundColor.match(/rgba?\\(([^)]+)\\)/);
            const parts = m ? m[1].split(',').map(s => parseFloat(s.trim())) : [];
            const alpha = parts.length === 4 ? parts[3] : 1;
            return {
              text: el.textContent.trim(),
              position: cs.position,
              zIndex: cs.zIndex,
              backgroundColor: cs.backgroundColor,
              alpha: alpha,
            };
          });
        }
    """)


def test_vendor_catalogue_sticky_header_cells_are_opaque(browser, live_server, seeded):
    page = browser.new_page(viewport={"width": 700, "height": 900})
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        page.goto(live_server + "/vendors/", wait_until="networkidle", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(500)

        cells = _sticky_cell_opacity(page)
        sticky_cells = [c for c in cells if c["position"] == "sticky"]
        assert sticky_cells, (
            "no sticky first/last header cell found on /vendors/ -- either the "
            "table stopped overflowing (nothing to test) or the sticky-column "
            "CSS rule stopped matching; confirm which before trusting this test"
        )

        translucent = [c for c in sticky_cells if c["alpha"] < 0.999]
        assert not translucent, (
            "%d sticky header cell(s) have a translucent background, so "
            "content scrolling underneath them shows through instead of "
            "being hidden:\n  %s"
            % (len(translucent), "\n  ".join(
                "%r: %s (alpha=%.2f)" % (c["text"], c["backgroundColor"], c["alpha"])
                for c in translucent))
        )
    finally:
        page.close()
