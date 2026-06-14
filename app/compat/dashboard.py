"""
Compatibility wrappers for the dashboard module (legacy -> v2).

Feature-flag gating: USE_DASHBOARD_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.mapping_registry import register_routes
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("dashboard")


class DashboardCompatStats(CompatStats):
    """Thread-safe hit counter for legacy dashboard endpoints."""

    pass


LEGACY_ROUTE_MAP = {
    # dashboard blueprint (17 routes, url_prefix=/dashboard)
    "dashboard.index": {"url": "/dashboard/", "v2": "dashboard.index", "method": "GET"},
    "dashboard.overview": {
        "url": "/dashboard/dashboards/overview",
        "v2": "dashboard.overview",
        "method": "GET",
    },
    "dashboard.operations": {
        "url": "/dashboard/dashboards/operations",
        "v2": "dashboard.operations",
        "method": "GET",
    },
    "dashboard.api_overview_chart": {
        "url": "/dashboard/dashboards/api/overview/chart",
        "v2": "dashboard.api_overview_chart",
        "method": "GET",
    },
    "dashboard.api_overview_table": {
        "url": "/dashboard/dashboards/api/operations/table",
        "v2": "dashboard.api_overview_table",
        "method": "GET",
    },
    "dashboard.api_operations_chart": {
        "url": "/dashboard/dashboards/api/operations/chart",
        "v2": "dashboard.api_operations_chart",
        "method": "GET",
    },
    "dashboard.api_operations_table": {
        "url": "/dashboard/dashboards/api/operations/table",
        "v2": "dashboard.api_operations_table",
        "method": "GET",
    },
    "dashboard.api_colvis": {
        "url": "/dashboard/dashboard/api/colvis",
        "v2": "dashboard.api_colvis",
        "method": "GET,POST",
    },
    "dashboard.api_colorder": {
        "url": "/dashboard/dashboard/api/colorder",
        "v2": "dashboard.api_colorder",
        "method": "GET,POST",
    },
    "dashboard.api_sort": {
        "url": "/dashboard/dashboard/api/sort",
        "v2": "dashboard.api_sort",
        "method": "GET,POST",
    },
    "dashboard.api_edit": {
        "url": "/dashboard/dashboard/api/edit",
        "v2": "dashboard.api_edit",
        "method": "POST",
    },
    "dashboard.api_filters": {
        "url": "/dashboard/dashboard/api/filters",
        "v2": "dashboard.api_filters",
        "method": "GET,POST",
    },
    "dashboard.api_tab": {
        "url": "/dashboard/dashboard/api/tab",
        "v2": "dashboard.api_tab",
        "method": "GET,POST",
    },
    "dashboard.api_duplicate": {
        "url": "/dashboard/dashboard/api/duplicate",
        "v2": "dashboard.api_duplicate",
        "method": "POST",
    },
    "dashboard.api_delete": {
        "url": "/dashboard/dashboard/api/delete",
        "v2": "dashboard.api_delete",
        "method": "POST",
    },
    "dashboard.api_bulk_delete": {
        "url": "/dashboard/dashboard/api/bulk-delete",
        "v2": "dashboard.api_bulk_delete",
        "method": "POST",
    },
    "dashboard.api_table_get": {
        "url": "/dashboard/dashboard/api/table/<table_name>",
        "v2": "dashboard.api_table_get",
        "method": "GET",
    },
    # dashboard_pages blueprint (40 routes, url_prefix=/dashboard)
    "dashboard_pages.api_capability_heatmap": {
        "url": "/dashboard/api/capability-heatmap",
        "v2": "dashboard_pages.api_capability_heatmap",
        "method": "GET",
    },
    "dashboard_pages.review_queue": {
        "url": "/dashboard/review-queue",
        "v2": "dashboard_pages.review_queue",
        "method": "GET",
    },
    # dashboard_pages.apqc_browser removed — zero backend API
    "dashboard_pages.import_history": {
        "url": "/dashboard/import-history",
        "v2": "dashboard_pages.import_history",
        "method": "GET",
    },
    # dashboard_pages.vendor_catalog removed — redundant with /vendors/
    "dashboard_pages.rationalization_dashboard": {
        "url": "/dashboard/rationalization",
        "v2": "dashboard_pages.rationalization_dashboard",
        "method": "GET",
    },
    "dashboard_pages.governance_dashboard": {
        "url": "/dashboard/governance",
        "v2": "dashboard_pages.governance_dashboard",
        "method": "GET",
    },
    # dashboard_pages.vendor_risk_dashboard removed — niche
    "dashboard_pages.consolidation_dashboard": {
        "url": "/dashboard/consolidation",
        "v2": "dashboard_pages.consolidation_dashboard",
        "method": "GET",
    },
    "dashboard_pages.rationalization_assessment": {
        "url": "/dashboard/rationalization/assessment",
        "v2": "dashboard_pages.rationalization_assessment",
        "method": "GET",
    },
    "dashboard_pages.rationalization_scorecard": {
        "url": "/dashboard/rationalization/scorecard",
        "v2": "dashboard_pages.rationalization_scorecard",
        "method": "GET",
    },
    "dashboard_pages.rationalization_onboard": {
        "url": "/dashboard/rationalization/onboard",
        "v2": "dashboard_pages.rationalization_onboard",
        "method": "GET",
    },
    "dashboard_pages.response_validation": {
        "url": "/dashboard/rationalization/validate",
        "v2": "dashboard_pages.response_validation",
        "method": "GET",
    },
}

register_routes("dashboard", LEGACY_ROUTE_MAP)

wrap_legacy_dashboard_bp = make_legacy_wrapper(_config, DashboardCompatStats)
wrap_legacy_dashboard_pages_bp = make_legacy_wrapper(_config, DashboardCompatStats)
