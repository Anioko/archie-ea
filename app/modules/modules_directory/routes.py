"""All-modules directory route.

GET /modules — the sidebar diet's long-tail answer. Every link from every
role's SIDEBAR_ZONES (app/utils/role_access.py), deduplicated and grouped by
zone, plus a curated "More tools" section for real, working routes that were
never assigned to any persona's zone at all (surfaced by the shell-overhaul
Wave 1 review). Every link is guarded by the same
`endpoint in flask.current_app.view_functions` check the sidebar uses, so a
non-fatally-failed blueprint degrades one row here instead of a BuildError.

Two rules keep the page honest, both added 30 Aug 2026 after every advertised
destination was requested with a logged-in client:

* a row is only rendered if the current user could actually open it — the page
  unions EVERY role's zones, which previously showed an enterprise_architect 19
  admin/procurement/my-applications links that return a hard 403;
* a row is only rendered if its destination is a real, distinct page —
  `_NOT_RENDERED` drops one permanently-404 deprecated module and four 302
  aliases whose labels promised a module the user had already been offered
  under its real name.
"""

from flask import current_app, render_template, url_for
from flask_login import current_user, login_required

from app.utils.role_access import _ZONE_TITLES, SIDEBAR_ZONES, can_access_section

from . import modules_directory_bp

# Endpoint-prefix -> the EXCLUSIVE_SECTIONS key that gates it (role_access.py).
# This page unions EVERY role's SIDEBAR_ZONES, so without this filter it
# advertised the procurement, my-applications and admin surfaces to every
# persona. Measured: an enterprise_architect was shown 19 links that return a
# hard 403 - a directory of dead buttons. get_sidebar_zones() already drops the
# admin zone on the real `is_platform_admin` boolean for exactly this reason;
# that guard was simply never carried across to this page.
_SECTION_BY_ENDPOINT_PREFIX = {
    "admin.": "administration",
    "procurement.": "procurement",
    "my_applications.": "my_applications",
}


def _link_visible(endpoint: str) -> bool:
    """False when `endpoint` belongs to a role-exclusive section this user has
    no access to, so the directory never renders a guaranteed-403 link."""
    if endpoint in _NOT_RENDERED:
        return False
    for prefix, section in _SECTION_BY_ENDPOINT_PREFIX.items():
        if endpoint.startswith(prefix):
            if section == "administration":
                # Mirror get_sidebar_zones(): /admin/organizations is guarded by
                # platform_admin_required, and `enterprise_role` defaults to the
                # string "platform_admin" for every user, so the role lookup
                # alone would let it through.
                return bool(getattr(current_user, "is_platform_admin", False))
            return can_access_section(current_user, section)
    return True


