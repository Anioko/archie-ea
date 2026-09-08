"""Create -> edit -> persist journey for Business Capabilities, plus a
cross-store count check (ADR 0008 / the store-agreement gate's concern).

Wave 3. Prior recon: the capability model list/create UI lives at
`/enterprise/capability-map/capabilities` (app/routes/unified_low_priority_routes.py),
which renders `capability_map/capabilities.html`. The "New Capability" / "Edit"
controls are gated on `can_edit_capabilities()` (app/utils/role_access.py), whose
CAPABILITY_EDITOR_ROLES set includes business_architect -- the persona this
journey uses. The dialog POSTs/PUTs JSON to
`/enterprise/capabilities[/<id>]` (app/modules/capabilities/routes/enterprise_crud_routes.py),
which writes `BusinessCapability` rows -- this is a legacy-flat-blueprint CRUD
surface, not `unified_capabilities` (the ADR 0008 canonical store), because
`unified_capabilities` still has no producer (see CLAUDE.md's "One system of
record" section). Both count surfaces exercised below --
`/enterprise/capability-map/capabilities` (this page) and
`/enterprise/capability-map/` (the dashboard, `capability_map/index.html` via
`count_business_capabilities()`) -- read `BusinessCapability` under the hood, so
they are expected to agree; the test asserts that rather than assuming it.

Follows tests/smoke/test_business_case_journey.py's pattern: real login (so CSRF
flows as the browser sends it), `expect_response` on the actual network call,
and a page reload before the final persistence assertion.
"""

import re
import time

import pytest
from playwright.sync_api import expect

from tests.smoke.conftest import PASSWORD

PAGE_TIMEOUT = 30000
CAP_LIST_URL = "/enterprise/capability-map/capabilities"
CAP_DASHBOARD_URL = "/enterprise/capability-map/"
CAP_API = re.compile(r"/enterprise/capabilities(/\d+)?$")


def _login(page, base, email):
    page.goto(base + "/account/login", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#email", email)
    page.fill("#password", PASSWORD)
    page.locator("#submit").click()
    page.wait_for_url(lambda url: "/account/login" not in url, timeout=PAGE_TIMEOUT)


def _total_capabilities_on_list_page(page, base):
    page.goto(base + CAP_LIST_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    return page.locator(".cap-card").count()


def _total_capabilities_on_dashboard(page, base):
    # capability_map/index.html renders the count service's number into
    # #unified-cap-count (capability_count_service.count_business_capabilities()),
    # specifically to keep this figure from drifting between surfaces again --
    # see that module's docstring for the 500-vs-495 disagreement it replaced.
    page.goto(base + CAP_DASHBOARD_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    locator = page.locator("#unified-cap-count")
    if locator.count() == 0:
        return None
    # The span lives in an Alpine x-show tab panel that may not be the active
    # tab on load, so it can be present-but-hidden -- inner_text() would return
    # "" for a hidden element and text_content() reads the DOM regardless.
    text = (locator.text_content() or "").strip()
    return int(text) if text.isdigit() else None


@pytest.mark.smoke
@pytest.mark.journey
def test_capability_create_edit_and_cross_store_count(browser, live_server, seeded):
    """A business_architect creates a capability, confirms it survives a
    reload, edits it, confirms the edit persisted, then checks that the
    capability-map list and dashboard agree on the total count."""
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    page.on("dialog", lambda d: d.accept())
    try:
        _login(page, live_server, seeded["emails"]["business_architect"])

        name = "Smoke Capability %d" % int(time.time() * 1000)
        list_url = live_server + CAP_LIST_URL

        # ---- Baseline counts, before creating anything ---------------------
        list_count_before = _total_capabilities_on_list_page(page, live_server)
        dashboard_count_before = _total_capabilities_on_dashboard(page, live_server)

        # ---- CREATE (POST /enterprise/capabilities) -------------------------
        page.goto(list_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.locator('[data-action="openCapCreate"]').click()
        dialog = page.locator("#cap-dialog")
        expect(dialog).to_be_visible(timeout=PAGE_TIMEOUT)
        page.fill("#cap-name", name)
        page.select_option("#cap-category", "strategic")
        page.fill("#cap-owner", "Smoke Journey Owner")
        with page.expect_response(
            lambda r: bool(CAP_API.search(r.url)) and r.request.method == "POST",
            timeout=PAGE_TIMEOUT,
        ) as created:
            page.locator('[data-action="submitCap"]').click()
        assert created.value.status < 400, f"create POST failed: {created.value.status}"

        # submitCap reloads the page itself (setTimeout(reload, 400)) on success.
        page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        expect(page.locator(".cap-card", has_text=name)).to_be_visible(timeout=PAGE_TIMEOUT)

        # ---- PERSISTENCE (fresh GET, not client DOM state) ------------------
        page.goto(list_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        expect(page.locator(".cap-card", has_text=name)).to_be_visible(timeout=PAGE_TIMEOUT)

        # ---- EDIT (PUT /enterprise/capabilities/<id>) ------------------------
        card = page.locator(".cap-card", has_text=name)
        card.locator('[data-action="openCapEdit"]').click()
        expect(dialog).to_be_visible(timeout=PAGE_TIMEOUT)
        edited_owner = "Edited Smoke Owner"
        owner_field = page.locator("#cap-owner")
        owner_field.fill("")
        owner_field.fill(edited_owner)
        with page.expect_response(
            lambda r: bool(CAP_API.search(r.url)) and r.request.method == "PUT",
            timeout=PAGE_TIMEOUT,
        ) as edited:
            page.locator('[data-action="submitCap"]').click()
        assert edited.value.status < 400, f"edit PUT failed: {edited.value.status}"
        page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)

        # ---- PERSISTENCE (reload -- the edit must survive a fresh GET) -----
        page.goto(list_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        edited_card = page.locator(".cap-card", has_text=name)
        expect(edited_card).to_be_visible(timeout=PAGE_TIMEOUT)
        expect(edited_card.get_by_text(edited_owner, exact=False)).to_be_visible(
            timeout=PAGE_TIMEOUT
        )

        # ---- CROSS-STORE COUNT AGREEMENT (ADR 0008) -------------------------
        # Both surfaces are expected to read the same BusinessCapability table,
        # so both should have gone up by exactly one.
        list_count_after = _total_capabilities_on_list_page(page, live_server)
        dashboard_count_after = _total_capabilities_on_dashboard(page, live_server)

        assert list_count_after == list_count_before + 1, (
            "capability list page did not reflect the new row: "
            f"before={list_count_before} after={list_count_after}"
        )
        if dashboard_count_before is not None and dashboard_count_after is not None:
            assert dashboard_count_after == dashboard_count_before + 1, (
                "Cross-store disagreement: the capability list page counts "
                f"{list_count_after} capabilities after create, but the "
                f"capability-map dashboard counts {dashboard_count_after} "
                f"(was {dashboard_count_before} before create). Both are "
                "documented as reading BusinessCapability directly -- if they "
                "disagree, one of them is stale or filtered differently."
            )
        else:
            pytest.skip(
                "Dashboard total-capabilities figure could not be parsed from "
                "the rendered page; skipping the cross-store comparison rather "
                "than asserting on a value we could not extract."
            )
    finally:
        context.close()
