"""Authenticated browser requests cannot crash the element picker with a limit."""

import pytest

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def test_element_picker_survives_malformed_limits_in_browser(browser, live_server, seeded):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["solution_architect"])
        for query in ("limit=-1", "limit=0", "limit=abc", "limit=99999999999999999999",
                      "type=application_component&layer=application&limit=-1"):
            response = page.goto(live_server + "/api/archimate/elements?" + query, timeout=PAGE_TIMEOUT)
            assert response.status == 200
            payload = response.json()
            assert payload["success"] is True
            assert payload["count"] == len(payload["data"])
            assert payload["count"] <= 100
    finally:
        page.close()
