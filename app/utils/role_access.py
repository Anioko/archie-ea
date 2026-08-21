"""
Role-Based Navigation Access Control (NS-006)

Defines which navigation sections each enterprise_role can access.
Used by admin_sidebar.html to filter navigation items.

Part of North Star Persona MVP implementation.
ADR Reference: docs/adr/0009-persona-based-navigation.md
"""

from typing import Dict, List, Set

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


# Navigation sections defined in the sidebar
NAVIGATION_SECTIONS = [
    "home",
    "solutions",
    "portfolio",
    "architecture",
    "capabilities",
    "business_architecture",
    "roadmaps",
    "governance",
    "procurement",
    "my_applications",
    "data_integration",
    "administration",
]

# Role to sections mapping
# Each role has a set of sections they can access
ROLE_SECTION_ACCESS: Dict[str, Set[str]] = {
    ROLE_SOLUTION_ARCHITECT: {
        "home",
        "solutions",
        "portfolio",
        "architecture",
        "capabilities",
        "roadmaps",
        "governance",
        "data_integration",
    },
    ROLE_ENTERPRISE_ARCHITECT: {
        "home",
        "solutions",
        "portfolio",
        "architecture",
        "capabilities",
        "business_architecture",
        "roadmaps",
        "governance",
        "data_integration",
    },
    ROLE_BUSINESS_ARCHITECT: {
        "home",
        "business_architecture",
        "capabilities",
        "architecture",
        "roadmaps",
        "governance",
        "portfolio",
        "solutions",
        "data_integration",
    },
    ROLE_ARB_MEMBER: {
        "home",
        "solutions",
        "portfolio",
        "governance",
    },
    ROLE_PORTFOLIO_MANAGER: {
        "home",
        "solutions",
        "portfolio",
        "capabilities",
        "roadmaps",
        "governance",
        "procurement",  # Read-only access to procurement for cost visibility
    },
    ROLE_CTO: {
        "home",
        "solutions",
        "portfolio",
        "capabilities",
        "roadmaps",
        "governance",
    },
    ROLE_PROCUREMENT: {
        "home",
        "portfolio",  # Read-only for app-vendor context
        "procurement",
    },
    ROLE_APPLICATION_MANAGER: {
        "home",
        "solutions",  # Read-only for impact awareness
        "portfolio",  # Read-only for integration context
        "my_applications",
        "roadmaps",  # Read-only
    },
    ROLE_PLATFORM_ADMIN: {
        "home",
        "solutions",
        "portfolio",
        "architecture",
        "capabilities",
        "business_architecture",
        "roadmaps",
        "governance",
        "procurement",
        "my_applications",
        "data_integration",
        "administration",
    },
}

# Sections that require specific roles (exclusive access)
EXCLUSIVE_SECTIONS: Dict[str, List[str]] = {
    "administration": [ROLE_PLATFORM_ADMIN],
    "procurement": [ROLE_PROCUREMENT, ROLE_PORTFOLIO_MANAGER, ROLE_PLATFORM_ADMIN],
    "my_applications": [ROLE_APPLICATION_MANAGER, ROLE_PLATFORM_ADMIN],
}

# Default role if user has no enterprise_role set
DEFAULT_ROLE = ROLE_SOLUTION_ARCHITECT


def get_user_role(user) -> str:
    """Get user's enterprise role with fallback to default.

    Must never raise. Since the shipped sidebar started calling
    can_access_section(), this runs while rendering EVERY authenticated page, so
    an exception here 500s the whole application rather than one feature.

    Reading the attribute can fail for reasons that have nothing to do with
    roles: a detached or expired instance re-fetches on access, and if the row
    has gone (or the session was rolled back mid-request) SQLAlchemy raises
    ObjectDeletedError. That is exactly what happened on the applications list
    error path - the view caught its own failure and re-rendered the template,
    and the sidebar then turned a handled error into an unhandled 500.

    `hasattr` does not protect against this: it only swallows AttributeError.
    """
    if not user:
        return DEFAULT_ROLE
    try:
        return getattr(user, "enterprise_role", None) or DEFAULT_ROLE
    except Exception:  # noqa: BLE001 - a nav gate must not be able to 500 a page
        return DEFAULT_ROLE


