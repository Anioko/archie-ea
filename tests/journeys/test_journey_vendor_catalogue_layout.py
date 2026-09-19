"""Journey: the Vendor Catalogue table must fit at 1440px, with no empty box beside it.

UX_IA_REVIEW.md finding 6 (Medium): the "Readiness" header was cut to "READINE", its value was hidden behind
the "Actions" column, and an empty white box floated to the right of the table.

Root cause, measured in a browser before the fix. The products side panel is meant to be "hidden by default to
give table full width" (app/static/js/vendors/list.js: showVendorProducts removes `lg:hidden` and adds
`lg:block` when a vendor is clicked), but the template's wrapper was `class="hidden lg:block ..."`, already
visible from 1024px up. So at 1440px an empty, bordered panel (innerHTML length 0) reserved 288px, the table
(980px wide) was squeezed into an 820px scroll container, and its sticky, opaque, 176px-wide Actions column sat
on top of the Contract and Score columns.

The real page is rendered for a logged-in architect, with a vendor seeded so the table has a row to measure.
"""
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import pytest

from .conftest import login, make_org, make_user

pytestmark = pytest.mark.journey

STATIC = Path(__file__).resolve().parents[2] / "app" / "static"

MEASURE = r"""() => {
  const wrap = document.querySelector('.workbench-table-scroll');
  const wrapper = document.getElementById('vendor-products-wrapper');
  const ths = [...document.querySelectorAll('table[role=grid] thead th')].map(th => {
    const r = th.getBoundingClientRect();
    return {text: (th.innerText || '').trim(), left: r.left, right: r.right};
  });
  return {
    scrollWidth: wrap.scrollWidth, clientWidth: wrap.clientWidth,
    wrapperDisplay: getComputedStyle(wrapper).display,
    ths: ths,
  };
}"""


@pytest.fixture
def page_and_document(app, client):
    from app import db
    from app.models.vendor.vendor_organization import VendorOrganization

    with app.app_context():
        org = make_org(db, "VendorLayout")
        user = make_user(db, org, "sa", "solution_architect", role_name="Architect")
        vendor = VendorOrganization(
            name="Layout Vendor " + uuid.uuid4().hex[:6], vendor_type="saas_provider", status="active",
            contract_status="contracted", enterprise_readiness_score=72,
        )
        if hasattr(vendor, "organization_id"):
            vendor.organization_id = org
        db.session.add(vendor)
        db.session.commit()
    login(client, user)
    return client.get("/applications/vendors").get_data(as_text=True)


@pytest.fixture(scope="module")
def browser():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        chromium = p.chromium.launch()
        yield chromium
        chromium.close()


def _open(browser, client, document, width=1440):
    pg = browser.new_page(viewport={"width": width, "height": 900})

    def handle(route):
        url = urlparse(route.request.url)
        if url.path.startswith("/static/"):
            f = STATIC / url.path[len("/static/"):]
            return route.fulfill(path=str(f)) if f.is_file() else route.fulfill(status=404, body="")
        if url.path == "/applications/vendors":
            return route.fulfill(status=200, content_type="text/html", body=document)
        if url.path.startswith(("/api/", "/applications/", "/vendors")):
            r = client.get(url.path, query_string=dict(parse_qsl(url.query)))
            return route.fulfill(status=r.status_code, content_type=r.content_type or "application/json", body=r.get_data())
        return route.fulfill(status=204, body="")

    pg.route("http://app.test/**", handle)
    pg.goto("http://app.test/applications/vendors")
    pg.wait_for_selector("table[role=grid] tbody td button.font-medium", timeout=15000)  # the vendor-name button
    pg.wait_for_timeout(500)
    return pg


def test_the_products_panel_is_hidden_until_a_vendor_is_clicked(browser, client, page_and_document):
    pg = _open(browser, client, page_and_document)
    try:
        assert pg.evaluate(MEASURE)["wrapperDisplay"] == "none", "an empty products panel is on screen"
    finally:
        pg.close()


def test_the_table_fits_at_1440_without_scrolling(browser, client, page_and_document):
    pg = _open(browser, client, page_and_document)
    try:
        m = pg.evaluate(MEASURE)
        assert m["scrollWidth"] <= m["clientWidth"] + 1, (
            "the table is %dpx wide in a %dpx container, so it scrolls and the sticky Actions column "
            "covers the columns beside it" % (m["scrollWidth"], m["clientWidth"])
        )
    finally:
        pg.close()


def test_no_column_sits_underneath_the_actions_column(browser, client, page_and_document):
    pg = _open(browser, client, page_and_document)
    try:
        ths = pg.evaluate(MEASURE)["ths"]
        actions = next(t for t in ths if t["text"].lower() == "actions")
        for t in ths:
            if t is actions:
                continue
            assert t["right"] <= actions["left"] + 1, "%r runs underneath the Actions column" % t["text"]
        readiness = next(t for t in ths if t["text"].lower() == "readiness")
        assert readiness["right"] - readiness["left"] >= 90, "the Readiness header has no room for its text"
    finally:
        pg.close()


def test_the_wrapper_is_still_shown_when_a_vendor_is_clicked(browser, client, page_and_document):
    """Hiding it by default must not stop it appearing: showVendorProducts adds lg:block."""
    pg = _open(browser, client, page_and_document)
    try:
        pg.evaluate("() => { try { window.showVendorProducts(1, 'Probe'); } catch (e) {} }")
        pg.wait_for_timeout(300)
        assert pg.evaluate(MEASURE)["wrapperDisplay"] == "block"
    finally:
        pg.close()