# Real, working routes with no home in any persona's SIDEBAR_ZONES — enumerated
# by the shell-overhaul Wave 1 review. Not the ~50 /architecture/<layer>/<type>
# drill-downs (those are covered by the single "ArchiMate Elements" library
# link) — see the review comment on scripts task-3 fix round.
_MORE_TOOLS = [
    ("Stakeholder Map", "stakeholder_map.stakeholder_map_page", "users"),
    ("Capability Health", "strategic.capability_health", "heart-pulse"),
    ("Impact Analysis", "strategic.impact_analysis", "target"),
    ("Maturity Frameworks", "maturity_management.frameworks_overview", "trending-up"),
    ("Batch Import", "batch_import_view.dashboard", "upload"),
    ("Consolidation List", "consolidation_list.dashboard", "combine"),
    ("Duplicate Detection", "unified_duplicate.simple_dashboard", "copy"),
    ("EA Briefings", "solution_design.ea_briefings", "newspaper"),
    ("Data Stewardship", "solution_design.data_stewardship", "database"),
    ("Chief Architect Synthesis", "solution_design.architect_synthesis", "layout-dashboard"),
    # Hidden from this list on 30 Aug 2026 after every entry was requested with
    # a logged-in client and its status recorded:
    #   implementation_planning.implementation_dashboard - 404 for everyone. Its
    #     blueprint's before_request aborts 404 unless a feature flag row exists
    #     AND is active, and the module is marked DEPRECATED in its own
    #     docstring. "Work Packages" (enterprise.work_packages) is the live
    #     surface and is already listed.
    #   main.capability_framework.dashboard - 302 to /framework-management/,
    #     already listed as "Framework Management".
    #   dashboard.index - 302 to /dashboard/overview, already a Home zone link.
    #   unified_duplicate.enterprise_dashboard - 302 to
    #     /duplicate-detection/simple, already listed as "Duplicate Detection".
    #   architect_ui.roadmap_builder - 302 to /capability-roadmap, already a
    #     zone link ("Roadmaps").
    # A row whose label promises a distinct module and lands on another row in
    # the same list is the navigation equivalent of fabricated data: the user
    # cannot tell it apart from a real destination.
    #
    # They stay in this list rather than being deleted, because
    # tests/test_module_discoverability.py scans the url_map for module roots
    # and requires each to be known here — deleting them would report five
    # brand-new "orphan modules" that are not orphans. `_NOT_RENDERED` below is
    # what keeps them out of the page and out of global search.
    ("Implementation Planning", "implementation_planning.implementation_dashboard", "package"),
    ("Capability Framework", "main.capability_framework.dashboard", "map"),
    ("Dashboard", "dashboard.index", "layout-dashboard"),
    ("Duplicate Detection — Enterprise", "unified_duplicate.enterprise_dashboard", "copy"),
    ("Roadmap Builder", "architect_ui.roadmap_builder", "map"),
    ("My Applications — My List", "my_applications.app_list", "list"),
    ("My Applications — Health", "my_applications.health_overview", "heart-pulse"),
    ("My Applications — Roadmap Impact", "my_applications.roadmap_impact", "git-branch"),
    # S-11 follow-on (18 Aug 2026, this pass): a full url_map scan for
    # zero-argument GET module roots — the same shape as the original 25 —
    # turned up 25 more real, working, never-linked pages that the S-11
    # register's spot check did not reach either. Every one 200s and is not
    # a redirect (see tests/test_module_discoverability.py, which excludes
    # endpoints containing "redirect" and true infra routes like
    # favicon/robots/health/apidocs automatically rather than by this list).
    # Added here rather than triaged individually against a persona zone —
    # this file is exactly the designed overflow valve for "real route, no
    # natural zone owner yet" per its own module docstring.
    ("Agentic Gaps", "main.agentic_gaps_ui", "search"),
    ("Application Management", "application_management", "layout-dashboard"),
    ("Architecture Assistant", "architect_ui.architecture_assistant", "bot"),
    ("Model Registry", "dynamic_dashboards.model_registry_index", "database"),
    ("Business Case", "business_case.index", "briefcase"),
    ("Business Model", "business_model.index", "layout-dashboard"),
    ("EA Workflows", "main.ea_workflows_dashboard", "git-merge"),
    ("Framework Config", "framework_config_ui.framework_config_dashboard", "settings"),
    ("Framework Management", "main.framework_management.dashboard", "settings"),
    ("Hybrid Mapping Dashboard", "main.hybrid_mapping_dashboard", "map"),
    ("Industry APQC", "industry_apqc.industry_apqc_dashboard", "layers"),
    ("Integration Workflows", "integration.workflow_dashboard", "git-branch"),
    ("Market Intelligence", "architect_ui.market_intelligence", "trending-up"),
    ("Organization", "organization.index", "building-2"),
    ("Policy Monitoring", "policy_monitoring.policy_dashboard", "shield-check"),
    ("Product Roadmap", "roadmap_outcome.product_roadmap_page", "map"),
    ("Risk Register", "risk.risk_register", "alert-triangle"),
    ("Usage Analytics", "usage_analytics.analytics_root", "bar-chart-3"),
    ("Vendor ArchiMate Analysis", "main.vendor_archimate_analysis", "building"),
    ("Integrations", "main.integrations", "cloud"),
    ("ArchiMate Roadmap", "main.archimate_roadmap", "map"),
    ("Enterprise Dashboard", "enterprise.enterprise_dashboard", "layout-dashboard"),
]

# Endpoints present in _MORE_TOOLS / SIDEBAR_ZONES that must never be rendered
# as a directory row or returned as a search hit. Each was requested with a
# logged-in client on 30 Aug 2026 and its status recorded; the reason is the
# measurement, not a guess. tests/test_modules_directory.py re-measures every
# one of them, so an entry that becomes live again fails the suite instead of
# staying invisible.
_NOT_RENDERED = {
    # Hard 404 for every user: the blueprint's before_request aborts unless a
    # feature-flag row exists AND is active, and the module's own docstring
    # says DEPRECATED. "Work Packages" (enterprise.work_packages) is live.
    "implementation_planning.implementation_dashboard": "404 - deprecated module",
    # 302 aliases onto a page this directory already lists under its own name.
    "main.capability_framework.dashboard": "302 -> Framework Management",
    "dashboard.index": "302 -> Dashboard Overview",
    "unified_duplicate.enterprise_dashboard": "302 -> Duplicate Detection",
    "architect_ui.roadmap_builder": "302 -> Roadmaps",
}

