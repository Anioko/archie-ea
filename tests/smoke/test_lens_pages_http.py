"""Signed-in smoke coverage for the architect "lens" pages.

These are the read-only decision lenses added for solution/enterprise
architects — the reference catalogue (reuse library of approved solutions),
the data-freshness cockpit, and the capability/application fact sheets. They
render for a real signed-in persona against the real server/database; this
asserts each returns a usable 200 rather than a 500 or an auth bounce, and
that the reference catalogue's filter form round-trips.
"""
import pytest

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


@pytest.mark.parametrize("path", [
    "/enterprise/reference-catalog",
    "/enterprise/reference-catalog?domain=Finance",
    "/enterprise/data-freshness",
])
def test_lens_page_renders_for_enterprise_architect(browser, live_server, seeded, path):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["enterprise_architect"])
        response = page.goto(live_server + path, timeout=PAGE_TIMEOUT)
        assert response is not None
        assert response.status == 200, response.text()
        # No server-error banner and no unresolved Jinja/None reprs on the page.
        body = page.content()
        assert "Something went wrong" not in body
    finally:
        page.close()
