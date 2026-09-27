"""Real signed-in browser HTTP contract, not a fabricated template-picker test.

The smoke fixture intentionally has no ElementTemplate catalog. This checks the
fresh-install response through the actual server/database without network doubles.
"""
import pytest

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


@pytest.mark.parametrize("path", [
    "/dashboard/api/templates/frameworks",
    "/applications/api/templates/frameworks",
])
def test_empty_framework_catalog_is_a_successful_empty_collection(
    browser, live_server, seeded, path
):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["platform_admin"])
        response = page.goto(live_server + path, timeout=PAGE_TIMEOUT)
        assert response is not None
        assert response.status == 200, response.text()
        assert "application/json" in response.headers.get("content-type", "")
        assert response.json() == []
    finally:
        page.close()