def can_access_section(user, section: str) -> bool:
    """
    Check if user can access a navigation section.

    Args:
        user: User object with enterprise_role attribute
        section: Navigation section identifier

    Returns:
        True if user can access the section
    """
    role = get_user_role(user)
    allowed_sections = ROLE_SECTION_ACCESS.get(role, set())
    return section in allowed_sections


def get_visible_sections(user) -> List[str]:
    """
    Get list of navigation sections visible to user.

    Args:
        user: User object with enterprise_role attribute

    Returns:
        List of section identifiers user can see
    """
    role = get_user_role(user)
    allowed_sections = ROLE_SECTION_ACCESS.get(role, set())
    # Return in defined order
    return [s for s in NAVIGATION_SECTIONS if s in allowed_sections]


def is_admin(user) -> bool:
    """Check if user has admin role."""
    return get_user_role(user) == ROLE_PLATFORM_ADMIN


def is_procurement(user) -> bool:
    """Check if user has procurement role."""
    return get_user_role(user) == ROLE_PROCUREMENT


def is_application_manager(user) -> bool:
    """Check if user has application manager role."""
    return get_user_role(user) == ROLE_APPLICATION_MANAGER


def get_role_display_name(role: str) -> str:
    """Get human-readable name for role."""
    from app.models.user import ROLE_DISPLAY_NAMES
    return ROLE_DISPLAY_NAMES.get(role, role.replace("_", " ").title())


def get_all_roles_with_access(section: str) -> List[str]:
    """Get all roles that can access a section."""
    return [
        role for role, sections in ROLE_SECTION_ACCESS.items()
        if section in sections
    ]


# ---------------------------------------------------------------------------
# Persona sidebar zones (shell-overhaul Wave 1)
#
# Single source of truth for the server-filtered sidebar: role -> ordered
# zones -> links. app/templates/components/admin_sidebar.html renders from
# get_sidebar_zones() only (Task 3) instead of the 1,062-line hand-maintained
# template that dimmed out-of-role links client-side. Endpoint strings below
# were resolved by grepping the pre-rewrite admin_sidebar.html for the real
# url_for(...) target of each spec surface; a few spec-named surfaces
# (Portfolio, Investment Analysis) have a real registered blueprint endpoint
# but no existing sidebar link — those are noted in the Task 2 report.
#
# Spec: docs/superpowers/specs/2026-08-12-shell-overhaul-design.md section 1.
#
# Fix round (Task 3 review): raised 25 -> 26. platform_admin's two new,
# review-mandated admin-zone links (Salesforce Integration, Power Platform)
# alone already render exactly 25 real links; the All-modules directory link
# (see _LIBRARY_LINKS_WITH_DIRECTORY below) is mandatory on every role's
# sidebar and platform_admin has no headroom left to absorb it without either
# dropping one of those two links or raising the budget by exactly the one
# link being added. Every other role stays well under 25 either way — see
# scripts/check_sidebar_links.py's per-role table.
#
# Fix round (evidence review, Wave 1 screenshot pass): lowered 26 -> 25.
# _MY_WORK_LINKS[ROLE_PLATFORM_ADMIN] carried an "Applications" link pointing
# at unified_applications.application_list — the exact same endpoint already
# in _LIBRARY_LINKS, so platform_admin rendered the label twice. Dropping the
# duplicate takes My work from 3 links to 2, so platform_admin's real link
# count (header + 22 zone links + footer All-modules + footer logout) is now
# 25, one below the old ceiling; the budget is lowered to match rather than
# left slack that would silently hide a future regression the same size.

# S-11 (discoverability wave, 18 Aug 2026): raised 25 -> 26. One governance
# link was added ("Decisions" -> arch_decisions.list_decisions), which is the
# only zone platform_admin — the role with zero headroom — shares. Its
# zone-only total goes 22 -> 23 and its rendered total 25 -> 26. The two
# Implementation & Migration links added in the same pass (Gap Analysis, Work
# Packages) land in the enterprise_architect My-work zone only, which has
# ample headroom, so they do not move this number.
#
# S-11 remainder (18 Aug 2026, QA Update 6/8): raised 26 -> 27. Ten modules
# were reachable only from /modules/, never from a sidebar zone. Nine of them
# landed in EA / business_architect / portfolio_manager My-work zones, all of
# which had headroom; the tenth ("Batch Import") landed in platform_admin's
# admin zone, the only zone that role shares, moving its zone-only total
# 23 -> 24 and rendered total 26 -> 27. The remaining three (my-applications
# list/health/roadmap) were nested as in-page tabs under the existing
# "My Applications" sidebar link rather than given zone entries of their own
# — see app/modules/my_applications/templates/my_applications/*.html.
#
# BA-A1 (21 Aug 2026): raised 27 -> 28. The Business Architecture landing page
# is the front door to all twelve business-architecture outputs, and an
# evaluating architect had concluded three of them did not exist because there
# was no such door. platform_admin is the default enterprise_role for anyone who
# never picked one, so it is the role that most needs the link, and its only
# shared zone (admin) was already exactly on the ceiling. The alternative was to
# retire "Batch Import", but that link exists to satisfy the S-11 finding above
# — trading one discoverability defect for another. Raising the budget by one is
# the honest cost of adding a front door.
SIDEBAR_LINK_BUDGET = 28

