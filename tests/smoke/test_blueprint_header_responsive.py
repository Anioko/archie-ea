"""A long live-style title must not place header actions beneath governance."""
import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT
from .test_solution_blueprint_controls import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


@pytest.mark.parametrize("width", [1280, 1100])
def test_long_blueprint_header_opens_real_code_workbench(browser, live_server, seeded, width):
    from app import create_app, db

    app = create_app("testing")
    params = {"id": seeded["ids"]["solution"], "org": seeded["ids"]["org"]}
    title = "Legacy CRM Retirement (Lotus Notes → Sales Cloud)"
    with app.app_context():
        prior_name = db.session.execute(db.text(
            "SELECT name FROM solutions WHERE id=:id AND organization_id=:org"
        ), params).scalar_one()
        db.session.execute(db.text(
            "UPDATE solutions SET name=:name WHERE id=:id AND organization_id=:org"
        ), {**params, "name": title})
        db.session.commit()
    context = browser.new_context(viewport={"width": width, "height": 631})
    try:
        page = context.new_page()
        _login(page, live_server, seeded["emails"]["platform_admin"])
        response = page.goto(live_server + f'/solutions/{params["id"]}', timeout=PAGE_TIMEOUT)
        assert response.status == 200
        expect(page.get_by_role("heading", level=1)).to_have_text(title)
        page.evaluate("document.fonts.ready")
        button = page.get_by_role("button", name="More actions", exact=True)
        button.scroll_into_view_if_needed()
        assert button.evaluate("el => {const r=el.getBoundingClientRect(); return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}")
        button.click()
        expect(page.get_by_role("menuitem", name="Code Workbench", exact=True)).to_be_visible()
        with page.expect_navigation(timeout=PAGE_TIMEOUT) as navigation:
            page.get_by_role("menuitem", name="Code Workbench", exact=True).click()
        assert navigation.value.status == 200
        expect(page.get_by_role("heading", name="Code Workbench", exact=True)).to_be_visible()
    finally:
        context.close()
        with app.app_context():
            db.session.execute(db.text(
                "UPDATE solutions SET name=:name WHERE id=:id AND organization_id=:org"
            ), {**params, "name": prior_name})
            db.session.commit()
