"""Persona sidebar zone budgets and membership (shell-overhaul Wave 1, Task 2).

Pure unit tests against app.utils.role_access.SIDEBAR_ZONES / get_sidebar_zones —
no app/db fixtures needed, the structure is plain Python data.
"""

from collections import Counter

from app.models.user import (
    ROLE_APPLICATION_MANAGER,
    ROLE_ARB_MEMBER,
    ROLE_BUSINESS_ARCHITECT,
    ROLE_CTO,
    ROLE_ENTERPRISE_ARCHITECT,
    ROLE_PLATFORM_ADMIN,
    ROLE_PORTFOLIO_MANAGER,
    ROLE_PROCUREMENT,
    ROLE_SOLUTION_ARCHITECT,
)
from app.utils.role_access import (
    SIDEBAR_LINK_BUDGET,
    SIDEBAR_ZONES,
    get_sidebar_zones,
)

ALL_ROLES = [
    ROLE_SOLUTION_ARCHITECT,
    ROLE_ENTERPRISE_ARCHITECT,
    ROLE_BUSINESS_ARCHITECT,
    ROLE_ARB_MEMBER,
    ROLE_PORTFOLIO_MANAGER,
    ROLE_CTO,
    ROLE_APPLICATION_MANAGER,
    ROLE_PROCUREMENT,
    ROLE_PLATFORM_ADMIN,
]

BOARD_ROLES = {ROLE_ENTERPRISE_ARCHITECT, ROLE_ARB_MEMBER, ROLE_CTO, ROLE_PLATFORM_ADMIN}


class _StubUser:
    def __init__(self, role, is_platform_admin=False):
        self.enterprise_role = role
        self.is_platform_admin = is_platform_admin

    def is_admin(self):
        return self.is_platform_admin


def _zone_names(role):
    return {zone["zone"] for zone in SIDEBAR_ZONES[role]}


def _all_links(role):
    links = []
    for zone in SIDEBAR_ZONES[role]:
        links.extend(zone["links"])
    return links


def test_sidebar_link_budget_is_28():
    """Raised 25 -> 26 in the Task 3 fix round (coordinator review of the
    sidebar rewrite): platform_admin's two review-mandated admin-zone links
    (Salesforce Integration, Power Platform) alone render exactly 25 visible
    links, leaving no headroom for the also-mandatory All-modules directory
    link.

    Lowered back 26 -> 25 in the evidence-review fix round: My-work's
    "Applications" link for platform_admin duplicated Library's — same
    endpoint, same label, twice in the sidebar — and removing it dropped the
    real count by exactly one. See app/utils/role_access.py's
    SIDEBAR_LINK_BUDGET comment and
    tests/test_sidebar_render.py::test_platform_admin_hits_the_link_budget_exactly.

    Raised 27 -> 28 (BA-A1, 21 Aug 2026): the Business Architecture landing page
    is the front door to all twelve BA outputs, and platform_admin is the default
    role for anyone who never picked one — so it is the role that most needs the
    link, and its only shared zone was already exactly on the ceiling. Retiring
    "Batch Import" to make room would have regressed the S-11 finding that put it
    there, trading one discoverability defect for another.

    S-11 (18 Aug 2026): raised 25 -> 26 for the one governance link added to
    surface Architecture Decisions, which platform_admin also renders.
    """
    assert SIDEBAR_LINK_BUDGET == 28


def test_every_role_is_defined():
    for role in ALL_ROLES:
        assert role in SIDEBAR_ZONES, f"missing SIDEBAR_ZONES entry for {role}"


def test_every_role_within_link_budget():
    for role in ALL_ROLES:
        total = len(_all_links(role))
        assert total <= SIDEBAR_LINK_BUDGET, (
            f"{role} has {total} sidebar links, budget is {SIDEBAR_LINK_BUDGET}"
        )


