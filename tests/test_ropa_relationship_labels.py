"""Mixed access-edge endpoints must not all be presented as applications."""

from playwright.sync_api import sync_playwright
from app.modules.codegen.services.genome_data_ropa_emitter import render_ropa_table


def test_browser_register_preserves_accessing_element_types():
    html = render_ropa_table({
        "spec_hash": "fixture",
        "processing_activities": [{
            "name": "Customer record", "data_categories": [],
            "systems": [
                {"name": "Manage Customers", "archimate_type": "business_process", "access_mode": "read"},
                {"name": "CRM", "archimate_type": "application_component", "access_mode": "readwrite"},
            ],
            "lawful_basis": None, "retention": None,
            "provenance": {"archimate_element_id": 1, "archimate_type": "data_object"},
        }],
    })
    assert "Accessing elements" in str(html), str(html)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(str(html))
            assert page.get_by_role("columnheader", name="Accessing elements", exact=True).count() == 1, page.content()
            assert page.get_by_role("columnheader", name="Systems / applications", exact=True).count() == 0
            row = page.locator('tr[data-element-id="1"]')
            assert "business process" in row.inner_text()
            assert "application component" in row.inner_text()
            assert "Manage Customers" in row.inner_text()
            assert "CRM" in row.inner_text()
        finally:
            browser.close()
