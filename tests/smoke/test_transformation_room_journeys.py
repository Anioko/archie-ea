"""Browser-level Transformation Room deep-link and responsive-shell proof."""

import pytest

from .conftest import PAGE_TIMEOUT, PASSWORD
from .test_archetype_journeys import PAGE_STATE, _login, _visit

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


@pytest.mark.parametrize("page", [390, 1024], indirect=True)
def test_transformation_intake_is_accessible_and_responsive(
    page, live_server, seeded
):
    _login(page, live_server, seeded["emails"]["enterprise_architect"])
    response, state = _visit(page, live_server, "/solutions/new-programme")

    assert response.status < 400
    assert page.locator('main form[action="/solutions/create-programme"]').count() == 1
    assert page.get_by_role("combobox", name="Programme owner").count() == 1
    assert page.get_by_role("button", name="Create programme").count() == 1
    assert state["unnamed"] == []
    assert state["overflow"] == 0
    assert not page.console_errors
    assert not page.page_errors
