"""Signed-in smoke coverage for the architect "lens" pages.

These are the read-only decision lenses added for solution/enterprise
architects — the reference catalogue (reuse library of approved solutions)
and the data-freshness cockpit. They render for a real signed-in persona
against the real server/database.

"Done means DEMONSTRATED": this does not merely assert 200. It drives the
reference catalogue's real filter form as an enterprise architect would —
finding the seeded approved solution, filtering it in by domain, and
confirming a non-matching filter empties the results — so a dead Save-style
regression (a filter that does nothing) is caught, not just a 500.
"""
import pytest

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

_REF_NAME_FRAGMENT = "Smoke reference payroll integration"


def test_data_freshness_cockpit_renders(browser, live_server, seeded):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["enterprise_architect"])
        response = page.goto(live_server + "/enterprise/data-freshness", timeout=PAGE_TIMEOUT)
        assert response is not None
        assert response.status == 200, response.text()
        assert "Something went wrong" not in page.content()
    finally:
        page.close()


def test_impact_graph_draws_the_dependency_nodes(browser, live_server, seeded):
    """The impact graph is d3-rendered from a fetch — a broken endpoint or a JS
    error leaves the SVG empty while the page still returns 200. Assert the
    graph actually draws the seeded source + target nodes."""
    element_id = seeded["ids"]["impact_source_element"]
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["enterprise_architect"])
        response = page.goto(
            live_server + "/archimate/elements/%s/impact" % element_id, timeout=PAGE_TIMEOUT)
        assert response is not None
        assert response.status == 200, response.text()
        # d3 appends one <g> with a <circle> per node once the fetch resolves.
        page.wait_for_selector("#impact-svg circle", timeout=PAGE_TIMEOUT)
        circles = page.locator("#impact-svg circle").count()
        assert circles >= 2, "expected the source + target nodes, got %d" % circles
        # The counts line must leave its Loading… placeholder.
        assert page.locator("#impact-counts").inner_text().strip() != "Loading…"
    finally:
        page.close()


def test_reference_catalogue_lists_and_filters_approved_solutions(browser, live_server, seeded):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["enterprise_architect"])

        # 1. The approved seed solution is present; the draft one is not.
        response = page.goto(live_server + "/enterprise/reference-catalog", timeout=PAGE_TIMEOUT)
        assert response is not None
        assert response.status == 200, response.text()
        body = page.content()
        assert "Something went wrong" not in body
        assert _REF_NAME_FRAGMENT in body, "approved solution should appear in the catalogue"
        assert "Smoke solution blueprint" not in body, "draft solution must NOT be a reference"

        # 2. Filtering by its real domain keeps it (the control actually works).
        page.select_option("select#domain", "Finance")
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
        assert _REF_NAME_FRAGMENT in page.content()

        # 3. A non-matching domain empties the results — proves the filter is
        #    real, not decorative. Reached by URL because the option only exists
        #    when such a domain is seeded.
        page.goto(live_server + "/enterprise/reference-catalog?domain=NoSuchDomain",
                  timeout=PAGE_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
        assert _REF_NAME_FRAGMENT not in page.content()
    finally:
        page.close()