_ZONE_ORDER = ["home", "my_work", "library", "governance", "admin"]


def all_module_links():
    """Every link this app knows how to point at: every role's SIDEBAR_ZONES
    plus the curated _MORE_TOOLS list, deduplicated by endpoint. Single
    source of truth for both this directory page and global search (P-10:
    search indexed none of the modules that live only here or in a zone) —
    a module added to either list becomes searchable automatically instead
    of needing a third hand-maintained list.
    """
    seen: dict[str, dict] = {}
    for zones in SIDEBAR_ZONES.values():
        for zone in zones:
            for link in zone["links"]:
                seen.setdefault(link["endpoint"], link)
    for label, endpoint, icon in _MORE_TOOLS:
        seen.setdefault(endpoint, {"label": label, "endpoint": endpoint, "icon": icon})
    return list(seen.values())


def visible_module_links():
    """`all_module_links()` minus anything the *current* user is structurally
    barred from (role-exclusive sections). Global search must use this, not
    `all_module_links()`: a result that 403s on click is a dead result."""
    return [link for link in all_module_links() if _link_visible(link["endpoint"])]


def _grouped_zone_sections():
    """Union every role's SIDEBAR_ZONES, deduplicated by endpoint within each
    zone kind, in a stable role-iteration order (dict insertion order, which
    for SIDEBAR_ZONES is the order roles were defined in role_access.py)."""
    buckets: dict[str, dict[str, dict]] = {key: {} for key in _ZONE_ORDER}

    # The "admin" zone is dropped wholesale for non-platform-admins, exactly as
    # get_sidebar_zones() does. Per-endpoint prefix matching is not enough: the
    # zone also carries `main.settings`, whose /settings route 403s every other
    # persona despite the endpoint not being namespaced under `admin.`.
    show_admin_zone = bool(getattr(current_user, "is_platform_admin", False))

    for zones in SIDEBAR_ZONES.values():
        for zone in zones:
            if zone["zone"] == "admin" and not show_admin_zone:
                continue
            bucket = buckets.setdefault(zone["zone"], {})
            for link in zone["links"]:
                if not _link_visible(link["endpoint"]):
                    continue
                bucket.setdefault(link["endpoint"], link)

    sections = []
    for key in _ZONE_ORDER:
        links = sorted(buckets.get(key, {}).values(), key=lambda link: link["label"])
        if links:
            sections.append({"title": _ZONE_TITLES.get(key, key.title()), "links": links})
    return sections


def _resolve(links):
    """Attach a real URL to each link, dropping any that cannot be built.

    The template used to call `url_for(link.endpoint)` itself behind an
    `endpoint in view_functions` guard. That guard is not sufficient: a
    registered endpoint whose rule takes a required parameter still raises
    BuildError, which 500s this entire page rather than one row. Resolving
    here, per link, in a try/except, makes a bad entry cost exactly one row.
    """
    resolved = []
    for link in links:
        if link["endpoint"] not in current_app.view_functions:
            continue
        try:
            href = url_for(link["endpoint"])
        except Exception:
            current_app.logger.warning(
                "modules directory: cannot build URL for %s - row omitted",
                link["endpoint"],
            )
            continue
        resolved.append({**link, "href": href})
    return resolved


@modules_directory_bp.route("/", strict_slashes=False)
@login_required
def index():
    sections = []
    for section in _grouped_zone_sections():
        links = _resolve(section["links"])
        if links:
            sections.append({"title": section["title"], "links": links})

    more_tools = _resolve(
        {"label": label, "endpoint": endpoint, "icon": icon}
        for label, endpoint, icon in _MORE_TOOLS
        if _link_visible(endpoint)
    )
    total = sum(len(section["links"]) for section in sections) + len(more_tools)
    return render_template(
        "modules_directory/index.html",
        sections=sections,
        more_tools=more_tools,
        total_count=total,
    )
