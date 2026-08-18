"""All-modules directory route.

GET /modules — the sidebar diet's long-tail answer. Every link from every
role's SIDEBAR_ZONES (app/utils/role_access.py), deduplicated and grouped by
zone, plus a curated "More tools" section for real, working routes that were
never assigned to any persona's zone at all (surfaced by the shell-overhaul
Wave 1 review). Every link is guarded by the same
`endpoint in flask.current_app.view_functions` check the sidebar uses, so a
non-fatally-failed blueprint degrades one row here instead of a BuildError.
"""

from flask import render_template
from flask_login import login_required

from app.utils.role_access import _ZONE_TITLES, SIDEBAR_ZONES

from . import modules_directory_bp

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
    ("Capability Framework", "main.capability_framework.dashboard", "map"),
    ("Dashboard", "dashboard.index", "layout-dashboard"),
    ("Duplicate Detection — Enterprise", "unified_duplicate.enterprise_dashboard", "copy"),
    ("EA Workflows", "main.ea_workflows_dashboard", "git-merge"),
    ("Framework Config", "framework_config_ui.framework_config_dashboard", "settings"),
    ("Framework Management", "main.framework_management.dashboard", "settings"),
    ("Hybrid Mapping Dashboard", "main.hybrid_mapping_dashboard", "map"),
    ("Implementation Planning", "implementation_planning.implementation_dashboard", "package"),
    ("Industry APQC", "industry_apqc.industry_apqc_dashboard", "layers"),
    ("Integration Workflows", "integration.workflow_dashboard", "git-branch"),
    ("Market Intelligence", "architect_ui.market_intelligence", "trending-up"),
    ("Organization", "organization.index", "building-2"),
    ("Policy Monitoring", "policy_monitoring.policy_dashboard", "shield-check"),
    ("Product Roadmap", "roadmap_outcome.product_roadmap_page", "map"),
    ("Risk Register", "risk.risk_register", "alert-triangle"),
    ("Roadmap Builder", "architect_ui.roadmap_builder", "map"),
    ("Usage Analytics", "usage_analytics.analytics_root", "bar-chart-3"),
    ("Vendor ArchiMate Analysis", "main.vendor_archimate_analysis", "building"),
    ("Integrations", "main.integrations", "cloud"),
    ("ArchiMate Roadmap", "main.archimate_roadmap", "map"),
    ("Enterprise Dashboard", "enterprise.enterprise_dashboard", "layout-dashboard"),
]

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


def _grouped_zone_sections():
    """Union every role's SIDEBAR_ZONES, deduplicated by endpoint within each
    zone kind, in a stable role-iteration order (dict insertion order, which
    for SIDEBAR_ZONES is the order roles were defined in role_access.py)."""
    buckets: dict[str, dict[str, dict]] = {key: {} for key in _ZONE_ORDER}

    for zones in SIDEBAR_ZONES.values():
        for zone in zones:
            bucket = buckets.setdefault(zone["zone"], {})
            for link in zone["links"]:
                bucket.setdefault(link["endpoint"], link)

    sections = []
    for key in _ZONE_ORDER:
        links = sorted(buckets.get(key, {}).values(), key=lambda link: link["label"])
        if links:
            sections.append({"title": _ZONE_TITLES.get(key, key.title()), "links": links})
    return sections


@modules_directory_bp.route("/", strict_slashes=False)
@login_required
def index():
    more_tools = [
        {"label": label, "endpoint": endpoint, "icon": icon}
        for label, endpoint, icon in _MORE_TOOLS
    ]
    return render_template(
        "modules_directory/index.html",
        sections=_grouped_zone_sections(),
        more_tools=more_tools,
    )
