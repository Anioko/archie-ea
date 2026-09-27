"""composer-diagram-link-mismatches bucket (D1, D2, D3, D4).

Founder-reported, twice tonight, that "open this in the composer" links land
on the wrong canvas. Four link-building sites passed a numeric SavedDiagram.id
as ``?viewpoint=`` (a named-key-only param, so it silently fell through to the
'basic' STANDARD_VIEWPOINTS default) instead of ``?viewpoint_id=`` (the param
`loadSavedViewpoint` actually reads). This drives the real browser for D1 (the
dashboard "Architecture Overview" card) and D3 (AI-chat generated stakeholder
viewpoints), which were not covered by any existing smoke test.

D2 (composer.js linkSubDiagram) and D4 (archimate_composer_service.py,
archimate_routes.py, chat_workflows.py:817) are covered at unit level in
tests/test_composer_diagram_link_mismatches.py -- they either require canvas
sub-diagram state not reachable from a fresh smoke seed (D2) or are pure
string-building already exercised by service-level tests (D4).
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
def test_dashboard_architecture_overview_card_opens_layered_viewpoint(browser, live_server, seeded):
    """D1: the "Architecture Overview -- Layered Viewpoint" card's "Open
    Composer" button must carry ?viewpoint=layered, not the bare composer URL
    that falls through to a blank template-picker canvas."""
    email = seeded["emails"]["enterprise_architect"]

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        _login(page, live_server, email)

        page.goto(live_server + "/dashboard/overview", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        # The heading and the "Open Composer" anchor are both descendants of
        # one flex row (see app/templates/dashboards/overview.html) -- scope
        # to that row via :has() rather than assuming a fixed ancestor depth.
        card_link = page.locator(
            'div.flex:has(h2:has-text("Architecture Overview")) a[href*="/archimate/composer"]'
        ).first
        expect(card_link).to_be_visible(timeout=PAGE_TIMEOUT)
        href = card_link.get_attribute("href")
        assert href and "viewpoint=layered" in href, (
            f"Architecture Overview card link must carry ?viewpoint=layered, got {href!r}"
        )

        card_link.click()
        page.wait_for_url(lambda url: "/archimate/composer" in url, timeout=PAGE_TIMEOUT)
        assert "viewpoint=layered" in page.url, page.url

        page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
        body_text = page.inner_text("body")
        assert "Start from a template" not in body_text, (
            "composer rendered the blank-canvas template picker from the "
            "dashboard card -- D1 regressed"
        )
    finally:
        context.close()


@pytest.mark.smoke
def test_traceability_chain_add_button_preserves_layer(browser, live_server, seeded):
    """FIX 1 (2026-09-19 refuter follow-up): the traceability chain's
    layer-scoped "+ Add" buttons pass only ?layer=X, no ?viewpoint=. Before
    the composer.js init-logic fix, `initialLayer` was only ever applied
    inside the `if (initialVp)` branch, so a layer-only link silently opened
    the generic blank canvas -- the layer was dropped. This clicks the real
    "+ Add" button in the Business layer, follows it into the composer, and
    asserts the layer survives into the rendered canvas state (not just the
    URL), and that the generic template-picker did not render instead."""
    email = seeded["emails"]["enterprise_architect"]

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        _login(page, live_server, email)

        page.goto(live_server + "/archimate/traceability", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        add_link = page.locator('a[href*="/archimate/composer?layer=Business"]').first
        expect(add_link).to_be_visible(timeout=PAGE_TIMEOUT)
        href = add_link.get_attribute("href")
        assert href and "layer=Business" in href and "viewpoint=" not in href, (
            f"expected a bare layer-only link (no viewpoint=), got {href!r}"
        )

        add_link.click()
        page.wait_for_url(lambda url: "/archimate/composer" in url, timeout=PAGE_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)

        body_text = page.inner_text("body")
        assert "Start from a template" not in body_text, (
            "layer-only '+ Add' link opened the blank template-picker canvas "
            "-- the layer was silently dropped (FIX 1 regressed)"
        )

        # The composer's page-load config must have defaulted the viewpoint
        # to 'layered' and preserved the requested layer, not left it unset.
        config = page.evaluate("() => window.__COMPOSER_CONFIG__ || {}")
        assert config.get("initialLayer") == "Business", config
    finally:
        context.close()


@pytest.mark.smoke
def test_architect_viewpoints_generates_real_openable_diagrams(browser, live_server, seeded):
    """D3: POST /ai-chat/architect/viewpoints must create real SavedDiagram
    rows (not dead ViewpointView rows) and return ?viewpoint_id= links that
    actually open on the canvas with real elements -- not a placeholder
    ?viewpoint=0 link to nothing."""
    from app import create_app, db

    email = seeded["emails"]["enterprise_architect"]
    org_id = seeded["ids"]["org"]
    solution_id = seeded["ids"]["solution"]

    app = create_app("testing")
    seeded_element_ids = []
    with app.app_context():
        from app.models.archimate_core import ArchiMateElement
        from app.models.solution_archimate_element import SolutionArchiMateElement

        suffix = uuid.uuid4().hex[:6]
        el = ArchiMateElement(
            name=f"Order API {suffix}", type="ApplicationComponent",
            layer="application", organization_id=org_id,
        )
        db.session.add(el)
        db.session.commit()
        seeded_element_ids.append(el.id)
        db.session.add(SolutionArchiMateElement(solution_id=solution_id, element_id=el.id))
        db.session.commit()

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        _login(page, live_server, email)

        # CSRF token needed for the POST -- grab it from any authenticated page.
        page.goto(live_server + "/dashboard/overview", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        csrf = page.evaluate(
            "() => document.querySelector('meta[name=csrf-token]')?.content || "
            "document.querySelector('input[name=csrf_token]')?.value"
        )

        resp = page.request.post(
            live_server + "/ai-chat/architect/viewpoints",
            data={"solution_id": solution_id},
            headers={"X-CSRFToken": csrf} if csrf else {},
        )
        assert resp.ok, resp.text()
        payload = resp.json()
        assert payload["success"], payload

        viewpoints = payload["viewpoints"]
        assert len(viewpoints) == 4, viewpoints

        opened_real_content = False
        for vp in viewpoints:
            assert "viewpoint_view_id" not in vp, (
                "response still carries the retired viewpoint_view_id field"
            )
            url = vp["composer_url"]
            if url is None:
                # A viewpoint matching zero elements must be null, never a
                # fabricated placeholder link.
                assert vp["saved_diagram_id"] is None, vp
                assert vp["element_count"] == 0, vp
                continue

            assert "viewpoint_id=" in url, f"D3 regressed -- non-key link: {url!r}"
            assert "viewpoint=0" not in url and "viewpoint=" not in url.replace("viewpoint_id=", ""), url

            diagram_id = vp["saved_diagram_id"]
            assert diagram_id is not None

            api_resp = page.request.get(
                live_server + f"/archimate/api/saved-viewpoints/{diagram_id}"
            )
            assert api_resp.ok, (diagram_id, api_resp.text())
            diagram_payload = api_resp.json()
            elements = diagram_payload.get("elements") or diagram_payload.get("data", {}).get("elements")
            if elements:
                opened_real_content = True

        assert opened_real_content, (
            "none of the generated viewpoints resolved to a diagram with real "
            "elements via /archimate/api/saved-viewpoints/<id>"
        )

        # Browser walkthrough: follow one real composer_url and see the
        # tenant's element on the canvas, not a blank/template-picker state.
        real_url = next(vp["composer_url"] for vp in viewpoints if vp["composer_url"])
        page.goto(live_server + real_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
        body_text = page.inner_text("body")
        assert "Start from a template" not in body_text, (
            "AI-chat-generated viewpoint link opened the blank template "
            "picker instead of the real SavedDiagram -- D3 regressed"
        )
    finally:
        context.close()
        with app.app_context():
            from app.models.archimate_core import ArchiMateElement
            from app.models.archimate_core import SavedDiagramElement
            from app.models.solution_archimate_element import SolutionArchiMateElement

            # architect_viewpoints() created real SavedDiagram rows referencing
            # these elements (that's the point of D3) -- clear the layout join
            # rows first or the ArchiMateElement delete below hits a real FK.
            SavedDiagramElement.query.filter(
                SavedDiagramElement.element_id.in_(seeded_element_ids)
            ).delete(synchronize_session=False)
            SolutionArchiMateElement.query.filter(
                SolutionArchiMateElement.element_id.in_(seeded_element_ids)
            ).delete(synchronize_session=False)
            ArchiMateElement.query.filter(ArchiMateElement.id.in_(seeded_element_ids)).delete(
                synchronize_session=False
            )
            db.session.commit()


@pytest.mark.smoke
def test_tenant_isolation_on_architect_generated_diagram(browser, live_server, seeded):
    """A second org must not be able to load a SavedDiagram created by
    architect_viewpoints() under the first org -- SavedDiagram carries
    TenantMixin, unlike the retired ViewpointView it replaces."""
    from app import create_app, db

    email_org1 = seeded["emails"]["enterprise_architect"]
    org1_id = seeded["ids"]["org"]
    solution_id = seeded["ids"]["solution"]

    app = create_app("testing")
    seeded_element_ids = []
    org2_id = None
    org2_email = None
    with app.app_context():
        from app.models.archimate_core import ArchiMateElement
        from app.models.organization import Organization
        from app.models.solution_archimate_element import SolutionArchiMateElement
        from app.models.user import Role, User
        from werkzeug.security import generate_password_hash

        suffix = uuid.uuid4().hex[:6]
        el = ArchiMateElement(
            name=f"Tenant Isolation Probe {suffix}", type="ApplicationComponent",
            layer="application", organization_id=org1_id,
        )
        db.session.add(el)
        db.session.commit()
        seeded_element_ids.append(el.id)
        db.session.add(SolutionArchiMateElement(solution_id=solution_id, element_id=el.id))
        db.session.commit()

        org2 = Organization(name=f"Other Org {suffix}", slug=f"other-org-{suffix}")
        db.session.add(org2)
        db.session.commit()
        org2_id = org2.id

        role = Role.query.filter_by(name="Architect").first()
        org2_email = f"other-org-{suffix}@example.com"
        user2 = User(
            email=org2_email, first_name="Other", last_name="Org",
            organization_id=org2_id, role=role, confirmed=True,
            password_hash=generate_password_hash(PASSWORD),
        )
        db.session.add(user2)
        db.session.commit()

    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        _login(page, live_server, email_org1)
        page.goto(live_server + "/dashboard/overview", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        csrf = page.evaluate(
            "() => document.querySelector('meta[name=csrf-token]')?.content || "
            "document.querySelector('input[name=csrf_token]')?.value"
        )
        resp = page.request.post(
            live_server + "/ai-chat/architect/viewpoints",
            data={"solution_id": solution_id},
            headers={"X-CSRFToken": csrf} if csrf else {},
        )
        assert resp.ok, resp.text()
        viewpoints = resp.json()["viewpoints"]
        diagram_id = next(vp["saved_diagram_id"] for vp in viewpoints if vp["saved_diagram_id"])
        page.context.clear_cookies()

        _login(page, live_server, org2_email)
        cross_org_resp = page.request.get(
            live_server + f"/archimate/api/saved-viewpoints/{diagram_id}"
        )
        assert cross_org_resp.status in (403, 404), (
            f"org2 could load org1's architect-generated diagram: "
            f"{cross_org_resp.status} {cross_org_resp.text()}"
        )
    finally:
        context.close()
        with app.app_context():
            from app.models.archimate_core import ArchiMateElement
            from app.models.organization import Organization
            from app.models.solution_archimate_element import SolutionArchiMateElement
            from app.models.archimate_core import SavedDiagramElement
            from app.models.user import User

            SavedDiagramElement.query.filter(
                SavedDiagramElement.element_id.in_(seeded_element_ids)
            ).delete(synchronize_session=False)
            SolutionArchiMateElement.query.filter(
                SolutionArchiMateElement.element_id.in_(seeded_element_ids)
            ).delete(synchronize_session=False)
            ArchiMateElement.query.filter(ArchiMateElement.id.in_(seeded_element_ids)).delete(
                synchronize_session=False
            )
            if org2_email:
                # Logging in as user2 writes a soc2_audit_log row referencing
                # them; clear it first or the User delete below hits a real FK.
                try:
                    from app.models.audit_log import AuditLog

                    user2 = User.query.filter_by(email=org2_email).first()
                    if user2:
                        AuditLog.query.filter_by(user_id=user2.id).delete(
                            synchronize_session=False
                        )
                except ImportError:
                    pass
                User.query.filter_by(email=org2_email).delete(synchronize_session=False)
            if org2_id:
                Organization.query.filter_by(id=org2_id).delete(synchronize_session=False)
            db.session.commit()