_ZONE_TITLES = {
    "home": "Home",
    "my_work": "My work",
    "library": "Library",
    "governance": "Governance",
    "admin": "Admin",
}


def _zone(zone_key, links):
    return {"zone": zone_key, "title": _ZONE_TITLES[zone_key], "links": links}


def _link(label, endpoint, icon):
    return {"label": label, "endpoint": endpoint, "icon": icon}


_HOME_LINKS = [
    _link("Dashboard Overview", "dashboard.overview", "layout-dashboard"),
    _link("Health Scorecard", "dashboard.health_scorecard", "heart-pulse"),
]

_LIBRARY_LINKS = [
    _link("Applications", "unified_applications.application_list", "list"),
    _link("Capabilities", "capability_map.index", "map"),
    _link("Vendors", "unified_applications.vendors", "building"),
    _link("ArchiMate Elements", "archimate_crud.dashboard", "table"),
]

# Fix round: the design's stated long-tail fallback ("Ctrl-K search + one new
# 'All modules' directory page") didn't exist — Ctrl-K is a visual hint with
# no wired event, and there was no directory page. app/modules/modules_directory
# is that page; this is the last Library link for every role except
# platform_admin, which is already exactly at SIDEBAR_LINK_BUDGET once its two
# new admin-zone links are added (see _ADMIN_LINKS below) and would go over if
# a fifth Library link were added too. admin_sidebar.html renders this link in
# the sidebar footer instead for whichever role's SIDEBAR_ZONES don't already
# contain it — currently just platform_admin — so it is still reachable from
# every role's sidebar, just not always from the same zone.
_ALL_MODULES_LINK = _link("All modules", "modules_directory.index", "grid-3x3")
_LIBRARY_LINKS_WITH_DIRECTORY = _LIBRARY_LINKS + [_ALL_MODULES_LINK]

_GOVERNANCE_LINKS = [
    _link("ARB Dashboard", "arb.dashboard", "layout-dashboard"),
    _link("Reviews", "arb.reviews", "shield-check"),
    _link("Sessions", "arb.sessions", "calendar"),
    # S-11: architecture decisions were reachable from nowhere in the sidebar.
    # `arch_decisions.list_decisions` is the canonical of two listings over the
    # same `architecture_decisions` table — it is the tenant-scoped one (its
    # model carries TenantMixin) and the one every template links to. The
    # duplicate, `adrs.list_adrs`, now 302s here; see
    # app/modules/architecture/routes/adr_routes.py:list_adrs.
    _link("Decisions", "arch_decisions.list_decisions", "gavel"),
]

_ADMIN_LINKS = [
    _link("Command Center", "admin.index", "layout-dashboard"),
    _link("Users", "admin.registered_users", "users"),
    _link("Organizations", "admin.organizations_list", "building-2"),
    _link("API Settings", "admin.api_settings", "key"),
    _link("AI Prompts", "solution_prompt_admin.solution_prompts_page", "sparkles"),
    _link("Governance Gates", "admin.governance_gates", "shield-check"),
    _link("Import History", "dashboard_pages.import_history", "history"),
    _link("Seed Management", "admin.seed_management", "database"),
    _link("Settings", "main.settings", "settings"),
    # Added in the Task 3 fix round (review finding: orphaned real routes —
    # both existed, worked, and had no sidebar link of any kind).
    _link("Salesforce Integration", "admin.salesforce_integration", "cloud"),
    _link("Power Platform", "admin.power_platform_integration", "grid-3x3"),
    # S-11 remainder (18 Aug 2026): batch import was directory-only, never in
    # a sidebar zone of any role.
    _link("Batch Import", "batch_import_view.dashboard", "upload"),
]

