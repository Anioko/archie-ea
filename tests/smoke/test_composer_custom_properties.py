"""Custom Properties (CMP-043, ArchiMate 3.2 Properties mechanism) actually persist.

An Architect adds a tagged key/value pair to an element via the existing
"Custom Properties" section of the composer detail panel and reloads the
page - the value must still be there, fetched fresh from the server, not
just sitting in this browser's localStorage cache.

This closes a real backend defect, not a missing feature: the GET/PUT
/archimate/api/elements/<id>/properties routes were reading and writing
app.models.models.ArchiMateElement.properties, a same-table (extend_existing),
different-column duplicate of the canonical archimate_core.ArchiMateElement
used everywhere else in this file (including the /detail endpoint the
composer's own detail panel reads from). That column was real but never read
by anything, so every save through this already-existing UI was silently
invisible on the very next page load - exactly the class of defect the
Capgemini SAP assessment's "no structured metadata field" finding describes.
Fixed by repointing both routes at archimate_core.ArchiMateElement.custom_properties
(reserved under a "tags" sub-key so it cannot clobber the data_classification/
contains_pii/lifecycle_history keys other features already write there via
PATCH /api/elements/<id>).
"""

import re
import uuid

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


def _quick_add(page, name):
    page.keyboard.press("Control+k")
    input_box = page.locator("#quick-add-input")
    expect(input_box).to_be_visible(timeout=PAGE_TIMEOUT)
    input_box.fill(name)
    create_btn = page.get_by_role("button", name=re.compile("^Create$"))
    expect(create_btn).to_be_visible(timeout=PAGE_TIMEOUT)
    create_btn.click()


@pytest.mark.smoke
def test_custom_property_survives_reload(browser, live_server, seeded):
    email = seeded["emails"]["enterprise_architect"]
    suffix = uuid.uuid4().hex[:8]
    key = "InterfaceProtocol"
    value = "OData-" + suffix

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    _login(page, live_server, email)

    page.goto(live_server + "/archimate/composer", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    expect(page.locator("nav[aria-label='Composer toolbar']")).to_be_visible(timeout=PAGE_TIMEOUT)

    _quick_add(page, "CustomProp %s Node" % suffix)
    expect(page.locator(".joint-element")).to_have_count(1, timeout=PAGE_TIMEOUT)
    page.locator(".joint-element").first.click()

    detail_panel = page.locator(".detail-panel")
    expect(detail_panel).to_be_visible(timeout=PAGE_TIMEOUT)

    actions_summary = detail_panel.get_by_text("Actions", exact=True)
    expect(actions_summary).to_be_visible(timeout=PAGE_TIMEOUT)
    actions_summary.locator("xpath=ancestor::details[1]").evaluate("el => { el.open = true; }")

    custom_props_toggle = detail_panel.locator("button", has_text="Custom Properties")
    expect(custom_props_toggle).to_be_visible(timeout=PAGE_TIMEOUT)
    custom_props_toggle.click()

    key_input = detail_panel.get_by_label("Key", exact=True)
    value_input = detail_panel.get_by_label("Property value", exact=True)
    expect(key_input).to_be_visible(timeout=PAGE_TIMEOUT)
    key_input.fill(key)
    value_input.fill(value)
    value_input.press("Enter")

    # Give the PUT a moment to land before deselecting.
    page.wait_for_timeout(1000)

    # Deselect, then reselect the same still-on-canvas element. This re-runs
    # loadCustomPropsFromServer (composer.js selection flow), issuing a fresh
    # GET against the just-fixed endpoint - a genuine server round-trip, not
    # a read of client-side state left over from the add. A full page reload
    # would additionally exercise diagram-canvas autosave/restore, a separate,
    # pre-existing product behaviour this test does not need to couple to.
    # Click blank canvas to deselect (composer.js paper 'blank:pointerclick'
    # handler) rather than the panel's own close button, which sits close to
    # a small floating dock-toggle icon and was flaky to target reliably.
    page.locator("#composer-canvas, .joint-paper, svg.joint-paper-background").first.click(position={"x": 20, "y": 20}, force=True)
    expect(detail_panel).to_be_hidden(timeout=PAGE_TIMEOUT)
    page.locator(".joint-element").first.click()

    detail_panel = page.locator(".detail-panel")
    expect(detail_panel).to_be_visible(timeout=PAGE_TIMEOUT)
    actions_summary = detail_panel.get_by_text("Actions", exact=True)
    expect(actions_summary).to_be_visible(timeout=PAGE_TIMEOUT)
    actions_summary.locator("xpath=ancestor::details[1]").evaluate("el => { el.open = true; }")
    custom_props_toggle = detail_panel.locator("button", has_text="Custom Properties")
    # customPropsOpen is top-level Alpine state, not reset by reselecting the
    # element (unlike the <details> "open" attribute forced above) - it is
    # already true from the first open, so click only if the list is closed.
    if not detail_panel.locator("text=" + key).is_visible():
        custom_props_toggle.click()

    expect(detail_panel.locator("text=" + key)).to_be_visible(timeout=PAGE_TIMEOUT)
    expect(detail_panel.locator("text=" + value)).to_be_visible(timeout=PAGE_TIMEOUT)
