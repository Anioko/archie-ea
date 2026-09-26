"""A procurement lead keeps one vendor record with its group and legal entities.

In a brand-new organisation the procurement lead records a holding company
from the "Create Vendor" form (/vendors/create), then a subsidiary: its
parent group is picked from the vendor catalogue with the live-search
picker, and its legal entities are entered with their registry identifiers.
After a reload the subsidiary's page (/vendors/<id>) shows the parent group
and both legal entities, and the holding company's page lists the
subsidiary as a group member. Editing the record adds a third legal entity,
which also survives a reload. Recording the subsidiary again under a
different letter case is refused, with a link to the existing record, and
the catalogue still holds exactly one.

The vendor catalogue is shared reference data by design (a vendor's group
and legal entities are facts about the vendor in the world, like the rest of
the record), so a second new organisation sees the same record - including
its corporate structure - and is refused a duplicate in the same way. What
each organisation buys from the vendor stays in its own contracts.
"""

import re

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT
from .fresh_org import api, create_fresh_org, sign_in

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def _new_page(browser):
    """A fresh browser session with the first-login welcome tour already seen."""
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 1000})
    context.add_init_script("localStorage.setItem('archie_onboarding_ts', Date.now().toString());")
    return context, context.new_page()


def _fill_entities(page, entities, start=0):
    for offset, (name, identifier) in enumerate(entities):
        page.get_by_role("button", name="Add legal entity").click()
        n = start + offset + 1
        page.get_by_label("Legal entity name %d" % n, exact=True).fill(name)
        page.get_by_label("Registry identifier %d" % n, exact=True).fill(identifier)


def _create_vendor(page, base, name, parent=None, entities=()):
    page.goto(base + "/vendors/create", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.fill("#name", name)
    page.select_option("#vendor_type", "saas_platform")
    if parent:
        picker = page.get_by_label("Parent group")
        picker.fill(parent)
        option = page.locator("#parent_vendor_results").get_by_role("button", name=parent, exact=True)
        expect(option).to_be_visible(timeout=PAGE_TIMEOUT)
        option.click()
        expect(page.get_by_test_id("parent-vendor-selected")).to_contain_text(parent)
    _fill_entities(page, entities)
    with page.expect_response(
        lambda r: r.url.endswith("/applications/vendors/create") and r.request.method == "POST",
        timeout=PAGE_TIMEOUT,
    ) as created:
        page.get_by_role("button", name="Create Vendor").click()
    return created.value


def _vendor_id(page):
    page.wait_for_url(re.compile(r"/applications/vendors/\d+$"), timeout=PAGE_TIMEOUT)
    return int(re.search(r"/vendors/(\d+)$", page.url).group(1))


def _entities_on_page(page):
    items = page.get_by_test_id("vendor-legal-entities").locator("li")
    return [tuple(s.strip() for s in item.locator("span").all_inner_texts()) for item in items.all()]


def test_procurement_keeps_one_vendor_record_with_its_group_and_legal_entities(browser, live_server):
    first = create_fresh_org("procurement")
    second = create_fresh_org("procurement")
    suffix = first["suffix"]
    holding = "Launch Holdings %s" % suffix
    subsidiary = "Launch Cloud %s" % suffix
    entities = [("Launch Cloud Ltd", "GB-%s" % suffix), ("Launch Cloud Inc", "DUNS-%s" % suffix)]

    context, page = _new_page(browser)
    sign_in(page, live_server, first["emails"]["procurement"])
    response = _create_vendor(page, live_server, holding, entities=[("Launch Holdings plc", "LEI-%s" % suffix)])
    assert response.status < 400, "creating the holding company answered %s" % response.status
    holding_id = _vendor_id(page)

    response = _create_vendor(page, live_server, subsidiary, parent=holding, entities=entities)
    assert response.status < 400, "creating the subsidiary answered %s" % response.status
    subsidiary_id = _vendor_id(page)

    # The canonical vendor address, after a reload.
    page.goto(live_server + "/vendors/%d" % subsidiary_id, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    page.reload(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    expect(page.get_by_test_id("vendor-parent-group")).to_contain_text(holding)
    assert _entities_on_page(page) == list(entities)
    page.get_by_test_id("vendor-parent-group").get_by_role("link", name=holding).click()
    page.wait_for_url(re.compile(r"/applications/vendors/%d$" % holding_id), timeout=PAGE_TIMEOUT)
    expect(page.get_by_test_id("vendor-group-members")).to_contain_text(subsidiary)
    expect(page.get_by_test_id("vendor-parent-group")).to_contain_text("—")

    # Maintain the record: add a third legal entity through the edit form.
    page.goto(live_server + "/vendors/%d/edit" % subsidiary_id, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    expect(page.get_by_test_id("parent-vendor-selected")).to_contain_text(holding)
    expect(page.get_by_label("Legal entity name 2", exact=True)).to_have_value("Launch Cloud Inc")
    _fill_entities(page, [("Launch Cloud GmbH", "HRB-%s" % suffix)], start=2)
    with page.expect_response(
        lambda r: r.url.endswith("/vendors/%d/edit" % subsidiary_id) and r.request.method == "POST",
        timeout=PAGE_TIMEOUT,
    ) as edited:
        page.get_by_role("button", name="Update Vendor").click()
    assert edited.value.status < 400, "saving the vendor answered %s" % edited.value.status
    page.goto(live_server + "/vendors/%d" % subsidiary_id, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    assert _entities_on_page(page) == list(entities) + [("Launch Cloud GmbH", "HRB-%s" % suffix)]
    expect(page.get_by_test_id("vendor-parent-group")).to_contain_text(holding)

    # The same vendor again, in another letter case, is refused.
    response = _create_vendor(page, live_server, subsidiary.upper())
    assert response.status == 409, "a duplicate vendor answered %s" % response.status
    duplicate = page.get_by_test_id("vendor-duplicate")
    expect(duplicate).to_contain_text("already in the vendor catalogue")
    expect(duplicate.get_by_role("link", name="Open %s" % subsidiary)).to_have_attribute(
        "href", "/applications/vendors/%d" % subsidiary_id)
    status, body = api(page, "GET", "/api/vendors/list?q=%s&per_page=50" % suffix)
    assert status == 200
    assert sorted(v["name"].lower() for v in body["vendors"]) == sorted([holding.lower(), subsidiary.lower()])
    context.close()

    # A second organisation shares the catalogue record, structure included,
    # and cannot add the vendor a second time either.
    context, page = _new_page(browser)
    sign_in(page, live_server, second["emails"]["procurement"])
    page.goto(live_server + "/vendors/%d" % subsidiary_id, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    expect(page.get_by_test_id("vendor-parent-group")).to_contain_text(holding)
    response = _create_vendor(page, live_server, subsidiary.lower())
    assert response.status == 409
    context.close()
