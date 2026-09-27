"""The authenticated RoPA page uses the application shell and generates its table."""

import pytest
from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def test_ropa_generation_from_application_shell(browser, live_server, seeded):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["data_architect"])
        response = page.goto(live_server + "/genome/data/ropa",
                             wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        assert response.status == 200
        assert page.get_by_role("main").count() == 1
        assert page.get_by_role("link", name="About", exact=True).count() == 0
        with page.expect_navigation(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT) as navigation:
            page.get_by_role("button", name="Generate RoPA", exact=True).click()
        assert navigation.value.status == 200
        page.get_by_role("heading", name="Record of Processing Activities", exact=True).wait_for(
            state="visible", timeout=PAGE_TIMEOUT
        )
        assert page.get_by_role("main").count() == 1
    finally:
        page.close()
