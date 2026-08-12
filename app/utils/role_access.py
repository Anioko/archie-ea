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

SIDEBAR_LINK_BUDGET = 25

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
        _link("Portfolio", "portfolio.index", "layout-dashboard"),
        _link("Capability Map", "capability_map.index", "map"),
        _link("Elements", "archimate_crud.dashboard", "table"),
        _link("Roadmaps", "main.capability_roadmap", "map"),
        # Fix round: both were reachable from nowhere in the sidebar.
        _link("ArchiMate Composer", "archimate.composer_page", "pen-tool"),
        _link("Traceability Matrix", "architect_ui.traceability_matrix", "git-branch"),
    ],
    ROLE_CTO: [
        _link("Health Scorecard", "dashboard.health_scorecard", "heart-pulse"),
        _link("Rationalization", "unified_applications.rationalization_dashboard", "git-merge"),
        _link("Investment Analysis", "architecture.investment_priorities", "target"),
    ],
    ROLE_BUSINESS_ARCHITECT: [
        # The five surfaces this persona exists for. The sidebar became
        # data-driven in the shell rework while these modules were being built
        # on another branch, so the merge left every one of them reachable only
        # by typing its URL — including value streams and the business model
        # canvas, which predate both branches. A zone filters out any link whose
        # endpoint is unregistered, so listing them here is safe even where a
        # blueprint failed to register.
        _link("Capability Map", "capability_map.index", "map"),
        _link("Import a Model", "capability_map.import_page", "upload"),
        _link("Value Streams", "value_stream.index", "waypoints"),
        _link("Customer Journeys", "customer_journey.index", "route"),
        _link("Information Model", "information_model.index", "database"),
        _link("Business Model Canvas", "business_model.index", "layout-dashboard"),
    ],
    ROLE_PORTFOLIO_MANAGER: [
        _link("Rationalization", "unified_applications.rationalization_dashboard", "git-merge"),
        _link("Vendors", "unified_applications.vendors", "building"),
        _link("Applications", "unified_applications.application_list", "list"),
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
    """
    role = get_user_role(user)
    return SIDEBAR_ZONES.get(role, SIDEBAR_ZONES[DEFAULT_ROLE])


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
