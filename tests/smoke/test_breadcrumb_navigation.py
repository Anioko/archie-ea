"""Reported duplicate trails must reduce to one working navigation trail."""

import pytest
from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


@pytest.mark.parametrize("path", [
    "/applications/rationalization/enrich",
    "/applications/rationalization/tracking",
    "/applications/rationalization/workbench",
    "/ea-workflows/definitions",
    "/ea-workflows/phase/1/viewpoint",
])
def test_single_breadcrumb_and_working_parent_navigation(browser, live_server, seeded, path):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["solution_architect"])
        response = page.goto(live_server + path, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        assert response.status == 200
        trail = page.get_by_role("navigation", name="Breadcrumb", exact=True)
        assert trail.count() == 1
        assert trail.is_visible()
        parent = trail.get_by_role("link").first
        with page.expect_navigation(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT) as navigation:
            parent.click()
        assert navigation.value.status == 200
        assert page.get_by_role("heading", level=1).count() == 1
    finally:
        page.close()