def test_every_role_has_home_my_work_library():
    for role in ALL_ROLES:
        zones = _zone_names(role)
        assert {"home", "my_work", "library"}.issubset(zones), (
            f"{role} is missing one of home/my_work/library, has {zones}"
        )


def test_only_board_roles_have_governance():
    for role in ALL_ROLES:
        zones = _zone_names(role)
        if role in BOARD_ROLES:
            assert "governance" in zones, f"{role} should have a governance zone"
        else:
            assert "governance" not in zones, f"{role} should not have a governance zone"


def test_only_platform_admin_has_admin_zone():
    for role in ALL_ROLES:
        zones = _zone_names(role)
        if role == ROLE_PLATFORM_ADMIN:
            assert "admin" in zones, "platform_admin should have an admin zone"
        else:
            assert "admin" not in zones, f"{role} should not have an admin zone"


def test_every_endpoint_is_a_dotted_string():
    for role in ALL_ROLES:
        for link in _all_links(role):
            endpoint = link["endpoint"]
            assert isinstance(endpoint, str), f"{role} link {link!r} endpoint is not a string"
            assert "." in endpoint, f"{role} link {link!r} endpoint is not dotted"


def _my_work_labels(role):
    for zone in SIDEBAR_ZONES[role]:
        if zone["zone"] == "my_work":
            return [link["label"] for link in zone["links"]]
    raise AssertionError(f"{role} has no my_work zone")


def test_solution_architect_my_work_membership():
    """Task 3 fix round: Programmes (solution_design.programmes_list) added —
    a real, working route reachable from nowhere in the sidebar. Coordinator
    review of the sidebar rewrite; membership amended accordingly."""
    assert _my_work_labels(ROLE_SOLUTION_ARCHITECT) == [
        "Architecture Journey",
        "Solutions",
        "AI Chat",
        "ADM Kanban",
        # 31 Aug 2026: the ARB dashboard was reachable from no persona's
        # sidebar, though the solution architect is the role that takes work
        # TO the board. Adding it closed a handoff that stopped mid-journey.
        "Review Board",
        "Programmes",
    ]


def test_enterprise_architect_my_work_membership():
    """Task 3 fix round: ArchiMate Composer and Traceability Matrix added —
    both real, working routes reachable from nowhere in the sidebar.
    Coordinator review of the sidebar rewrite; membership amended
    accordingly."""
    assert _my_work_labels(ROLE_ENTERPRISE_ARCHITECT) == [
        "Transformation programmes",
        # BA-A3 (21 Aug 2026): "Business Architecture" is deliberately absent
        # here — this role renders 26 links, exactly the sidebar_links ratchet
        # baseline, so a 27th would trip the gate. See the comment on this
        # role's entry in app/utils/role_access.py.
        "Portfolio",
        # NAV-1 (27 Aug 2026): "Capability Map" removed — it pointed at
        # capability_map.index, the identical endpoint Library already renders
        # as "Capabilities" for every role, so this persona showed one page
        # twice. Rendered total 26 -> 25, which is what let the nav-coverage
        # links land elsewhere without any persona exceeding the budget.
        "Roadmaps",
        "ArchiMate Composer",
        "Traceability Matrix",
        # S-11: real Implementation & Migration pages that were reachable
        # from nowhere in the sidebar.
        "Gap Analysis",
        "Work Packages",
        # S-11 remainder: directory-only, never in a sidebar zone.
        "Impact Analysis",
        "Capability Health",
        "Duplicate Detection",
        # ARCH-123 / ARCH-124 (QA register closure, 18 Aug 2026): Data
        # Architecture (existing, previously undiscoverable) and Tech Radar
        # (new), folded into enterprise_architect's My work since there is
        # no dedicated Data Architect / Technical Architect role yet.
        "Data Architecture",
        "Tech Radar",
    ]


