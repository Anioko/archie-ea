"""Founder-reported bug: the dashboard overview's per-layer "Open in
composer" button (Technology tab: "32 elements") landed on a blank,
unscoped composer canvas instead of that layer's real elements.

Fixed across:
- app/templates/dashboards/overview.html:619 -- static href replaced with an
  Alpine-bound `:href="'/archimate/composer?viewpoint=layered&layer=' +
  activeRole"`.
- app/modules/architecture/routes/archimate_routes.py -- `composer_page`
  passes through `layer` as `initial_layer`; `api_viewpoint_data` accepts an
  allowlisted `layer` query param (400 on an unknown value).
- app/services/archimate_viewpoint_service.py -- `get_viewpoint_data` narrows
  the element query by type, via the shared LAYER_TYPES map, before the
  500-row cap.
- app/static/js/archimate/composer_search.js / composer.js -- `layer`
  threaded through `selectViewpoint`'s existing URL construction.

See docs/buckets/dashboard-composer-layer-links/.

This drives the real browser: click a layer tab's "Open in composer" link,
land on the composer already scoped to that layer, and see only that
layer's elements -- not a blank canvas, not the whole enterprise model.
"""
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


@pytest.mark.smoke
def test_technology_layer_tab_open_in_composer_shows_only_technology_elements(
    browser, live_server, seeded
):
    """Reproduces the founder's exact report: seed a Technology-layer element
    and an Application-layer element, click the Technology tab's "Open in
    composer" link, and confirm the composer lands scoped to `layer=
    technology` with only the technology element visible -- not blank, and
    not the unscoped whole-tenant canvas.
    """
    from app import create_app, db

    email = seeded["emails"]["enterprise_architect"]
    org_id = seeded["ids"]["org"]

    app = create_app("testing")
    seeded_ids = []
    with app.app_context():
        from app.models.application_portfolio import ApplicationComponent
        from app.models.archimate_core import ArchiMateElement

        suffix = uuid.uuid4().hex[:6]
        tech_el = ArchiMateElement(
            name=f"Cloud Platform {suffix}", type="Node", layer="technology",
            organization_id=org_id,
        )
        app_el = ArchiMateElement(
            name=f"Order Service {suffix}", type="ApplicationComponent",
            layer="application", organization_id=org_id,
        )
        db.session.add_all([tech_el, app_el])
        # dashboard_mode == 'data' requires >= 5 applications or a capability
        # mapping (dashboard_views.py:606-608) -- otherwise the layer tabs
        # never render and this test would be checking the guided-setup page.
        existing_apps = ApplicationComponent.query.filter_by(
            organization_id=org_id
        ).count()
        if existing_apps < 5:
            db.session.add_all([
                ApplicationComponent(name=f"Smoke App {suffix}-{i}", organization_id=org_id)
                for i in range(5 - existing_apps)
            ])
        db.session.commit()
        seeded_ids = [
            el.id
            for el in ArchiMateElement.query.filter(
                ArchiMateElement.name.like(f"%{suffix}")
            ).all()
        ]

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        _login(page, live_server, email)

        page.goto(live_server + "/dashboard/overview", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        # Switch to the Technology layer tab.
        tech_tab = page.locator('[data-testid="layer-tab-technology"]').first
        expect(tech_tab).to_be_visible(timeout=PAGE_TIMEOUT)
        tech_tab.click()

        composer_link = page.locator('a:has-text("Open in composer")').first
        expect(composer_link).to_be_visible(timeout=PAGE_TIMEOUT)
        href = composer_link.get_attribute("href")
        assert href and "layer=technology" in href, (
            f"Technology tab's 'Open in composer' link must carry "
            f"layer=technology, got {href!r}"
        )
        assert "viewpoint=layered" in href, href

        composer_link.click()
        page.wait_for_url(lambda url: "/archimate/composer" in url, timeout=PAGE_TIMEOUT)
        assert "layer=technology" in page.url, page.url

        page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)

        body_text = page.inner_text("body")
        assert "Start from a template" not in body_text, (
            "layer-scoped composer link rendered the blank-canvas template "
            "picker instead of the technology layer's elements"
        )
        assert suffix in body_text, (
            f"the seeded technology element (suffix {suffix}) is not visible "
            "on the layer-filtered composer canvas"
        )

        # D1 regression guard: a view-only layer-filtered load must not mark
        # the canvas dirty -- otherwise the 30s autosave timer would create a
        # phantom SavedDiagram row for a user who only looked.
        is_dirty = page.evaluate(
            "() => window.Alpine ? "
            "Alpine.$data(document.querySelector('[x-data=\"composerApp()\"]')).viewpointDirty "
            ": null"
        )
        assert is_dirty is False, (
            f"viewpointDirty must be false after a view-only layer-filtered "
            f"load, got {is_dirty!r} -- risk of a phantom autosave POST"
        )
    finally:
        context.close()
        with app.app_context():
            from app.models.application_portfolio import ApplicationComponent
            from app.models.archimate_core import ArchiMateElement

            if seeded_ids:
                ArchiMateElement.query.filter(ArchiMateElement.id.in_(seeded_ids)).delete(
                    synchronize_session=False
                )
            ApplicationComponent.query.filter(
                ApplicationComponent.name.like(f"Smoke App {suffix}-%")
            ).delete(synchronize_session=False)
            db.session.commit()