# Per-role "My work" — the persona's primary surface, 3-6 items.
# SA / EA / CTO membership below is pinned verbatim to the spec's zone table
# (docs/superpowers/specs/2026-08-12-shell-overhaul-design.md section 1) and
# asserted exactly by tests/test_sidebar_budgets.py.
_MY_WORK_LINKS = {
    ROLE_SOLUTION_ARCHITECT: [
        _link("Architecture Journey", "architecture_journey.index", "compass"),
        _link("Solutions", "solution_design.list_solutions", "wrench"),
        _link("AI Chat", "unified_ai_chat.index", "message-square"),
        _link("ADM Kanban", "adm_kanban_view.index", "kanban"),
        # Fix round: Programmes was reachable from nowhere in the sidebar.
        _link("Programmes", "solution_design.programmes_list", "git-merge"),
    ],
    ROLE_ENTERPRISE_ARCHITECT: [
        # BA-A3 (21 Aug 2026): the /business-architecture landing page is
        # deliberately NOT here. enterprise_architect renders 26 sidebar links,
        # which is the `sidebar_links` ratchet's baseline exactly — adding a
        # 27th trips the gate, and raising a ratchet is a regression, not a
        # cleanup. The page is not lost to this persona: EA's zones already
        # carry Capability Map, Gap Analysis, Work Packages, Traceability
        # Matrix, Capability Health, Roadmaps and Data Architecture directly,
        # which is most of what the landing page fronts, and platform_admin —
        # the default enterprise_role for any user who never picked one — does
        # carry the link. Give EA this link only in the same change that
        # retires one of its existing 13 My-work links.
        _link("Portfolio", "portfolio.index", "layout-dashboard"),
        _link("Capability Map", "capability_map.index", "map"),
        _link("Elements", "archimate_crud.dashboard", "table"),
        _link("Roadmaps", "main.capability_roadmap", "map"),
        # Fix round: both were reachable from nowhere in the sidebar.
        _link("ArchiMate Composer", "archimate.composer_page", "pen-tool"),
        _link("Traceability Matrix", "architect_ui.traceability_matrix", "git-branch"),
        # S-11: both are real, working Implementation & Migration pages that
        # were reachable from nowhere in the sidebar. Gap Analysis here is
        # `enterprise.gap_analysis` (the ArchiMate `Gap` register), not
        # `adm_kanban_view.gap_analysis` (KanbanCard rows on the ADM board,
        # already linked from that board). Work Packages is an Alpine table
        # over /enterprise/api/work-packages.
        _link("Gap Analysis", "enterprise.gap_analysis", "git-compare"),
        _link("Work Packages", "enterprise.work_packages", "package"),
        # S-11 remainder (18 Aug 2026, QA Update 6/8): these three were
        # directory-only — reachable from /modules/ but from no sidebar zone
        # of any role. All three are EA-shaped working pages.
        _link("Impact Analysis", "strategic.impact_analysis", "git-branch"),
        _link("Capability Health", "strategic.capability_health", "heart-pulse"),
        _link("Duplicate Detection", "unified_duplicate.simple_dashboard", "copy"),
        # ARCH-123 / ARCH-124 (QA register closure, 18 Aug 2026): the Data
        # Architect and Technical Architect personas the register flagged as
        # underserved are folded into enterprise_architect here — there is no
        # dedicated role for either yet. Data Architecture already existed
        # (models + dashboard) but was reachable from nowhere in the
        # sidebar; Tech Radar is new. Both are now linked.
        _link("Data Architecture", "data_architecture.data_architecture_dashboard", "workflow"),
        _link("Tech Radar", "tech_radar.index", "radar"),
    ],
    ROLE_CTO: [
        _link("Health Scorecard", "dashboard.health_scorecard", "heart-pulse"),
        _link("Rationalization", "unified_applications.rationalization_dashboard", "git-merge"),
        _link("Investment Analysis", "architecture.investment_priorities", "target"),
    ],
    ROLE_BUSINESS_ARCHITECT: [
        # BA-A1/A2. This persona had 4 links against a budget of 27 while
        # enterprise_architect had 13, so most of what a business architect
        # needs existed and was reachable only by typing a URL. An evaluating
        # architect concluded outright that capability maturity, gap analysis
        # and strategy-to-execution were not built. They are; 350 routes serve
        # them. Nothing below is a new page — every endpoint already ships and
        # is already in another persona's zones.
        #
        # BA-A3. The front door, deliberately first: the persona's problem was
        # never that a page was missing, it was that twelve outputs were spread
        # over five generic zones with no page that presents them as one
        # practice. /business-architecture is that page.
        _link("Business Architecture", "business_architecture.index", "compass"),
        _link("Capability Map", "capability_map.index", "map"),
        # Points at the heatmap, NOT frameworks_overview. That was the only
        # maturity link this persona had, it is labelled "Frameworks" rather
        # than "Maturity", and it lands on the one maturity page that renders
        # near-empty (the framework taxonomy does not match the categories the
        # data actually carries — BA-12). Clicking the single maturity link and
        # finding nothing is precisely why maturity was reported as missing.
        _link("Capability Maturity", "maturity_management.maturity_heatmap", "thermometer"),
        # Kept alongside the heatmap, not replaced by it. A QA finding pins
        # frameworks_overview as needing a sidebar zone, and repointing this
        # persona's only maturity link at the heatmap had quietly removed it
        # from every zone — trading one discoverability defect for another.
        _link("Capability Frameworks", "maturity_management.frameworks_overview", "layers"),
        _link("Value Streams", "value_stream.index", "waypoints"),
        _link("Stakeholder Map", "stakeholder_map.stakeholder_map_page", "users"),
        _link("Gap Analysis", "enterprise.gap_analysis", "search-x"),
        _link("Roadmaps", "main.capability_roadmap", "milestone"),
        _link("Work Packages", "enterprise.work_packages", "package"),
        _link("Traceability Matrix", "architect_ui.traceability_matrix", "git-compare"),
        _link("Capability Health", "strategic.capability_health", "activity"),
        _link("Data Architecture", "data_architecture.data_architecture_dashboard", "database"),
    ],
    ROLE_PORTFOLIO_MANAGER: [
        # S-11 / ARCH-122: /portfolio/ is a complete programme-management
        # module (initiative, phase, RAG health, budget/spend/variance,
        # completion, benefits, sponsor) that the portfolio_manager persona —
        # the one whose whole job it is — had no sidebar link to. It is
        # already in the enterprise_architect / arb_member / platform_admin
        # zones; this is the missing one.
        _link("Portfolio", "portfolio.index", "layout-dashboard"),
        _link("Rationalization", "unified_applications.rationalization_dashboard", "git-merge"),
        _link("Vendors", "unified_applications.vendors", "building"),
        _link("Applications", "unified_applications.application_list", "list"),
        # S-11 remainder: directory-only, never in a sidebar zone.
        _link("Consolidation List", "consolidation_list.dashboard", "layers"),
    ],
    ROLE_PROCUREMENT: [
        # Fix round: Overview, Licences and Compliance were reachable from
        # nowhere in the sidebar despite having working, guarded routes.
        _link("Overview", "procurement.index", "shopping-cart"),
        _link("Vendors", "unified_applications.vendors", "building"),
        _link("Contracts", "procurement.contracts_list", "file-text"),
        _link("Renewals", "procurement.renewals_dashboard", "history"),
        _link("Spend", "procurement.spend_analytics", "bar-chart-3"),
        _link("Licences", "procurement.licenses_list", "key-round"),
        _link("Compliance", "procurement.compliance_dashboard", "clipboard-check"),
    ],
    ROLE_APPLICATION_MANAGER: [
        # Fix round: my_applications.dashboard is a personally-scoped view
        # (ApplicationOwner rows for current_user only — see
        # app/modules/my_applications/routes.py:get_owned_apps) distinct from
        # unified_applications.application_list's org-wide paginated list; it
        # was reachable from nowhere in the sidebar.
        _link("My Applications", "my_applications.dashboard", "layout-dashboard"),
        _link("Applications", "unified_applications.application_list", "list"),
        _link("Rationalization", "unified_applications.rationalization_dashboard", "git-merge"),
        _link("Vendors", "unified_applications.vendors", "building"),
    ],
    # Not enumerated in the spec's My-work column; ARB member's primary work
    # is governance review, backed by its own zone below. My work here mirrors
    # its existing legacy ROLE_SECTION_ACCESS scope (solutions, portfolio).
    ROLE_ARB_MEMBER: [
        _link("Solutions", "solution_design.list_solutions", "wrench"),
        _link("Portfolio", "portfolio.index", "layout-dashboard"),
    ],
    # Also not enumerated in the spec; platform_admin gets a working set that
    # mirrors its legacy full-access scope, distinct from the Admin zone below.
    # Fix round (evidence review): "Applications" used to be listed here too,
    # pointing at unified_applications.application_list — the exact same
    # endpoint already listed under Library (_LIBRARY_LINKS above), so
    # platform_admin saw the identical "Applications" label twice. Library's
    # copy is the one every other role gets, so it stays; this duplicate is
    # dropped rather than relabelled, since there is no second, distinct view
    # to relabel it as.
    ROLE_PLATFORM_ADMIN: [
        _link("Solutions", "solution_design.list_solutions", "wrench"),
        _link("Portfolio", "portfolio.index", "layout-dashboard"),
        # BA-A3. platform_admin is the default enterprise_role for every user
        # who has not picked one during onboarding (see the column comment in
        # app/models/user.py), so a page that exists only for the two architect
        # roles is invisible to most real accounts. Rendered total for this
        # role goes 25 -> 26, still under SIDEBAR_LINK_BUDGET (27).
        _link("Business Architecture", "business_architecture.index", "compass"),
    ],
}

