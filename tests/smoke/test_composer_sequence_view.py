"""Composer Sequence View: a lifeline/message render of ArchiMate elements and
relationships already on the canvas (see composer.js layoutSequence, ADR 0008 —
one system of record per concept, no separate sequence-diagram store).

Why this exists: "Place Full Diagram on Canvas" previously threw a silent
TypeError on every click, because the composer's JS bundle never loaded
Platform.confirm (see core-composer.js / scripts/build_js.py). That regression
was invisible to every source-only gate — the button existed, its handler
existed, the call site was correct — and was only found by clicking it. This
test exists so Sequence View cannot regress the same way: it drives the real
button in a real browser and asserts the real DOM changed, not that the
handler is merely wired.

Seeds two ArchiMateElements, one relationship between them (no sequence_order
set, proving the created-at fallback works), and a saved diagram positioning
both — through the ORM, per this harness's convention, since the point is to
prove Sequence View, not the separate "place elements via the AI wizard" path.
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


@pytest.fixture()
def sequence_diagram(seeded):
    """A saved diagram with three elements and two un-ordered relationships,
    so the reorder panel has something real to swap (a single-message diagram
    can only prove rendering, not that a swap persists)."""
    from app import create_app, db
    from app.models.archimate_core import (
        ArchiMateElement, ArchiMateRelationship, SavedDiagram,
        SavedDiagramElement, SavedDiagramRelationship,
    )

    app = create_app("testing")
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        org_id = seeded["ids"]["org"]

        caller = ArchiMateElement(
            name="Order Service %s" % suffix, type="ApplicationComponent",
            layer="application", organization_id=org_id,
        )
        middle = ArchiMateElement(
            name="Payment Gateway %s" % suffix, type="ApplicationComponent",
            layer="application", organization_id=org_id,
        )
        callee = ArchiMateElement(
            name="Fraud Check %s" % suffix, type="ApplicationComponent",
            layer="application", organization_id=org_id,
        )
        db.session.add_all([caller, middle, callee])
        db.session.commit()

        # Created outside a request context: no g.current_org_id, so
        # organization_id must be set explicitly (see CLAUDE.md tenancy notes).
        rel1 = ArchiMateRelationship(source_id=caller.id, target_id=middle.id,
                                      type="triggering", organization_id=org_id)
        rel2 = ArchiMateRelationship(source_id=middle.id, target_id=callee.id,
                                      type="triggering", organization_id=org_id)
        db.session.add_all([rel1, rel2])
        db.session.commit()

        diagram = SavedDiagram(
            name="Sequence smoke %s" % suffix, viewpoint_type="application",
            organization_id=org_id,
        )
        db.session.add(diagram)
        db.session.commit()

        db.session.add_all([
            SavedDiagramElement(diagram_id=diagram.id, element_id=caller.id,
                                position_x=60, position_y=60, width=180, height=64),
            SavedDiagramElement(diagram_id=diagram.id, element_id=middle.id,
                                position_x=500, position_y=180, width=180, height=64),
            SavedDiagramElement(diagram_id=diagram.id, element_id=callee.id,
                                position_x=900, position_y=300, width=180, height=64),
        ])
        db.session.add_all([
            SavedDiagramRelationship(diagram_id=diagram.id, relationship_id=rel1.id),
            SavedDiagramRelationship(diagram_id=diagram.id, relationship_id=rel2.id),
        ])
        db.session.commit()

        ids = {"diagram_id": diagram.id, "rel1_id": rel1.id, "rel2_id": rel2.id}
        db.session.remove()
        return ids


@pytest.mark.smoke
def test_sequence_view_renders_lifelines_and_persists_reorder(browser, live_server, seeded, sequence_diagram):
    email = seeded["emails"]["solution_architect"]
    url = live_server + "/archimate/composer?viewpoint_id=%d" % sequence_diagram["diagram_id"]

    # >=1920px keeps "Layout" on the primary toolbar rather than collapsed into
    # "More" (CMP-063) — a real solution architect drives this from a desktop
    # monitor, not the 1280px default Playwright viewport.
    context = browser.new_context(ignore_https_errors=True, viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    _login(page, live_server, email)

    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    # The canvas boots asynchronously (JointJS init + viewpoint fetch); wait for
    # an element node rather than a fixed sleep.
    expect(page.locator(".joint-element").first).to_be_visible(timeout=PAGE_TIMEOUT)

    # Open the Layout dropdown and switch to Sequence View — this is the exact
    # handler ("Place Full Diagram on Canvas" is a different button) that was
    # never reachable while core-composer.js lacked Platform.confirm; this one
    # doesn't call Platform.confirm, but the underlying "did the bundle actually
    # load the JS that defines this Alpine method" failure mode is the same
    # class this test guards against.
    page.get_by_role("button", name="Layout").click()
    page.get_by_role("button", name="Sequence View").click()

    # The reorder panel is the visible proof the layout ran and found messages.
    panel = page.locator('[aria-label="Sequence View messages"]')
    expect(panel).to_be_visible(timeout=PAGE_TIMEOUT)
    rows = panel.locator("div.flex.items-center.gap-2.p-2")
    expect(rows).to_have_count(2, timeout=PAGE_TIMEOUT)
    expect(rows.nth(0)).to_contain_text("1. Triggering")
    expect(rows.nth(1)).to_contain_text("2. Triggering")

    # Three lifeline elements should now sit at the same y (top row).
    boxes = page.locator(".joint-element").evaluate_all(
        "els => els.map(e => e.getBoundingClientRect().top)"
    )
    assert len(set(round(b) for b in boxes)) == 1, (
        "expected every lifeline element at the same y after Sequence View, got %r" % boxes
    )

    # Move the second message earlier and assert the swap actually reaches the
    # relationship it renamed — a client-only reorder a reload would discard
    # is the same failure class as the dead "Place Full Diagram" button.
    with page.expect_response(
        lambda r: r.url.endswith("/archimate/api/relationships/%d" % sequence_diagram["rel1_id"])
        and r.request.method == "PUT"
    ):
        rows.nth(1).locator('[aria-label="Move message earlier"]').click()

    expect(rows.nth(0)).to_contain_text("1. Triggering", timeout=PAGE_TIMEOUT)

    from app import create_app, db
    from app.models.archimate_core import ArchiMateRelationship

    app = create_app("testing")
    with app.app_context():
        rel1 = db.session.get(ArchiMateRelationship, sequence_diagram["rel1_id"])
        rel2 = db.session.get(ArchiMateRelationship, sequence_diagram["rel2_id"])
        assert rel1.sequence_order == 1, "rel1 should have moved to step 2 (index 1)"
        assert rel2.sequence_order == 0, "rel2 should have moved to step 1 (index 0)"
        db.session.remove()
