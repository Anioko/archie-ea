"""F500-062 — the four Governance & Compliance editors on the blueprint page.

Real partials (_governance_compliance.html + _blueprint_governance_editor.html),
the real components/modal.html macro, the shipped Platform core bundle,
ui/modal.js, Alpine and solutions/blueprint.js run in Chromium. Only the
network boundary (the /solutions/<id>/... JSON API) is doubled with page.route.
No database, no Flask app, no login: full-app coverage is coordinator-owned.
"""
import json
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://blueprint.test"
SID = 32
EXISTING_EXCEPTION = {
    "id": 7, "solution_id": SID, "principle_id": None, "principle_name": "Cloud First",
    "exception_description": "On-prem mainframe stays until 2028", "justification": "Contract",
    "risk_accepted": None, "approved": False, "approval_date": None, "expiry_date": None,
    "mitigation_plan": None, "status": "requested",
}

CASES = [
    # button label, entity type, heading, required-field label, list endpoint
    ("+ Exception", "governance_exception", "Add Governance Exception", "Exception description *", "governance-exceptions"),
    ("+ Compliance", "compliance_mapping", "Add Compliance Mapping", "Framework *", "compliance-mappings"),
    ("+ Change", "change_request", "Add Change Request", "Title *", "change-requests"),
    ("+ Review", "feasibility_review", "Add Feasibility Review", "Review type *", "feasibility-reviews"),
]


def page_html(sad_data):
    env = Environment(loader=FileSystemLoader(ROOT / "app/templates"), autoescape=True)
    body = env.from_string(
        "{% include 'solutions/partials/_governance_compliance.html' %}"
        "{% include 'solutions/partials/_blueprint_governance_editor.html' %}"
    ).render()
    cfg = json.dumps({"solutionId": SID, "csrfToken": "t", "sectionDefinitions": {}, "sadData": sad_data})
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"csrf-token\" content=\"t\">"
        "<link rel=stylesheet href=/static/css/tailwind-output.css><style>[x-cloak]{display:none!important}</style>"
        "<script src=/static/js/bundles/core-admin.js></script><script src=/static/js/ui/modal.js></script>"
        "<script src=/static/js/solutions/blueprint.js></script>"
        "<script>window.__BLUEPRINT_CONFIG__=" + cfg + ";</script>"
        "<script defer src=/static/vendor/alpine.min.js></script></head><body>"
        '<div x-data="blueprintPage()" x-init="init()">' + body + "</div></body></html>"
    )


class Api:
    """Doubled /solutions/<id>/<resource> API. Records writes; serves lists."""

    def __init__(self, page, lists=None, fail_with=None):
        self.writes = []
        self.lists = lists or {}
        self.fail_with = fail_with
        page.route(BASE + "/solutions/*/**", self.handle)

    def handle(self, route):
        req = route.request
        resource = req.url.split("/solutions/%d/" % SID, 1)[1].split("/")[0]
        if req.method == "GET":
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"success": True, "items": self.lists.get(resource, [])}))
            return
        self.writes.append((req.method, req.url, req.post_data_json))
        if self.fail_with:
            route.fulfill(status=self.fail_with[0], content_type="application/json",
                          body=json.dumps({"success": False, "error": self.fail_with[1]}))
            return
        item = dict(req.post_data_json or {}, id=99, solution_id=SID)
        self.lists.setdefault(resource, []).append(item)
        route.fulfill(status=201 if req.method == "POST" else 200, content_type="application/json",
                      body=json.dumps({"success": True, "item": item}))


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    p = browser.new_page(viewport={"width": 1280, "height": 900})
    p.route(BASE + "/static/**", lambda r: r.fulfill(path=str(ROOT / "app" / r.request.url[len(BASE) + 1:].split("?")[0])))
    yield p
    p.close()


def open_page(page, sad_data=None):
    page.route(BASE + "/", lambda r: r.fulfill(body=page_html(sad_data or {}), content_type="text/html"))
    page.goto(BASE + "/")
    page.wait_for_function("window.Alpine && window.Platform && window.Platform.modal")
    return page.get_by_role("dialog")


