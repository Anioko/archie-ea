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
import requests
from playwright.sync_api import expect

from tests.smoke.conftest import PASSWORD

PAGE_TIMEOUT = 30000
CAP_LIST_URL = "/enterprise/capability-map/capabilities"
CAP_DASHBOARD_URL = "/enterprise/capability-map/"
CAP_API = re.compile(r"/enterprise/capabilities(/\d+)?$")
UNIFIED_CAP_API = "/api/v1/capabilities/"


def _unified_capabilities_count(page, base):
    """Read `/api/v1/capabilities/`'s total, via the browser's own session cookie.

    This is the write-time listener's demonstration (Task 02): the projection
    into `unified_capabilities` must have run inside the same transaction as the
    UI's `BusinessCapability` create, so this canonical-store-backed count must
    increase by exactly the same amount as the BusinessCapability-backed
    surfaces above, on the very next request.
    """

    cookies = {c["name"]: c["value"] for c in page.context.cookies()}
    resp = requests.get(base + UNIFIED_CAP_API, cookies=cookies, timeout=30)
    if resp.status_code != 200:
        return None, resp.status_code, resp.text
    payload = resp.json()
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    # success_response() shape: {"data": {"capabilities": [...], "pagination":
    # {"total": N, ...}}} -- app/api/v1/capabilities.py, app/utils/api_response.py.
    pagination = data.get("pagination") if isinstance(data, dict) else None
    if isinstance(pagination, dict) and "total" in pagination:
        return int(pagination["total"]), resp.status_code, resp.text
    if isinstance(data, dict) and "total" in data:
        return int(data["total"]), resp.status_code, resp.text
    if isinstance(data, list):
        return len(data), resp.status_code, resp.text
    return None, resp.status_code, resp.text


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
        unified_count_before, unified_status_before, unified_body_before = (
            _unified_capabilities_count(page, live_server)
        )

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
            pytest.fail(
                "Dashboard total-capabilities figure could not be parsed from "
                "the rendered page (#unified-cap-count missing or non-numeric). "
                "A 200 with no discoverable count is itself evidence of a "
                "regression (the element was removed or the count service "
                "stopped rendering) and must be treated as a failure, not "
                "skipped -- a skip here would silently stop guarding the "
                "cross-store count agreement this test exists to catch.\n"
                f"dashboard_count_before={dashboard_count_before!r} "
                f"dashboard_count_after={dashboard_count_after!r}"
            )

        # ---- CANONICAL STORE (ADR 0008 / Task 02's write-time sync) --------
        # /api/v1/capabilities/ reads unified_capabilities, not BusinessCapability
        # directly. If the write-time listener (app/models/business_capabilities.py)
        # is reverted or broken, this count stays flat while the two counts above
        # still go up by one -- that divergence is exactly what this assertion
        # exists to catch.
        page.goto(list_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        unified_count_after, unified_status_after, unified_body_after = (
            _unified_capabilities_count(page, live_server)
        )
        assert unified_status_before == 200, (
            "GET /api/v1/capabilities/ (the canonical store this test exists to "
            f"guard) did not return 200 before create: status={unified_status_before}. "
            "This must fail, not skip -- a skip here would hide the exact "
            "canonical-store regression (500/403/etc.) this test exists to catch."
        )
        assert unified_status_after == 200, (
            "GET /api/v1/capabilities/ (the canonical store this test exists to "
            f"guard) did not return 200 after create: status={unified_status_after}. "
            "This must fail, not skip -- a skip here would hide the exact "
            "canonical-store regression (500/403/etc.) this test exists to catch."
        )
        if unified_count_before is None or unified_count_after is None:
            # Round 3 / R2-4: a 200 with no discoverable count is itself evidence
            # something changed (a response-shape regression -- e.g.
            # success_response() wrapping changed, or the endpoint nests its data
            # differently) and is the more likely real-world regression than an
            # outright non-200, so this must fail loudly rather than skip. A skip
            # here would silently stop guarding the canonical store the moment its
            # response shape drifts, which is exactly the class of defect this
            # test exists to catch.
            pytest.fail(
                "/api/v1/capabilities/ returned 200 but its response body did not "
                "match any expected shape (pagination.total / top-level total / a "
                "list), so no count could be extracted. This is a response-shape "
                "regression on the canonical store's own API and must be treated "
                "as a failure, not skipped.\n"
                f"before body: {unified_body_before!r}\n"
                f"after body: {unified_body_after!r}"
            )
        else:
            assert unified_count_after == unified_count_before + 1, (
                "unified_capabilities (the canonical store /api/v1/capabilities/ "
                f"reads) did not increase after a BusinessCapability create: "
                f"before={unified_count_before} after={unified_count_after}. "
                "The write-time projection listener on BusinessCapability "
                "(app/models/business_capabilities.py) may be missing, reverted, "
                "or silently skipping (e.g. the provenance index is absent)."
            )
    finally:
        context.close()
