"""Every supported role can use the actual application's brand-home link."""

import pytest
from playwright.sync_api import expect

from .conftest import ARCHETYPES, PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


@pytest.mark.parametrize("role", ARCHETYPES)
def test_brand_home_click_reaches_dashboard_for_every_role(browser, live_server, seeded, role):
    """Real login, rendered shell and GET navigation; no request interception."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        _login(page, live_server, seeded["emails"][role])
        response = page.goto(live_server + "/dashboard/overview", timeout=PAGE_TIMEOUT)
        assert response.status == 200
        sidebar = page.get_by_test_id("sidebar")
        # Locate the actual brand, not the separate Dashboard Overview nav item.
        brand = sidebar.get_by_role("link").filter(has=page.locator(".sidebar-app-name"))
        expect(brand).to_have_count(1)
        expect(brand).to_be_visible()
        with page.expect_navigation(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT) as navigation:
            brand.click()
        assert navigation.value.status == 200, f"Brand home rejected {role}"
        expect(page).to_have_url(live_server + "/dashboard/overview")
        expect(page.get_by_role("heading", name="Dashboard", exact=True, level=1)).to_be_visible()
        if role == "platform_admin":
            command_center = page.get_by_test_id("sidebar").get_by_role("link", name="Command Center", exact=True)
            expect(command_center).to_be_visible()
            expect(command_center).to_have_attribute("href", "/admin/")
    finally:
        page.close()
