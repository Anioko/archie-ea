"""Two empty-state defects found in a full-app design pass on 13 Sep 2026,
both from screens outside the previously-reviewed sample.

- /usage-analytics/: a successful fetch with zero features/events left both
  tables rendering only their header row -- no message, indistinguishable
  from broken. The page's own JS already distinguished FAILED-fetch from
  merely-empty for the error path (showTableError), but never for the
  legitimately-empty-and-successful path. Fixed by adding an honest "No
  ... recorded yet" row for that case in each table.

- /stakeholders/map: the "+ Add First Stakeholder" button rendered even
  before a solution was selected, and clicking it in that state immediately
  failed with a "Select a solution first" toast -- a primary CTA offered in
  a state where it cannot succeed. Fixed by hiding it until a solution is
  selected (x-show="selectedSolution"), matching the same condition already
  used for the empty-state copy right above it.
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


def test_usage_analytics_empty_tables_say_so(browser, live_server, seeded):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        page.goto(live_server + "/usage-analytics/", wait_until="networkidle", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(1000)

        usage_rows = page.locator("#usage-table-body tr")
        events_rows = page.locator("#events-table-body tr")
        assert usage_rows.count() >= 1, (
            "the feature-usage table has zero rows and no empty-state message -- "
            "a bare header row is indistinguishable from a broken page"
        )
        assert events_rows.count() >= 1, (
            "the recent-events table has zero rows and no empty-state message"
        )
        # Whatever rendered must actually say something, not just exist as an
        # empty <tr> -- guards against a future regression that adds a row
        # but leaves its cell blank.
        assert usage_rows.first.inner_text().strip(), "usage table's row has no visible text"
        assert events_rows.first.inner_text().strip(), "events table's row has no visible text"
    finally:
        page.close()


def test_stakeholder_map_hides_add_button_until_solution_selected(browser, live_server, seeded):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["solution_architect"])
        page.goto(live_server + "/stakeholders/map", wait_until="networkidle", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(800)

        add_button = page.get_by_role("button", name="Add First Stakeholder")
        assert add_button.count() == 0 or not add_button.first.is_visible(), (
            "'+ Add First Stakeholder' is visible before a solution is "
            "selected -- clicking it here can only fail (a stakeholder "
            "cannot be linked to no solution), so it must not be offered yet"
        )
    finally:
        page.close()