@pytest.mark.parametrize("label,etype,heading,required,_res", CASES)
def test_open_cancel_and_escape_for_each_control(page, label, etype, heading, required, _res):
    dialog = open_page(page)
    Api(page)
    expect(dialog).to_be_hidden()
    page.get_by_role("button", name=label, exact=True).click()
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("heading", name=heading, exact=True)).to_be_visible()
    expect(dialog.get_by_text(required, exact=True)).to_be_visible()
    expect(page.locator("#bp-governance-editor :focus")).to_have_count(1)
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(dialog).to_be_hidden()
    # Reopen on the next click, dismiss with the keyboard, and it stays reusable.
    page.get_by_role("button", name=label, exact=True).click()
    expect(dialog).to_be_visible()
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    page.get_by_role("button", name=label, exact=True).click()
    expect(dialog.get_by_role("heading", name=heading, exact=True)).to_be_visible()


def test_blank_required_field_is_rejected_without_a_request(page):
    dialog = open_page(page)
    api = Api(page)
    page.get_by_role("button", name="+ Compliance", exact=True).click()
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(dialog.get_by_test_id("bp-governance-editor-error")).to_have_text("Framework is required.")
    expect(dialog).to_be_visible()
    assert api.writes == []


def test_create_exception_posts_to_endpoint_and_refreshes_list(page):
    dialog = open_page(page)
    api = Api(page)
    page.get_by_role("button", name="+ Exception", exact=True).click()
    dialog.get_by_label("Exception description *").fill("Keep the legacy ESB for phase 1")
    dialog.get_by_label("Status").select_option("approved")
    with page.expect_response(lambda r: r.request.method == "GET" and "/governance-exceptions" in r.url):
        dialog.get_by_role("button", name="Save", exact=True).click()
    expect(dialog).to_be_hidden()
    assert len(api.writes) == 1
    method, url, body = api.writes[0]
    assert (method, url) == ("POST", BASE + "/solutions/32/governance-exceptions")
    assert body["exception_description"] == "Keep the legacy ESB for phase 1"
    assert body["status"] == "approved"
    assert body.get("expiry_date") is None  # never sent as ''
    # The list re-rendered from the GET, not from the page reloading.
    expect(page.get_by_text("Keep the legacy ESB for phase 1")).to_be_visible()
    expect(page.get_by_role("heading", name="Governance Exceptions", exact=True)).to_be_visible()


def test_edit_shows_existing_values_and_puts_to_item_endpoint(page):
    dialog = open_page(page, {"governance_exceptions": [EXISTING_EXCEPTION]})
    api = Api(page, lists={"governance-exceptions": [EXISTING_EXCEPTION]})
    page.get_by_role("button", name="Edit", exact=True).click()
    expect(dialog.get_by_role("heading", name="Edit Governance Exception", exact=True)).to_be_visible()
    expect(dialog.get_by_label("Exception description *")).to_have_value("On-prem mainframe stays until 2028")
    expect(dialog.get_by_text("Cloud First", exact=True)).to_be_visible()
    dialog.get_by_label("Justification").fill("Contract renewed")
    dialog.get_by_role("button", name="Save changes", exact=True).click()
    expect(dialog).to_be_hidden()
    method, url, body = api.writes[0]
    assert (method, url) == ("PUT", BASE + "/solutions/32/governance-exceptions/7")
    assert body["justification"] == "Contract renewed"
    assert body["exception_description"] == "On-prem mainframe stays until 2028"


def test_failed_save_keeps_editor_open_with_values_and_shows_server_error(page):
    dialog = open_page(page)
    api = Api(page, fail_with=(400, "Missing required field: title"))
    page.get_by_role("button", name="+ Change", exact=True).click()
    dialog.get_by_label("Title *").fill("Swap message broker")
    dialog.get_by_label("Change type *").select_option("technology")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(dialog.get_by_test_id("bp-governance-editor-error")).to_have_text("Missing required field: title")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("Title *")).to_have_value("Swap message broker")
    expect(dialog.get_by_label("Change type *")).to_have_value("technology")
    expect(dialog.get_by_role("button", name="Save", exact=True)).to_be_enabled()
    assert [w[0] for w in api.writes] == ["POST"]
    # "Change Requests" never appeared: nothing was added on failure.
    expect(page.get_by_role("heading", name="Change Requests", exact=True)).to_have_count(0)


