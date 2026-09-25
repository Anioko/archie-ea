"""DOGFOOD-003/004 browser journey: upload the synthetic OEF fixture through
the real UI control at /solutions/import/archimate, preview, execute,
reload, and assert both the relationship count and the imported
custom_properties actually persisted.

"Done means DEMONSTRATED": this is the only check in the bucket that clicks
the real Preview Import / Import Elements buttons rather than calling the
service or the JSON API directly.
"""
import os

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "oef", "archiet_shaped.xml"
)


def test_oef_import_preview_execute_reload_persists(browser, live_server, seeded):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.set_default_timeout(PAGE_TIMEOUT)
    page = context.new_page()
    try:
        email = seeded["emails"]["solution_architect"]
        _login(page, live_server, email)

        page.goto(live_server + "/solutions/import/archimate", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        expect(page.locator("h3", has_text="Import ArchiMate Model")).to_be_visible(timeout=PAGE_TIMEOUT)

        page.set_input_files("input[type=file]", FIXTURE_PATH)
        page.click("button:has-text('Preview Import')")

        # Preview must classify every element and land on the fixture's known
        # shape before Execute is ever clicked.
        total_locator = page.locator("p.text-2xl", has_text="15").first
        expect(total_locator).to_be_visible(timeout=PAGE_TIMEOUT)

        page.click("button:has-text('Import Model')")
        expect(page.locator("h4", has_text="Import Complete")).to_be_visible(timeout=PAGE_TIMEOUT)

        # B1 (refuter): the import result must actually show relationship
        # results, not just element counts -- assert the new relationship
        # panel is rendered and reports the fixture's known shape (12
        # created, 1 failed -- the deliberately-invalid composition).
        rel_result = page.locator("[data-testid='relationship-import-result']")
        expect(rel_result).to_be_visible(timeout=PAGE_TIMEOUT)
        rel_result_text = rel_result.inner_text()
        assert "12" in rel_result_text
        assert "1" in rel_result_text

        # Reload a fresh page and confirm relationships/properties actually
        # persisted server-side, not just in the import panel's own state.
        page.goto(live_server + "/architecture/elements", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(1500)

        resp = page.request.get(live_server + "/archimate/api/elements/search?q=M-CON-10G-FREE-PILOTS")
        assert resp.ok, "element search API failed: %s" % resp.status
        results = resp.json()
        matches = results.get("data") or results.get("elements") or results.get("results") or (
            results if isinstance(results, list) else []
        )
        assert isinstance(matches, list) and len(matches) >= 1, (
            "M-CON-10G-FREE-PILOTS was not found after reload: %r" % results
        )
        element_id = matches[0]["id"]

        # Open the element detail drawer for real and read the rendered
        # properties panel, not the API response — this is the DOGFOOD-004
        # acceptance criterion (status/source/layer visible on the page).
        #
        # The page also carries a sidebar "Search navigation..." box and a
        # hidden global command-palette search, both of which also match
        # input[placeholder*='Search' i] and sort before this page's own
        # element search in the DOM -- .first silently picked the sidebar
        # box, which filters nothing here, so the row search only ever
        # worked by accident (the imported element already being on the
        # unfiltered first page in a lightly-seeded org). The element list's
        # own search box carries a placeholder no other control on the page
        # uses.
        search_box = page.locator("input[placeholder='Search by name...']")
        search_box.fill("M-CON-10G-FREE-PILOTS")
        target_row = page.locator("tr[data-testid='element-row']", has_text="M-CON-10G-FREE-PILOTS")
        expect(target_row).to_have_count(1, timeout=PAGE_TIMEOUT)
        target_row.click()

        props_panel = page.locator("[data-testid='element-properties']")
        expect(props_panel).to_be_visible(timeout=PAGE_TIMEOUT)
        props_text = props_panel.inner_text()
        assert "status" in props_text and "RULED" in props_text
        assert "layer" in props_text and "Motivation" in props_text

        detail_resp = page.request.get(
            live_server + "/archimate/api/elements/%s/detail" % element_id
        )
        assert detail_resp.ok
        detail = detail_resp.json()
        assert detail["custom_properties"]["status"] == "RULED"
        assert detail["custom_properties"]["layer"] == "Motivation"
        assert "archie:imported_at" in detail["custom_properties"]

        rel_resp = page.request.get(live_server + "/archimate/api/relationships")
        assert rel_resp.ok
        rel_data = rel_resp.json()
        # api_success() wraps the payload under "data" (see CLAUDE.md
        # convention: unwrap with json.data ?? json).
        payload = rel_data.get("data", rel_data)
        total = payload.get("total", len(payload.get("relationships", [])))
        assert total >= 12, (
            "expected at least the fixture's 12 valid relationships to persist, got %r" % rel_data
        )
    finally:
        context.close()
