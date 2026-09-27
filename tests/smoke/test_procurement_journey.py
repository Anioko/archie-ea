"""Create -> edit -> persist journey for Procurement vendor contracts.

Wave 3. Prior recon: `app/modules/procurement/crud_routes.py` is a full
server-rendered CRUD surface added 2026-07-31 (its own module docstring:
before that date the procurement persona could read but never create/amend a
contract, so every screen on a new tenant was permanently empty). Routes used
here: `/procurement/contracts/new` (GET/POST, create), `/procurement/contracts`
(list), `/procurement/contracts/<id>/edit` (GET/POST, amend). Guarded by
`@requires_procurement`; role_access.py's PROCUREMENT-owning role is
ROLE_PROCUREMENT, seeded as the `procurement` archetype in
tests/smoke/conftest.py.

Follows tests/smoke/test_business_case_journey.py's pattern: real login,
`expect_response` on the actual POST, and a page reload before the final
persistence assertion.
"""

import re
import time

import pytest
from playwright.sync_api import expect

from tests.smoke.conftest import PASSWORD

PAGE_TIMEOUT = 30000


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").click()
    page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)


@pytest.mark.smoke
@pytest.mark.journey
def test_procurement_contract_create_edit_and_persist(browser, live_server, seeded):
    """A procurement lead creates a vendor contract, confirms it appears in
    the contracts list, edits the owner, and confirms the edit survived a
    reload of the detail page."""
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    page.on("dialog", lambda d: d.accept())
    try:
        _login(page, live_server, seeded["emails"]["procurement"])

        name = "Smoke Contract %d" % int(time.time() * 1000)
        create_url = live_server + "/procurement/contracts/new"
        list_url = live_server + "/procurement/contracts"

        # ---- CREATE (POST /procurement/contracts/new) -----------------------
        page.goto(create_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.fill("#contract_name", name)
        page.fill("#start_date", "2026-01-01")
        page.fill("#contract_owner", "Smoke Journey Owner")
        with page.expect_response(
            lambda r: "/procurement/contracts/new" in r.url and r.request.method == "POST",
            timeout=PAGE_TIMEOUT,
        ) as created:
            page.locator('form:not([action*="csrf"]) button[type="submit"]').first.click()
        assert created.value.status < 400, f"create POST failed: {created.value.status}"
        page.wait_for_url(re.compile(r"/procurement/contracts/\d+$"), timeout=PAGE_TIMEOUT)
        detail_url = page.url
        contract_id = re.search(r"/contracts/(\d+)$", detail_url).group(1)

        expect(page.get_by_text(name, exact=False).first).to_be_visible(timeout=PAGE_TIMEOUT)

        # ---- Row appears in the contracts list -------------------------------
        page.goto(list_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        expect(page.get_by_text(name, exact=False).first).to_be_visible(timeout=PAGE_TIMEOUT)

        # ---- PERSISTENCE (fresh GET of the detail page) ----------------------
        page.goto(detail_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        expect(page.get_by_text(name, exact=False).first).to_be_visible(timeout=PAGE_TIMEOUT)
        expect(page.get_by_text("Smoke Journey Owner", exact=False)).to_be_visible(
            timeout=PAGE_TIMEOUT
        )

        # ---- EDIT (POST /procurement/contracts/<id>/edit) ---------------------
        edit_url = live_server + f"/procurement/contracts/{contract_id}/edit"
        page.goto(edit_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        owner_field = page.locator("#contract_owner")
        owner_field.fill("")
        owner_field.fill("Edited Smoke Owner")
        with page.expect_response(
            lambda r: "/edit" in r.url and r.request.method == "POST",
            timeout=PAGE_TIMEOUT,
        ) as edited:
            page.locator('button[type="submit"]').first.click()
        assert edited.value.status < 400, f"edit POST failed: {edited.value.status}"

        # ---- PERSISTENCE (reload the detail page -- edit must survive it) ---
        page.goto(detail_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        expect(page.get_by_text("Edited Smoke Owner", exact=False)).to_be_visible(
            timeout=PAGE_TIMEOUT
        )
    finally:
        context.close()