def test_feasibility_review_maps_select_to_boolean(page):
    dialog = open_page(page)
    api = Api(page)
    page.get_by_role("button", name="+ Review", exact=True).click()
    dialog.get_by_label("Review type *").select_option("financial")
    dialog.get_by_label("Feasible").select_option("false")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(dialog).to_be_hidden()
    method, url, body = api.writes[0]
    assert (method, url) == ("POST", BASE + "/solutions/32/feasibility-reviews")
    assert body["review_type"] == "financial"
    assert body["feasible"] is False
    assert body["review_phase"] is None


def test_successful_create_with_failed_refresh_does_not_offer_duplicate_save(page):
    dialog = open_page(page)
    api = Api(page)
    page.route(BASE + "/solutions/32/governance-exceptions", lambda route:
               route.fulfill(status=503, content_type="application/json", body='{"error":"Refresh unavailable"}')
               if route.request.method == "GET" else route.fallback())
    page.get_by_role("button", name="+ Exception", exact=True).click()
    dialog.get_by_label("Exception description *").fill("Saved once")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_text("Saved, but the list could not be refreshed — reload the page to see the latest data", exact=True)).to_be_visible()
    expect(dialog).to_be_hidden()
    assert len(api.writes) == 1


def test_principle_search_filters_type_and_submits_selected_identity(page):
    dialog = open_page(page)
    api = Api(page)
    searches = []

    def search(route):
        searches.append(route.request.url)
        route.fulfill(status=200, content_type="application/json",
                      body='{"data":[{"id":41,"name":"Cloud first","type":"Principle"}]}')

    page.route(BASE + "/archimate/api/elements/search?*", search)
    page.get_by_role("button", name="+ Exception", exact=True).click()
    dialog.get_by_label("Principle (ArchiMate element)").fill("Cloud")
    dialog.get_by_role("button", name="Cloud first Principle", exact=True).click()
    assert searches and "type=Principle" in searches[-1]
    dialog.get_by_label("Exception description *").fill("Temporary exception")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(dialog).to_be_hidden()
    assert api.writes[0][2]["principle_id"] == 41
    assert api.writes[0][2]["principle_name"] == "Cloud first"


def test_late_save_response_does_not_close_a_new_editor(page):
    dialog = open_page(page)
    Api(page)
    pending = []
    page.route(BASE + "/solutions/32/governance-exceptions", lambda route:
               pending.append(route) if route.request.method == "POST" else route.fallback())
    page.get_by_role("button", name="+ Exception", exact=True).click()
    dialog.get_by_label("Exception description *").fill("First editor")
    with page.expect_request(lambda req: req.method == "POST"):
        dialog.get_by_role("button", name="Save", exact=True).click()
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    page.get_by_role("button", name="+ Compliance", exact=True).click()
    dialog.get_by_label("Framework *").fill("Second editor unsaved input")
    assert len(pending) == 1
    with page.expect_response(lambda response: response.request.method == "GET" and "governance-exceptions" in response.url):
        pending[0].fulfill(status=201, content_type="application/json",
                           body='{"success":true,"item":{"id":99,"exception_description":"First editor"}}')
    expect(dialog.get_by_role("heading", name="Add Compliance Mapping", exact=True)).to_be_visible()
    expect(dialog.get_by_label("Framework *")).to_have_value("Second editor unsaved input")


def test_malformed_element_search_is_visible_not_an_empty_success(page):
    dialog = open_page(page)
    Api(page)
    page.route(BASE + "/archimate/api/elements/search?*", lambda route:
               route.fulfill(status=200, content_type="application/json", body='{"success":true}'))
    page.get_by_role("button", name="+ Compliance", exact=True).click()
    dialog.get_by_label("Mapped element (ArchiMate element)").fill("Missing")
    expect(dialog.get_by_text("Element search returned an invalid response.", exact=True)).to_be_visible()
