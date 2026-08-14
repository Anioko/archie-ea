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
]

_ZONE_ORDER = ["home", "my_work", "library", "governance", "admin"]


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
