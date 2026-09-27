"""An Enterprise Architect adds a real stakeholder and it persists.

/stakeholders/map's "Add Stakeholder" modal had no Person-or-Team input at
all - the whole x-if="!selectedPerson" / x-if="selectedPerson" block failed
to render, because the modal was rendered via {% block modals %}, which
admin_base.html deliberately places OUTSIDE the page's own
x-data="stakeholderMap()" div. Every field bound to that component's state
(selectedPerson, personSearch, form, aiPanel, ...) was therefore unscoped.

Fixed by moving both of this page's modals (add-stakeholder-modal,
ai-identify-modal) inside the x-data div instead of the separate
{% block modals %} - safe because the modal macro's root is position:fixed,
which escapes an ancestor's overflow-hidden regardless of DOM nesting depth.

Task-completion shape: add a stakeholder via the real modal (typing a
manual name, since the person-directory search depends on data this test
doesn't seed), then confirm it persisted via a fresh authenticated GET of
the same map-data API the page itself uses to render (the stakeholders are
D3-rendered into an SVG, not a plain text list, so this is the practical
equivalent of "reload and see it" for this page).
"""

import uuid

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT, PASSWORD

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    try:
        page.click("#submit", no_wait_after=True)
    except TypeError:
        page.locator("#submit").click()
    try:
        page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)
    except Exception:
        pass
    page.wait_for_timeout(800)
    assert "/account/login" not in page.url, "could not sign in as %s" % email


def test_add_stakeholder_survives_and_is_fetched_fresh(browser, live_server, seeded):
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    email = seeded["emails"]["enterprise_architect"]
    solution_id = seeded["ids"]["solution"]
    name = "SmkStakeholder %s" % uuid.uuid4().hex[:8]

    _login(page, live_server, email)
    page.goto(live_server + "/stakeholders/map", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(1000)

    page.select_option("select", str(solution_id))
    page.wait_for_timeout(1000)

    page.get_by_role("button", name="Add Stakeholder", exact=True).first.click()
    modal = page.locator("#add-stakeholder-modal")
    expect(modal).to_be_visible(timeout=PAGE_TIMEOUT)

    search_input = modal.get_by_label("Person or Team", exact=True)
    expect(search_input).to_be_visible(timeout=PAGE_TIMEOUT), (
        "regression: Person-or-Team input missing - the modal is unscoped again")
    search_input.fill(name)
    page.wait_for_timeout(600)

    manual_input = modal.get_by_label("Person name", exact=True)
    expect(manual_input).to_be_visible(timeout=PAGE_TIMEOUT)
    manual_input.fill(name)

    with page.expect_response(
        lambda r: r.url.endswith("/api/stakeholders/") and r.request.method == "POST",
        timeout=PAGE_TIMEOUT,
    ) as resp_info:
        modal.get_by_role("button", name="Add Stakeholder", exact=True).click()
    assert resp_info.value.status < 400, "add stakeholder POST failed: %d" % resp_info.value.status
    page.wait_for_timeout(1000)

    # Confirm it's fetched fresh from the server - the same API the page's own
    # loadData() calls - not just left over in client-side Alpine state.
    fresh = page.request.get(
        live_server + "/api/stakeholders/map-data?solution_id=%d" % solution_id
    )
    assert fresh.ok, "map-data GET failed: %d" % fresh.status
    body = fresh.text()
    assert name in body, "new stakeholder %r not present in a fresh map-data fetch" % name
    context.close()