_BOARD_ROLES = {
    ROLE_ENTERPRISE_ARCHITECT,
    ROLE_ARB_MEMBER,
    ROLE_CTO,
    ROLE_PLATFORM_ADMIN,
}


def _build_zones(role: str) -> List[Dict]:
    # platform_admin has no headroom left for a 5th library link once its two
    # admin-zone additions are counted (23 zone links -> 25 rendered, exactly
    # at SIDEBAR_LINK_BUDGET) — see _LIBRARY_LINKS_WITH_DIRECTORY's comment.
    library_links = (
        _LIBRARY_LINKS if role == ROLE_PLATFORM_ADMIN else _LIBRARY_LINKS_WITH_DIRECTORY
    )
    zones = [
        _zone("home", _HOME_LINKS),
        _zone("my_work", _MY_WORK_LINKS[role]),
        _zone("library", library_links),
    ]
    if role in _BOARD_ROLES:
        zones.append(_zone("governance", _GOVERNANCE_LINKS))
    if role == ROLE_PLATFORM_ADMIN:
        zones.append(_zone("admin", _ADMIN_LINKS))
    return zones


# role -> ordered zones. Built once at import time; zone dicts are shared
# (read-only) across roles where content is identical (home/library).
SIDEBAR_ZONES: Dict[str, List[Dict]] = {
    role: _build_zones(role) for role in _MY_WORK_LINKS
}


