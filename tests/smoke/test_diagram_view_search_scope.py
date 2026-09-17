"""Diagram View on the Architecture Elements page must respect the search box.

Live-reported bug: clicking "Diagram View" always requested the viewpoint
diagram API with only limit/layer -- the page's own search term was never
passed through, so the diagram showed an arbitrary unrelated slice of
elements (including seed/test data) with almost no relationships among them,
regardless of what was searched. Fixed in
app/modules/architecture/routes/architect_ui_routes.py::viewpoint_diagram_data
(new `search` param, scoping to matched elements + their real one-hop
relationship neighbors) and app/templates/architecture/elements.html
(loadDiagram() now sends the page's searchQuery through).

This test targets the frontend half specifically (the request URL actually
carries the search term) via the real "Create Element" modal, the same UI
flow verified working in this session's own live-production audit. The
backend's element+neighbor scoping logic has its own direct test:
tests/test_viewpoint_diagram_search_scope.py.

Not run against the local portable Postgres in this session (documented risk
on this machine: local Flask dev server + Postgres + Playwright Chromium
stacked together has previously caused an OOM freeze requiring a power
cycle). CI's own `smoke` job (a fresh runner, not this machine) is the first
real execution of this file.
"""

import pytest

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def test_diagram_view_request_carries_the_search_term(browser, live_server, seeded):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["enterprise_architect"])
        page.goto(live_server + "/architecture/dashboard", timeout=PAGE_TIMEOUT)

        # Create one real element via the actual "Create Element" modal (the
        # same flow this session's audit already verified persists and
        # renders correctly).
        page.click('[data-testid="btn-create-element"]')
        page.wait_for_timeout(500)
        page.select_option('select[x-model="formData.element_type"]', value="Goal")
        unique_name = "QA-E2E Diagram Search Target"
        page.fill('input[placeholder="Element name"]', unique_name)
        page.click('button[aria-label="Submit"]')
        page.wait_for_timeout(1500)

        # Now go to the Elements page, search for it, and open Diagram View --
        # the request the click makes must carry the search term.
        page.goto(live_server + "/architecture/elements", timeout=PAGE_TIMEOUT)
        page.fill('input[placeholder="Search by name..."]', unique_name)
        page.wait_for_timeout(500)  # debounce

        with page.expect_request(
            lambda r: "/api/archimate/viewpoints/" in r.url and "/diagram" in r.url,
            timeout=PAGE_TIMEOUT,
        ) as req_info:
            page.click('button:has-text("Diagram View")')
        request = req_info.value

        assert "search=" in request.url, f"diagram request must carry the search term, got: {request.url}"
        assert "QA-E2E" in request.url, f"the actual typed search text must be in the request, got: {request.url}"
        response = request.response()
        assert response.ok
        payload = response.json()
        assert payload["success"] is True
    finally:
        page.close()


def test_diagram_view_carries_search_term_from_url_directly(browser, live_server, seeded):
    """A shared/bookmarked link (?q=...) must scope the diagram too, not just
    a term typed live into the search box.

    Live-reported bug: elements.html's init() only ever read `?layer=` from
    the URL, never `?q=`/`?search=` -- so landing on a link like
    /architecture/elements?q=Design%20partners left searchQuery empty and
    both fetchElements() and loadDiagram() ran unfiltered, showing the
    default unrelated top-30 slice regardless of the URL's own search term.
    """
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["enterprise_architect"])

        # Create a real element via the actual "Create Element" modal first,
        # same as the sibling test, so there is something real to find.
        page.goto(live_server + "/architecture/dashboard", timeout=PAGE_TIMEOUT)
        page.click('[data-testid="btn-create-element"]')
        page.wait_for_timeout(500)
        page.select_option('select[x-model="formData.element_type"]', value="Goal")
        unique_name = "QA-E2E URL Search Target"
        page.fill('input[placeholder="Element name"]', unique_name)
        page.click('button[aria-label="Submit"]')
        page.wait_for_timeout(1500)

        # Land directly on the elements page with the search term already in
        # the URL -- never touch the search input.
        import urllib.parse
        page.goto(
            live_server + "/architecture/elements?q=" + urllib.parse.quote(unique_name),
            timeout=PAGE_TIMEOUT,
        )
        page.wait_for_timeout(500)

        search_value = page.input_value('input[placeholder="Search by name..."]')
        assert unique_name == search_value, (
            f"landing on a ?q= URL must pre-fill the search box, got: {search_value!r}"
        )

        with page.expect_request(
            lambda r: "/api/archimate/viewpoints/" in r.url and "/diagram" in r.url,
            timeout=PAGE_TIMEOUT,
        ) as req_info:
            page.click('button:has-text("Diagram View")')
        request = req_info.value

        assert "search=" in request.url, f"diagram request must carry the URL's search term, got: {request.url}"
        assert "URL" in request.url, f"the actual URL-supplied search text must reach the request, got: {request.url}"
    finally:
        page.close()
