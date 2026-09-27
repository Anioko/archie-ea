"""ADM Kanban's toolbar had two "Roadmap" links pointing at the exact same
route (adm_kanban_view.adm_roadmap_timeline) -- one grouped with the other
analysis views (Gap Analysis, Plateau Roadmap), one bare-text link sandwiched
after the Sprint Planning button. Found 13 Sep 2026 in a full-app design
pass: not just visual crowding, a genuine duplicate control offering the
same destination twice with no distinguishing purpose. Removed the second,
worse-grouped occurrence.
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


def test_toolbar_links_to_each_destination_only_once(browser, live_server, seeded):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        page.goto(live_server + "/adm-kanban/", wait_until="networkidle", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(600)

        hrefs = page.eval_on_selector_all(
            "[data-testid='adm-kanban-toolbar'] a[href]",
            "els => els.map(e => e.getAttribute('href'))"
        )
        assert hrefs, "the ADM Kanban toolbar rendered no links at all -- selector may be stale"
        seen = {}
        for href in hrefs:
            seen[href] = seen.get(href, 0) + 1
        duplicates = {h: c for h, c in seen.items() if c > 1}
        assert not duplicates, (
            "the ADM Kanban toolbar links to the same destination more than "
            "once: %s -- each distinct URL should appear behind exactly one "
            "control, not two competing ones" % duplicates
        )
    finally:
        page.close()
