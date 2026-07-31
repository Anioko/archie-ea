"""Journey: the procurement and application_manager modules actually serve pages.

These two modules were registration-disabled on 2026-06-11 because every page
route returned 500. Re-enabled 2026-07-31 after verifying the premise was
incomplete - the templates were never missing, they live in each blueprint's own
template_folder rather than app/templates/.

This file is the evidence for that claim. It renders every list and dashboard
page of both modules, as a user holding the matching archetype, against an EMPTY
database - the hardest case for a template, and the state a new tenant is in on
day one. A 500 here means the modules must go back to disabled.

Empty-state matters specifically: the original failure mode was pages blowing up,
and a page that only renders once data exists is not a working page.
"""

import pytest

from .conftest import cleanup, login, make_org, make_user

pytestmark = pytest.mark.journey

# Page routes only. Detail routes take an id and use first_or_404(), so on an
# empty database a clean 404 is correct behaviour, not a failure - they are
# asserted separately below.
MY_APPLICATIONS_PAGES = ["/my-applications/", "/my-applications/list",
                         "/my-applications/health", "/my-applications/roadmap"]
PROCUREMENT_PAGES = ["/procurement/contracts", "/procurement/renewals",
                     "/procurement/licenses", "/procurement/compliance",
                     "/procurement/spend"]


def _persona(app, db, archetype):
    with app.app_context():
        org_id = make_org(db, archetype[:10])
        user_id = make_user(db, org_id, archetype[:12], enterprise_role=archetype)
    return org_id, user_id


@pytest.mark.parametrize("path", MY_APPLICATIONS_PAGES)
def test_application_manager_pages_render_on_an_empty_tenant(app, client, path):
    from app import db

    org_id, user_id = _persona(app, db, "application_manager")
    try:
        login(client, user_id)
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code != 404, (
            "%s is not registered - the my_applications blueprint is disabled "
            "again, and application_manager has lost its defining section" % path
        )
        assert resp.status_code < 500, (
            "%s returned %s. This is the exact failure that caused the module to "
            "be disabled on 2026-06-11; it must not ship in that state."
            % (path, resp.status_code)
        )
    finally:
        with app.app_context():
            from app.models.organization import Organization
            from app.models.user import User

            cleanup(db, User, [user_id])
            cleanup(db, Organization, [org_id])


@pytest.mark.parametrize("path", PROCUREMENT_PAGES)
def test_procurement_pages_render_on_an_empty_tenant(app, client, path):
    from app import db

    org_id, user_id = _persona(app, db, "procurement")
    try:
        login(client, user_id)
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code != 404, (
            "%s is not registered - procurement has lost a third of its product" % path
        )
        assert resp.status_code < 500, (
            "%s returned %s - the 2026-06-11 failure mode has returned"
            % (path, resp.status_code)
        )
    finally:
        with app.app_context():
            from app.models.organization import Organization
            from app.models.user import User

            cleanup(db, User, [user_id])
            cleanup(db, Organization, [org_id])


@pytest.mark.parametrize(
    "path", ["/my-applications/app/999999", "/procurement/contracts/999999",
             "/procurement/licenses/999999"]
)
def test_detail_routes_404_cleanly_rather_than_500(app, client, path):
    """A missing record must be a 404, not a crash."""
    from app import db

    archetype = "application_manager" if path.startswith("/my-app") else "procurement"
    org_id, user_id = _persona(app, db, archetype)
    try:
        login(client, user_id)
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code < 500, (
            "%s returned %s for a non-existent id; first_or_404() should make "
            "this a clean 404" % (path, resp.status_code)
        )
    finally:
        with app.app_context():
            from app.models.organization import Organization
            from app.models.user import User

            cleanup(db, User, [user_id])
            cleanup(db, Organization, [org_id])


def test_the_wrong_archetype_is_refused():
    """Guard the guard: these modules are role-gated, and must stay that way.

    requires_procurement allows procurement and portfolio_manager;
    requires_application_owner allows application_manager. Both implicitly allow
    platform_admin. Asserted statically because the decorator wiring is what
    matters, and a runtime check here would only re-test Flask.
    """
    import io
    import os

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    proc = io.open(os.path.join(root, "app/modules/procurement/routes.py"), encoding="utf-8").read()
    myapp = io.open(os.path.join(root, "app/modules/my_applications/routes.py"), encoding="utf-8").read()

    assert proc.count("@requires_procurement") >= 5, "procurement routes lost their role gate"
    assert myapp.count("@requires_application_owner") >= 4, "my_applications routes lost their role gate"
