"""Journey: can each archetype reach the product it is promised?

ENTERPRISE_ROLE_SECTION_MAP grants each of the nine archetypes a set of
sections. This asserts the promise is keepable - that every granted section
resolves to something the application actually serves.

Two archetypes fail that today, and the cause is documented in the codebase
itself. app/_bootstrap/blueprints.py::_register_persona_modules:

    North Star persona modules - REGISTRATION DISABLED 2026-06-11.
    procurement (7 page routes) and my_applications (5 page routes) were
    registered with ZERO templates ... every page route returned 500 for any
    user with the matching role.

Disabling them was correct - 500s are worse than absence. The defect is that
the persona model was never updated to match, so:

  * procurement is granted 3 sections and one of them does not exist
  * application_manager is granted 5 and its DEFINING section does not exist

The tests below encode that as fact rather than aspiration. When the modules
are re-enabled with templates, the xfail turns into an unexpected pass and this
file must be updated - which is the point.
"""

import pytest

from .conftest import login, make_org, make_user, reachable

pytestmark = pytest.mark.journey

# The section each archetype exists to use. Not every section they can see -
# the one that, if missing, means they cannot do their job.
SIGNATURE_SECTION = {
    "business_architect": ("/business-case", "business_architecture"),
    "enterprise_architect": ("/value-streams", "architecture"),
    "solution_architect": ("/solutions", "solutions"),
    "portfolio_manager": ("/applications", "portfolio"),
    "application_manager": ("/my-applications", "my_applications"),
    "procurement": ("/procurement", "procurement"),
}

DISABLED_MODULES = {"my_applications", "procurement"}


@pytest.mark.parametrize(
    "archetype",
    [a for a, (_, s) in SIGNATURE_SECTION.items() if s not in DISABLED_MODULES],
)
def test_archetype_can_reach_its_signature_section(app, client, archetype):
    from app import db

    path, _section = SIGNATURE_SECTION[archetype]
    with app.app_context():
        org_id = make_org(db, "Journey")
        user_id = make_user(db, org_id, archetype[:12], enterprise_role=archetype)

    login(client, user_id)
    ok, status = reachable(client, path)
    assert ok, (
        "%s is granted this section by ENTERPRISE_ROLE_SECTION_MAP but %s "
        "returned 404 - the capability is advertised and not served" % (archetype, path)
    )


@pytest.mark.parametrize(
    "archetype",
    [a for a, (_, s) in SIGNATURE_SECTION.items() if s in DISABLED_MODULES],
)
def test_disabled_persona_modules_are_still_advertised(app, client, archetype):
    """These archetypes are promised a section the app does not serve.

    Deliberately asserts the BROKEN state, so the gap is visible in CI rather
    than living only in a docstring. Re-enabling the module should break this
    test.
    """
    from app import db

    path, section = SIGNATURE_SECTION[archetype]
    with app.app_context():
        org_id = make_org(db, "Journey")
        user_id = make_user(db, org_id, archetype[:12], enterprise_role=archetype)

    login(client, user_id)
    ok, status = reachable(client, path)
    assert not ok, (
        "%s now resolves (status %s). The %s module appears to be registered "
        "again - remove this archetype from DISABLED_MODULES and move it to the "
        "positive test above." % (path, status, section)
    )


def test_the_persona_map_and_the_live_navigation_use_different_taxonomies():
    """The persona model is orphaned from the navigation users actually see.

    ENTERPRISE_ROLE_SECTION_MAP is keyed on workflow sections (solutions,
    portfolio, governance). The sidebar rendered by 175 of 177 templates,
    admin_sidebar_northstar_phase2.html, is organised by ArchiMate element
    types (Business Actors, Application Components). There is no overlap, and
    the sidebar consumes no authorisation construct at all.

    This is a product-strategy gap, not a bug, so it is asserted rather than
    fixed: retrofitting a mapping between the two taxonomies would mean
    inventing one.
    """
    import io
    import os

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    live = io.open(
        os.path.join(root, "app/templates/components/admin_sidebar_northstar_phase2.html"),
        encoding="utf-8",
    ).read()

    gates = [
        "user_visible_sections", "show_all_sections", "current_user.can",
        "is_platform_admin", "enterprise_role", "required_roles", "has_role",
    ]
    present = {g: live.count(g) for g in gates if live.count(g)}
    assert not present, (
        "The live sidebar now references %s. If persona gating has been wired "
        "up, delete this test - it exists to record that it was not." % present
    )
