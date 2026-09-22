"""Full vendor create -> edit -> persist -> reload journey through the real UI.

test_vendor_dialog_controls.py already covers the create-dialog's cancel/escape
paths (no write on dismissal). This file covers the write path itself: a
platform_admin creates a real vendor through the "New Vendor" modal, confirms
it survives a hard page reload, then edits it through the "Edit Vendor" modal
and confirms the edit also survives a reload -- the "Done means DEMONSTRATED"
bar from CLAUDE.md, not just an unchecked POST.
"""
import uuid

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


def test_vendor_create_edit_persists_across_reload(browser, live_server, seeded):
    page = browser.new_page()
    vendor_name = f"QA Journey Vendor {uuid.uuid4().hex[:8]}"
    updated_name = f"{vendor_name} (Updated)"
    try:
        _login(page, live_server, seeded['emails']['platform_admin'])
        response = page.goto(live_server + '/applications/vendors', timeout=PAGE_TIMEOUT)
        assert response.status == 200

        # ---- Create ----
        page.get_by_role('button', name='Add Vendor', exact=True).click()
        dialog = page.locator('#create-vendor')
        expect(dialog).to_be_visible()
        dialog.get_by_label('Vendor Name *', exact=True).fill(vendor_name)
        dialog.locator('#cv-type').select_option('software_vendor')
        dialog.locator('#cv-website').fill('https://qa-journey-vendor.example.com')
        dialog.get_by_role('button', name='Create Vendor', exact=True).click()
        expect(dialog).not_to_be_visible(timeout=PAGE_TIMEOUT)

        # The modal's own success path reloads the page after a toast; wait for
        # that reload rather than racing it, then do our own hard reload so the
        # assertion is about persisted server state, not client-side Alpine state.
        page.wait_for_timeout(1200)
        page.reload(timeout=PAGE_TIMEOUT)
        row_name_button = page.get_by_role('button', name=vendor_name, exact=True)
        expect(row_name_button).to_be_visible(timeout=PAGE_TIMEOUT)

        # ---- Edit ----
        row_name_button.click()
        edit_dialog = page.locator('#edit-vendor-modal')
        expect(edit_dialog).to_be_visible()
        name_input = edit_dialog.get_by_label('Vendor Name', exact=True)
        expect(name_input).to_have_value(vendor_name)
        name_input.fill('')
        name_input.fill(updated_name)
        edit_dialog.get_by_label('Country', exact=True).fill('United Kingdom')
        edit_dialog.get_by_role('button', name='Save Changes', exact=True).click()
        expect(edit_dialog).not_to_be_visible(timeout=PAGE_TIMEOUT)

        # Confirm the edit persisted server-side, not merely in the in-page
        # Alpine table state that saveEdit() already refreshes itself.
        page.reload(timeout=PAGE_TIMEOUT)
        expect(page.get_by_role('button', name=updated_name, exact=True)).to_be_visible(timeout=PAGE_TIMEOUT)
        expect(page.get_by_role('button', name=vendor_name, exact=True)).to_have_count(0)
    finally:
        page.close()


def test_vendor_detail_deep_links_to_application_mapping(browser, live_server, seeded):
    """The vendor detail page must offer a way into the package's one real
    page, the application-to-vendor mapping across all vendors.

    The vendor list row's own "View" link points at the separate legacy
    application_mgmt vendor page, not the live unified_applications one this
    deep link lives on -- a pre-existing surface this task does not touch --
    so the created vendor's id is read from that link's href and the live
    detail page is opened directly.
    """
    page = browser.new_page()
    vendor_name = f"QA Mapping Link Vendor {uuid.uuid4().hex[:8]}"
    vendor_id = None
    try:
        _login(page, live_server, seeded['emails']['enterprise_architect'])
        response = page.goto(live_server + '/applications/vendors', timeout=PAGE_TIMEOUT)
        assert response.status == 200

        page.get_by_role('button', name='Add Vendor', exact=True).click()
        dialog = page.locator('#create-vendor')
        expect(dialog).to_be_visible()
        dialog.get_by_label('Vendor Name *', exact=True).fill(vendor_name)
        dialog.locator('#cv-type').select_option('software_vendor')
        dialog.get_by_role('button', name='Create Vendor', exact=True).click()
        expect(dialog).not_to_be_visible(timeout=PAGE_TIMEOUT)
        page.wait_for_timeout(1200)
        page.reload(timeout=PAGE_TIMEOUT)
        row_name_button = page.get_by_role('button', name=vendor_name, exact=True)
        expect(row_name_button).to_be_visible(timeout=PAGE_TIMEOUT)

        row = page.locator('tr', has=row_name_button)
        view_link = row.get_by_role('link', name='View vendor details')
        href = view_link.get_attribute('href')
        vendor_id = int(href.rstrip('/').rsplit('/', 1)[-1])

        response = page.goto(live_server + f'/applications/vendors/{vendor_id}', timeout=PAGE_TIMEOUT)
        assert response.status == 200

        link = page.get_by_test_id('vendor-application-mapping-link')
        expect(link).to_be_visible()
        expect(link).to_have_text('Application mapping across all vendors')

        with page.expect_navigation(timeout=PAGE_TIMEOUT) as navigation:
            link.click()
        assert navigation.value.status == 200
        expect(page.get_by_role('heading', level=1, name='All Vendors', exact=True)).to_be_visible()
    finally:
        page.close()
        if vendor_id is not None:
            from app import create_app, db

            cleanup_app = create_app('testing')
            with cleanup_app.app_context():
                from app.models.vendor_organization import VendorOrganization

                VendorOrganization.query.filter_by(id=vendor_id).delete(synchronize_session=False)
                db.session.commit()