def get_sidebar_zones(user) -> List[Dict]:
    """Resolve the current user's role and return their ordered sidebar zones.

    Must never raise for the same reason as get_user_role: this renders on
    every authenticated page. Falls back to the default role's zones for an
    unrecognized/legacy role value.

    The "admin" zone is filtered per-request on the real `is_platform_admin`
    boolean (defaults False, purpose-built for this), not on the cached
    per-role lookup above — `enterprise_role` (which selects that lookup)
    defaults to the string "platform_admin" for EVERY user for backward
    compatibility (see the column comment in app/models/user.py), so keying
    zone visibility off it alone showed the whole Admin section, full of
    routes guarded by a completely different check, to ordinary users who
    haven't explicitly picked a role during onboarding. Most of those routes
    correctly 403 them anyway (admin_required checks the Administrator role,
    unaffected by this), but /admin/organizations is guarded by
    platform_admin_required — the one route where this default actually
    controls data access, not just link visibility.
    """
    role = get_user_role(user)
    zones = SIDEBAR_ZONES.get(role, SIDEBAR_ZONES[DEFAULT_ROLE])
    if not getattr(user, "is_platform_admin", False):
        zones = [z for z in zones if z["zone"] != "admin"]
    return zones


# Context processor for templates
def role_access_context_processor():
    """
    Provide role access functions to Jinja2 templates.

    Usage in template:
        {% if can_access_section(current_user, 'administration') %}
    """
    return {
        "can_access_section": can_access_section,
        "get_visible_sections": get_visible_sections,
        "is_admin": is_admin,
        "is_procurement": is_procurement,
        "is_application_manager": is_application_manager,
        "get_role_display_name": get_role_display_name,
    }
