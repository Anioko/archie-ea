"""Directory filtering must change the visible list and preserve navigation."""

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def test_module_filter_empty_clear_and_destination(browser, live_server, seeded):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        response = page.goto(live_server + "/modules/", timeout=PAGE_TIMEOUT)
        assert response.status == 200
        directory = page.get_by_test_id("modules-directory")
        initial_count = directory.locator("a:visible").count()
        assert initial_count > 1
        search = page.get_by_role("searchbox", name="Search modules by name")
        search.fill("Data Lineage")
        expect(directory.locator("a:visible")).to_have_count(1, timeout=PAGE_TIMEOUT)
        expect(directory.get_by_role("link", name="Data Lineage", exact=True)).to_be_visible()
        search.fill("qa-no-such-module-489217")
        expect(directory.locator("a:visible")).to_have_count(0)
        expect(page.get_by_test_id("modules-directory-no-match")).to_be_visible()
        page.get_by_role("button", name="Clear the module filter", exact=True).click()
        expect(search).to_have_value("")
        expect(directory.locator("a:visible")).to_have_count(initial_count)
        expect(page.get_by_test_id("modules-directory-no-match")).to_be_hidden()
        search.fill("Data Lineage")
        expect(directory.locator("a:visible")).to_have_count(1)
        with page.expect_navigation(timeout=PAGE_TIMEOUT) as navigation:
            directory.get_by_role("link", name="Data Lineage", exact=True).click()
        assert navigation.value.status == 200
        expect(page.get_by_role("heading", level=1, name="Data Lineage", exact=True)).to_be_visible()
    finally:
        page.close()


def test_vendor_application_mapping_is_findable_and_opens(browser, live_server, seeded):
    """T-VEND-1: the vendors package's one honest page has no sidebar link;
    it must be findable from the module directory by name and open the real
    all-vendors application mapping, not the per-vendor page."""
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        response = page.goto(live_server + "/modules/", timeout=PAGE_TIMEOUT)
        assert response.status == 200
        directory = page.get_by_test_id("modules-directory")
        search = page.get_by_role("searchbox", name="Search modules by name")
        search.fill("Vendor Application Mapping")
        expect(directory.locator("a:visible")).to_have_count(1, timeout=PAGE_TIMEOUT)
        link = directory.get_by_role("link", name="Vendor Application Mapping", exact=True)
        expect(link).to_be_visible()
        with page.expect_navigation(timeout=PAGE_TIMEOUT) as navigation:
            link.click()
        assert navigation.value.status == 200
        assert page.url.endswith("/vendors/integration/mapping"), page.url
        expect(page.get_by_role("heading", level=1, name="All Vendors", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Back to Vendors", exact=True)).to_be_visible()
    finally:
        page.close()
