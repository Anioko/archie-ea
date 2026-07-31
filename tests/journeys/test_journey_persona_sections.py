"""Journey: can each archetype reach the product it is promised?

ENTERPRISE_ROLE_SECTION_MAP grants each of the nine archetypes a set of
sections. This asserts the promise is keepable - that every granted section
resolves to something the application actually serves.

Two archetypes failed that until 2026-07-31. app/_bootstrap/blueprints.py had
disabled the procurement and my_applications modules on 2026-06-11 because every
page route returned 500 - so procurement was promised 3 sections with 1 missing,
and application_manager was promised 5 with its DEFINING section missing.

The earlier version of this file asserted that broken state deliberately, so
that re-enabling the modules would break the test and force the model and the
runtime to be reconciled rather than drift apart again. That is exactly what
happened: the modules were re-enabled once their templates were found to exist
all along, in each blueprint's own template_folder rather than app/templates/,
and this file had to be updated in the same change.

All nine archetypes now reach the section they exist to use. Whether those pages
render is asserted separately, in test_journey_persona_modules.py.
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
    # /procurement itself has no index route - the blueprint's routes all sit
    # one level down (/contracts, /renewals, /licenses, /compliance, /spend).
    # Contracts is the natural entry point. Worth noting as a UX gap: a user who
    # navigates to the section root gets a 404 rather than a landing page.
    "procurement": ("/procurement/contracts", "procurement"),
}

# Emptied 2026-07-31: both modules were re-enabled after verifying their
# templates existed all along, in each blueprint's own template_folder.
DISABLED_MODULES = set()


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


def test_no_archetype_is_promised_a_section_the_app_does_not_serve():
    """The persona model and the runtime must agree.

    Until 2026-07-31 they did not: ENTERPRISE_ROLE_SECTION_MAP granted
    procurement and application_manager a section whose module was
    registration-disabled, so two of nine archetypes were advertised a product
    that returned 404. The previous version of this file asserted that broken
    state deliberately, so that re-enabling the modules would break the test and
    force this reconciliation. It did.

    DISABLED_MODULES is now empty. If a module is ever disabled again, add it
    back here AND remove the matching grant from ENTERPRISE_ROLE_SECTION_MAP -
    the two must move together.
    """
    assert not DISABLED_MODULES, (
        "Modules are disabled again: %s. Remove the matching sections from "
        "ENTERPRISE_ROLE_SECTION_MAP so the product stops advertising them."
        % sorted(DISABLED_MODULES)
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
