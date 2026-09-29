"""Enterprise Architect opens model freshness, re-scans, reloads and still sees the stalest owners.

Seeds, in the shared smoke organisation, an application whose record was last
saved 400 days ago and whose owner is a named person, plus a second
organisation with an even staler owner. Signs in as the Enterprise Architect,
opens the model health page, reads the freshness figure and the stalest-owner
list, clicks "Re-scan for drift", reloads, and checks the list is still there
and never names the other organisation's owner.
"""

import re
import uuid
from datetime import datetime, timedelta

import pytest
from playwright.sync_api import expect

from .conftest import PAGE_TIMEOUT
from .test_archetype_journeys import _login, _visit

pytestmark = [pytest.mark.smoke, pytest.mark.journey]

MODEL_HEALTH = "/genome/model-health/"


@pytest.fixture(scope="module")
def stale_owners(seeded, request):
    from app import create_app, db

    app = create_app("testing")
    suffix = uuid.uuid4().hex[:8]
    created = {"apps": [], "users": [], "orgs": []}
    names = {"ours": "Stale %s" % suffix, "theirs": "Foreign %s" % suffix}

    def seed_owner(session, org_id, last_name, days_old):
        from app.models.application_owner import ApplicationOwner
        from app.models.application_portfolio import ApplicationComponent
        from app.models.user import User

        user = User(email="fresh.%s.%s@example.com" % (last_name.split()[0].lower(), suffix),
                    first_name="Owner", last_name=last_name,
                    organization_id=org_id, confirmed=True, enterprise_role="application_manager")
        session.add(user)
        session.flush()
        component = ApplicationComponent(name="Freshness app %s %s" % (last_name, suffix),
                                         organization_id=org_id)
        session.add(component)
        session.flush()
        session.query(ApplicationComponent).filter(ApplicationComponent.id == component.id).update(
            {"updated_at": datetime.utcnow() - timedelta(days=days_old)}, synchronize_session=False)
        session.add(ApplicationOwner(application_id=component.id, user_id=user.id,
                                     organization_id=org_id, ownership_type="primary"))
        created["apps"].append((component.id, component.archimate_element_id))
        created["users"].append(user.id)

    with app.app_context():
        from app.models.organization import Organization

        session = db.session
        seed_owner(session, seeded["ids"]["org"], names["ours"], 400)
        other = Organization(name="Smoke Freshness Other %s" % suffix, slug="smoke-fresh-other-%s" % suffix)
        session.add(other)
        session.flush()
        created["orgs"].append(other.id)
        seed_owner(session, other.id, names["theirs"], 2000)
        session.commit()

    def remove_rows():
        with app.app_context():
            from app.models.application_owner import ApplicationOwner
            from app.models.application_portfolio import ApplicationComponent
            from app.models.archimate_core import ArchiMateElement
            from app.models.organization import Organization
            from app.models.user import User

            db.session.remove()
            app_ids = [a for a, _ in created["apps"]]
            element_ids = [e for _, e in created["apps"] if e]
            db.session.query(ApplicationOwner).filter(
                ApplicationOwner.application_id.in_(app_ids)).delete(synchronize_session=False)
            db.session.query(ApplicationComponent).filter(
                ApplicationComponent.id.in_(app_ids)).delete(synchronize_session=False)
            if element_ids:
                db.session.query(ArchiMateElement).filter(
                    ArchiMateElement.id.in_(element_ids)).delete(synchronize_session=False)
            db.session.query(User).filter(User.id.in_(created["users"])).delete(synchronize_session=False)
            db.session.query(Organization).filter(
                Organization.id.in_(created["orgs"])).delete(synchronize_session=False)
            db.session.commit()
            db.session.remove()

    request.addfinalizer(remove_rows)
    return names


def test_freshness_stalest_owners_survive_rescan_and_reload(browser, live_server, seeded, stale_owners):
    page = browser.new_page()
    try:
        _login(page, live_server, seeded["emails"]["enterprise_architect"])
        response, _state = _visit(page, live_server, MODEL_HEALTH)
        assert response.status == 200, "model health page HTTP %s" % response.status

        section = page.locator("#model-freshness")
        expect(section.get_by_role("heading", name="Freshness")).to_be_visible()
        # The seeded organisation has dated application records, so a figure is shown.
        expect(section.get_by_test_id("freshness-share")).to_have_text(re.compile(r"^\d+%$"))
        stalest = section.get_by_test_id("stalest-owners")
        expect(stalest).to_contain_text("Owner %s" % stale_owners["ours"])
        expect(section).not_to_contain_text(stale_owners["theirs"])

        # The page's own control: re-scan, then reload the result.
        page.get_by_role("button", name="Re-scan for drift").click()
        page.wait_for_load_state("domcontentloaded")
        page.reload(wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)

        section = page.locator("#model-freshness")
        stalest = section.get_by_test_id("stalest-owners")
        expect(stalest).to_contain_text("Owner %s" % stale_owners["ours"])
        expect(section.get_by_test_id("freshness-by-owner")).to_contain_text("Owner %s" % stale_owners["ours"])
        expect(section).not_to_contain_text(stale_owners["theirs"])
    finally:
        page.close()
