"""The Owners section on the application record, in a real browser.

An organisation admin adds a person to a role from the record itself, sees
them listed, removes them, and sees the role return to "Not recorded"; a
text-recorded owner with one matching organisation user offers a one-click
confirm that turns the text into a real assignment; the edit page's picker
and the create modal's picker both write the same kind of row, reachable
from the record they end up on.
"""

import uuid

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login

pytestmark = [pytest.mark.smoke, pytest.mark.journey]


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.set_default_timeout(PAGE_TIMEOUT)
    ctx.set_default_navigation_timeout(PAGE_TIMEOUT)
    pg = ctx.new_page()
    yield pg
    ctx.close()


@pytest.fixture
def owners_journey_records(app, seeded):
    """One target user and three applications, each set up for one step of
    the journey, on the seeded organisation. Cleaned up even on failure."""
    from app import db
    from app.models.application_owner import ApplicationOwner
    from app.models.application_portfolio import ApplicationComponent
    from app.models.user import Role, User

    suffix = uuid.uuid4().hex[:8]
    org_id = seeded["ids"]["org"]
    target_name = f"Owner Target {suffix}"
    app_ids = []
    target_id = None
    created_app_ids = []

    try:
        with app.app_context():
            db.session.remove()
            architect_role = Role.query.filter_by(name="Architect").one()
            target = User(
                email=f"owners-journey-target-{suffix}@example.com",
                first_name="Owner",
                last_name=f"Target {suffix}",
                organization_id=org_id,
                role=architect_role,
                confirmed=True,
            )
            db.session.add(target)
            db.session.flush()
            target_id = target.id

            add_remove_app = ApplicationComponent(
                name=f"Owners journey add-remove {suffix}", organization_id=org_id,
            )
            confirm_app = ApplicationComponent(
                name=f"Owners journey confirm {suffix}", organization_id=org_id,
                business_owner=target_name,
            )
            edit_app = ApplicationComponent(
                name=f"Owners journey edit {suffix}", organization_id=org_id,
            )
            db.session.add_all([add_remove_app, confirm_app, edit_app])
            db.session.commit()
            app_ids = [add_remove_app.id, confirm_app.id, edit_app.id]
            db.session.remove()

        yield {
            "target_name": target_name,
            "target_id": target_id,
            "add_remove_app_id": app_ids[0],
            "confirm_app_id": app_ids[1],
            "edit_app_id": app_ids[2],
            "created_app_ids": created_app_ids,
        }
    finally:
        with app.app_context():
            from app.models.archimate_core import ArchiMateElement

            db.session.rollback()
            all_app_ids = app_ids + created_app_ids
            if all_app_ids:
                ApplicationOwner.query.filter(
                    ApplicationOwner.application_id.in_(all_app_ids)
                ).delete(synchronize_session=False)
                element_ids = [
                    row.archimate_element_id
                    for row in ApplicationComponent.query.filter(
                        ApplicationComponent.id.in_(all_app_ids),
                        ApplicationComponent.organization_id == org_id,
                    ).all()
                    if row.archimate_element_id
                ]
                ApplicationComponent.query.filter(
                    ApplicationComponent.id.in_(all_app_ids),
                    ApplicationComponent.organization_id == org_id,
                ).delete(synchronize_session=False)
                if element_ids:
                    ArchiMateElement.query.filter(
                        ArchiMateElement.id.in_(element_ids)
                    ).delete(synchronize_session=False)
            if target_id:
                ApplicationOwner.query.filter_by(user_id=target_id).delete(
                    synchronize_session=False
                )
                User.query.filter_by(id=target_id).delete(synchronize_session=False)
            db.session.commit()
            db.session.remove()


def _role_card(page, role_label):
    return page.locator(
        "div.border.border-border.rounded-lg.p-3", has_text=role_label
    )


def test_owners_write_path_journey(page, live_server, seeded, owners_journey_records):
    fixture = owners_journey_records
    target_name = fixture["target_name"]

    _login(page, live_server, seeded["emails"]["platform_admin"])

    # ── add a person to a role, see them listed, remove them ──────────────
    detail_url = live_server + f"/applications/{fixture['add_remove_app_id']}"
    response = page.goto(detail_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    assert response is not None and response.status == 200

    technical_card = _role_card(page, "Technical Owner")
    expect(technical_card.get_by_text("Not recorded")).to_be_visible()

    technical_card.locator("#owner_add_technical").fill(target_name)
    technical_card.get_by_text(target_name, exact=True).click()
    technical_card.get_by_role("button", name="Add", exact=True).click()

    technical_card = _role_card(page, "Technical Owner")
    expect(technical_card.get_by_text(target_name, exact=True)).to_be_visible()

    technical_card.get_by_role("button", name="Remove Technical Owner").click()

    technical_card = _role_card(page, "Technical Owner")
    expect(technical_card.get_by_text("Not recorded")).to_be_visible()

    # ── a text-recorded owner with one matching user offers a confirm ─────
    detail_url = live_server + f"/applications/{fixture['confirm_app_id']}"
    response = page.goto(detail_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    assert response is not None and response.status == 200

    expect(page.get_by_text(f"Recorded as text: {target_name}")).to_be_visible()
    page.get_by_role(
        "button", name=f"Confirm {target_name} as Business Owner"
    ).click()

    expect(page.get_by_text(f"Recorded as text: {target_name}")).not_to_be_visible()
    business_card = _role_card(page, "Business Owner")
    expect(business_card.get_by_text(target_name, exact=True)).to_be_visible()

    # ── the edit page's picker writes the same kind of row ────────────────
    edit_url = live_server + f"/applications/{fixture['edit_app_id']}/edit"
    response = page.goto(edit_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    assert response is not None and response.status == 200

    page.fill("#business_owner_picker", target_name)
    page.get_by_text(target_name, exact=True).click()
    page.get_by_role("button", name="Save Changes", exact=True).click()

    business_card = _role_card(page, "Business Owner")
    expect(business_card.get_by_text(target_name, exact=True)).to_be_visible()

    # ── the create modal's picker lands on a record showing the person ────
    list_url = live_server + "/applications/"
    response = page.goto(list_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    assert response is not None and response.status == 200

    new_name = f"Owners journey created {uuid.uuid4().hex[:8]}"
    page.get_by_test_id("btn-add-application").click()
    page.fill("#ca-name", new_name)
    page.fill("#ca-owner", target_name)
    page.get_by_text(target_name, exact=True).click()

    with page.expect_response(
        lambda r: r.url.endswith("/applications/create") and r.request.method == "POST"
    ) as create_response:
        page.get_by_role("button", name="Add Application", exact=True).click()
    created = create_response.value.json()
    assert created.get("success") is True, created
    new_app_id = created["id"]
    fixture["created_app_ids"].append(new_app_id)

    response = page.goto(
        live_server + f"/applications/{new_app_id}",
        wait_until="domcontentloaded",
        timeout=PAGE_TIMEOUT,
    )
    assert response is not None and response.status == 200
    business_card = _role_card(page, "Business Owner")
    expect(business_card.get_by_text(target_name, exact=True)).to_be_visible()