def test_cto_my_work_membership():
    assert _my_work_labels(ROLE_CTO) == [
        # 31 Aug 2026: main.capability_roadmap is the CTO's own planning
        # surface and was linked from nowhere. It belongs first -- it is the
        # screen this persona opens to answer "what are we doing next".
        "Roadmaps",
        "Transformation programmes",
        "Health Scorecard",
        "Rationalization",
        "Investment Analysis",
        # NAV-1: nav-coverage output 9 (KPI/metric dashboards) had routes but
        # no sidebar link in any persona.
        "Portfolio KPIs",
        # Level 10 walkthrough, 30 Aug 2026: the radar is the CTO's technology
        # direction instrument and /technology/radar/classify names "cto" in
        # its own require_roles list -- the persona was authorised to set the
        # rings and had no link to the page from anywhere.
        "Tech Radar",
    ]


def test_business_architect_my_work_membership():
    """S-11 remainder: Stakeholder Map and Capability Frameworks were real,
    working pages reachable only from /modules/, never from any sidebar
    zone.

    BA-A1/A2 (20 Aug 2026): the persona carried 4 links against a budget of
    27 while enterprise_architect carried 13, so most of what a business
    architect needs was reachable only by typing a URL. "Capability
    Frameworks" was replaced by "Capability Maturity" pointing at the
    heatmap — frameworks_overview is the one maturity page that renders
    near-empty, and it was this persona's only maturity link.

    BA-A3 (21 Aug 2026): the /business-architecture practice landing page
    added first, as the front door to all twelve BA outputs.

    Corrected same day: "Capability Frameworks" is restored ALONGSIDE the
    heatmap rather than replaced by it. Repointing this persona's only maturity
    link had removed frameworks_overview from every sidebar zone, regressing the
    S-11 finding above — the full suite caught it; the targeted runs did not."""
    assert _my_work_labels(ROLE_BUSINESS_ARCHITECT) == [
        "Architecture Journey",
        "Capability Map",
        "Capability Maturity",
        "Capability Frameworks",
        "Value Streams",
        "Stakeholder Map",
        "Gap Analysis",
        "Roadmaps",
        "Work Packages",
        "Traceability Matrix",
        "Capability Health",
        "Data Architecture",
        # NAV-1 (27 Aug 2026): nav-coverage outputs 5, 6 and 10 — information/
        # data maps, strategy-to-execution and products & services — all had
        # working routes and no sidebar link in any persona. Every one of these
        # endpoints already shipped.
        "Data Lineage",
        "Motivation Model",
        "Products & Services",
    ]


def test_portfolio_manager_my_work_membership():
    """S-11 remainder: Consolidation List was directory-only."""
    assert _my_work_labels(ROLE_PORTFOLIO_MANAGER) == [
        "Portfolio",
        "Rationalization",
        "Vendors",
        "Applications",
        "Consolidation List",
        # NAV-1: see test_cto_my_work_membership — same page, other owner.
        "Portfolio KPIs",
    ]


def test_procurement_my_work_membership():
    """Task 3 fix round: Overview, Licences and Compliance added — all real,
    working routes reachable from nowhere in the sidebar. Overview goes
    first per the coordinator's review of the sidebar rewrite."""
    assert _my_work_labels(ROLE_PROCUREMENT) == [
        "Overview",
        "Vendors",
        "Contracts",
        "Renewals",
        "Spend",
        "Licences",
        "Compliance",
    ]


def test_application_manager_my_work_membership():
    """Task 3 fix round: My Applications added. my_applications.dashboard is
    a personally-scoped view (ApplicationOwner rows for the current user
    only) distinct from unified_applications.application_list's org-wide
    list — see app/modules/my_applications/routes.py:get_owned_apps — and
    was reachable from nowhere in the sidebar."""
    assert _my_work_labels(ROLE_APPLICATION_MANAGER) == [
        "My Applications",
        "Applications",
        "Rationalization",
        "Vendors",
    ]


