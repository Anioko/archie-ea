"""T-L1-IMPORT-OPS browser journey: upload the synthetic OEF fixture through
the real UI control at the canonical import screen, /architecture/import/oef,
reached from the element catalog's "Import model file" action, and assert the
elements and relationships actually persisted.

"Done means DEMONSTRATED": this clicks the real Import model file button and
the real upload form, rather than calling the service or the JSON API
directly. The second import screen this journey used to drive
(/solutions/import/archimate, a two-step preview/execute panel) has been
retired in favour of this one, per T-L1-IMPORT-OPS; its own round-trip
behaviour (relationship counts, custom-property preservation) stays covered
at the service level by tests/test_oef_import_roundtrip.py, which exercises
ArchiMateImportService directly.
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


def test_oef_import_via_catalog_button_persists_elements_and_relationships(browser, live_server, seeded):
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.set_default_timeout(PAGE_TIMEOUT)
    page = context.new_page()
    try:
        email = seeded["emails"]["solution_architect"]
        _login(page, live_server, email)

        page.goto(live_server + "/architecture/elements", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.click("[data-testid='import-oef-link']")
        page.wait_for_url("**/architecture/import/oef", timeout=PAGE_TIMEOUT)
        expect(page.locator("h1, h2", has_text="Import ArchiMate Model")).to_be_visible(timeout=PAGE_TIMEOUT)

        page.set_input_files("#oef_file", FIXTURE_PATH)
        page.click("button[type=submit]:has-text('Import Model')")

        expect(page.locator("h2", has_text="Import Result")).to_be_visible(timeout=PAGE_TIMEOUT)

        # The fixture's known shape (docs/buckets .../signup-to-first-answer-walk-v1.md):
        # 15 elements, 13 relationships, no errors.
        result_panel = page.locator("div", has=page.locator("h2", has_text="Import Result"))
        result_text = result_panel.first.inner_text()
        assert "15" in result_text, result_text
        assert "13" in result_text, result_text
        assert "No errors" in result_text, result_text

        # Reload a fresh page and confirm the import persisted server-side,
        # not just in this request's own response.
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
        # type/layer badges, not the API response.
        search_box = page.locator("input[placeholder='Search by name...']")
        search_box.fill("M-CON-10G-FREE-PILOTS")
        target_row = page.locator("tr[data-testid='element-row']", has_text="M-CON-10G-FREE-PILOTS")
        expect(target_row).to_have_count(1, timeout=PAGE_TIMEOUT)
        target_row.click()

        drawer_heading = page.locator("h2", has_text="M-CON-10G-FREE-PILOTS")
        expect(drawer_heading).to_be_visible(timeout=PAGE_TIMEOUT)

        detail_resp = page.request.get(
            live_server + "/archimate/api/elements/%s/detail" % element_id
        )
        assert detail_resp.ok
        detail = detail_resp.json()
        assert detail["name"] == "M-CON-10G-FREE-PILOTS"
        assert detail["layer"] == "motivation"
        assert detail["relationship_count"] >= 1

        rel_resp = page.request.get(live_server + "/archimate/api/relationships")
        assert rel_resp.ok
        rel_data = rel_resp.json()
        # api_success() wraps the payload under "data" (see CLAUDE.md
        # convention: unwrap with json.data ?? json).
        payload = rel_data.get("data", rel_data)
        total = payload.get("total", len(payload.get("relationships", [])))
        assert total >= 13, (
            "expected at least the fixture's 13 relationships to persist, got %r" % rel_data
        )
    finally:
        context.close()
