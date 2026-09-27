"""Technology classification must survive reload and a new authenticated session."""

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _assert_persisted_ring(page, element_id, ring):
    button = page.get_by_test_id(f"radar-reclassify-{element_id}")
    section = page.get_by_test_id(f"radar-section-{ring}")
    expect(section.get_by_test_id(f"radar-reclassify-{element_id}")).to_be_visible(
        timeout=PAGE_TIMEOUT
    )
    expect(button.locator("..").locator('select[name="ring"]')).to_have_value(ring)
    expect(page.get_by_test_id(f"radar-classify-{element_id}")).to_have_count(0)


def test_cto_classification_and_reclassification_persist(browser, live_server, seeded):
    element_id = seeded["ids"]["radar_element"]
    context = browser.new_context()
    try:
        page = context.new_page()
        _login(page, live_server, seeded["emails"]["cto"])
        response = page.goto(live_server + "/technology/radar/", timeout=PAGE_TIMEOUT)
        assert response.status == 200
        for ring, button_id in [
            ("trial", f"radar-classify-{element_id}"),
            ("hold", f"radar-reclassify-{element_id}"),
        ]:
            button = page.get_by_test_id(button_id)
            button.locator("..").locator('select[name="ring"]').select_option(ring)
            with page.expect_navigation(timeout=PAGE_TIMEOUT) as submitted:
                button.click()
            assert submitted.value.status == 200
            expect(page.get_by_role("heading", name="Tech Radar", exact=True)).to_be_visible()
            _assert_persisted_ring(page, element_id, ring)
            response = page.reload(timeout=PAGE_TIMEOUT)
            assert response.status == 200
            _assert_persisted_ring(page, element_id, ring)
    finally:
        context.close()

    # A fresh session rules out an optimistic display retained by the first page.
    context = browser.new_context()
    try:
        page = context.new_page()
        _login(page, live_server, seeded["emails"]["cto"])
        response = page.goto(live_server + "/technology/radar/", timeout=PAGE_TIMEOUT)
        assert response.status == 200
        _assert_persisted_ring(page, element_id, "hold")
    finally:
        context.close()