def test_platform_admin_zone_link_total_is_pinned():
    """Task 3 fix round: platform_admin's two new admin-zone links
    (Salesforce Integration, Power Platform) bring its zone-only link total
    (SIDEBAR_ZONES data, not counting the sidebar's own header/footer chrome)
    to exactly 23. All-modules is deliberately NOT one of platform_admin's
    zone links — see _LIBRARY_LINKS_WITH_DIRECTORY's comment in
    role_access.py — so it does not appear in this count; it is still
    reachable via the sidebar footer fallback, pinned instead by
    tests/test_sidebar_render.py::test_platform_admin_hits_the_link_budget_exactly
    (which renders the template and counts real visible links, 26 including
    that fallback plus the header logo and footer logout links). An
    equality assertion here, not <=, so a future zone edit that silently
    changes this number is caught rather than absorbed by budget headroom
    that does not actually exist.

    Evidence-review fix round: 23 -> 22. _MY_WORK_LINKS[ROLE_PLATFORM_ADMIN]'s
    "Applications" link duplicated the one already in Library (same
    endpoint, unified_applications.application_list); removing it drops the
    zone-only total by one, and the rendered total (see
    test_platform_admin_hits_the_link_budget_exactly) by the same one, to
    25.

    S-11 (18 Aug 2026): 22 -> 23. The governance zone gained "Decisions"
    (arch_decisions.list_decisions), which platform_admin shares; the two
    Implementation & Migration links added in the same pass are
    enterprise_architect-only and do not appear here.

    S-11 remainder (18 Aug 2026): 23 -> 24. "Batch Import" added to the admin
    zone — the only S-11-remainder module platform_admin shares; the other
    nine landed in EA / business_architect / portfolio_manager My-work zones.

    BA-A3 (21 Aug 2026): 24 -> 25. "Business Architecture" added to this
    role's My work. platform_admin is the default enterprise_role for any
    user who never picked one, so a page limited to the two architect roles
    would be invisible to most real accounts. Rendered total 25 -> 26, still
    under SIDEBAR_LINK_BUDGET (27).
    """
    assert len(_all_links(ROLE_PLATFORM_ADMIN)) == 25


def test_platform_admin_collapsed_sidebar_icons_are_unambiguous():
    """A collapsed rail must not use one glyph for different destinations."""
    icons = [link["icon"] for link in _all_links(ROLE_PLATFORM_ADMIN)]
    duplicates = {icon: count for icon, count in Counter(icons).items() if count > 1}
    assert duplicates == {}


def test_get_sidebar_zones_resolves_role():
    user = _StubUser(ROLE_SOLUTION_ARCHITECT)
    zones = get_sidebar_zones(user)
    assert zones == SIDEBAR_ZONES[ROLE_SOLUTION_ARCHITECT]


def test_get_sidebar_zones_defaults_for_unknown_role():
    user = _StubUser("not_a_real_role")
    zones = get_sidebar_zones(user)
    assert zones == SIDEBAR_ZONES[ROLE_SOLUTION_ARCHITECT]


def test_get_sidebar_zones_never_raises_for_none_user():
    zones = get_sidebar_zones(None)
    assert zones == SIDEBAR_ZONES[ROLE_SOLUTION_ARCHITECT]


def test_admin_zone_hidden_without_is_platform_admin():
    """13 Aug 2026 QA finding: enterprise_role defaults to the string
    "platform_admin" for every user (backward-compat column default), which
    put the whole Admin nav zone — including /admin/organizations, a
    genuinely cross-tenant route — in front of ordinary users who never
    explicitly picked a role. The zone must now track the real
    is_platform_admin boolean (defaults False), not the string default.
    """
    user = _StubUser(ROLE_PLATFORM_ADMIN, is_platform_admin=False)
    zones = get_sidebar_zones(user)
    assert "admin" not in {z["zone"] for z in zones}


def test_admin_zone_shown_for_real_platform_admin():
    user = _StubUser(ROLE_PLATFORM_ADMIN, is_platform_admin=True)
    zones = get_sidebar_zones(user)
    assert "admin" in {z["zone"] for z in zones}
