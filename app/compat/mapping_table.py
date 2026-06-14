"""
Comprehensive legacy -> new endpoint mapping table.

Provides a programmatic registry of all legacy route files, their new module
locations, feature flags, and deprecation status. Used by:
- Migration dashboard for progress tracking
- Compat layer for automated redirect generation
- CI pipeline for migration-phase compliance

Usage::

    from app.compat.mapping_table import get_mapping_table, get_module_summary

    table = get_mapping_table()
    summary = get_module_summary()
"""

from typing import Any, Dict, List

# Each entry maps a legacy file to its new location and migration metadata.
# Fields:
#   legacy_file: path to the original route file
#   new_module: dotted path to the new module
#   new_file: path to the new route file within the module
#   feature_flag: environment variable controlling the switch
#   compat_flag: environment variable enabling compat wrappers
#   status: "migrated" | "deprecated" | "removed"

_MODULE_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "monitoring": {
        "feature_flag": "USE_NEW_MONITORING",
        "compat_flag": "USE_MONITORING_COMPAT",
        "new_module": "app.modules.monitoring",
        "route_count": 12,
        "legacy_files": [
            {"legacy": "app/routes/health_routes.py", "new": "app/modules/monitoring/routes/health_routes.py"},
            {"legacy": "app/routes/metrics_routes.py", "new": "app/modules/monitoring/routes/metrics_routes.py"},
        ],
    },
    "account": {
        "feature_flag": "USE_NEW_ACCOUNT",
        "compat_flag": "USE_ACCOUNT_COMPAT",
        "new_module": "app.modules.account",
        "route_count": 18,
        "legacy_files": [
            {"legacy": "app/account/views.py", "new": "app/modules/account/routes/account_routes.py"},
            {"legacy": "app/account/forms.py", "new": "app/modules/account/forms/account_forms.py"},
        ],
    },
    "admin": {
        "feature_flag": "USE_NEW_ADMIN",
        "compat_flag": "USE_ADMIN_COMPAT",
        "new_module": "app.modules.admin",
        "route_count": 38,
        "legacy_files": [
            {"legacy": "app/admin/views.py", "new": "app/modules/admin/routes/admin_routes.py"},
            {"legacy": "app/admin/sidebar_mgmt_routes.py", "new": "app/modules/admin/routes/sidebar_mgmt_routes.py"},
        ],
    },
    "dashboard": {
        "feature_flag": "USE_NEW_DASHBOARD",
        "compat_flag": "USE_DASHBOARD_COMPAT",
        "new_module": "app.modules.dashboard",
        "route_count": 32,
        "legacy_files": [
            {"legacy": "app/dashboard/views.py", "new": "app/modules/dashboard/routes/dashboard_routes.py"},
            {"legacy": "app/dashboard/routes.py", "new": "app/modules/dashboard/routes/dashboard_routes.py"},
            {"legacy": "app/api/dashboard_routes.py", "new": "app/modules/dashboard/routes/dashboard_api.py"},
        ],
    },
    "vendors": {
        "feature_flag": "USE_NEW_VENDORS",
        "compat_flag": "USE_VENDORS_COMPAT",
        "new_module": "app.modules.vendors",
        "route_count": 166,
        "legacy_files": [
            {"legacy": "app/unified_vendors/", "new": "app/modules/vendors/routes/unified_vendor_views.py"},
            {"legacy": "app/api_vendors.py", "new": "app/modules/vendors/api/api_vendors.py"},
            {"legacy": "app/routes/vendor_management_routes.py", "new": "app/modules/vendors/routes/vendor_management_routes.py"},
            {"legacy": "app/routes/vendor_analysis_routes.py", "new": "app/modules/vendors/routes/vendor_analysis_routes.py"},
            {"legacy": "app/routes/vendor_comparison_routes.py", "new": "app/modules/vendors/routes/vendor_comparison_routes.py"},
            {"legacy": "app/routes/vendor_mdm_api.py", "new": "app/modules/vendors/routes/vendor_mdm_api.py"},
        ],
    },
    "duplicate_detection": {
        "feature_flag": "USE_NEW_DUPLICATE_DETECTION",
        "compat_flag": "USE_DEDUPE_COMPAT",
        "new_module": "app.modules.duplicate_detection",
        "route_count": 50,
        "legacy_files": [
            {"legacy": "app/routes/unified_duplicate_routes.py", "new": "app/modules/duplicate_detection/routes/unified_duplicate_routes.py"},
            {"legacy": "app/routes/ai_dedupe_routes.py", "new": "app/modules/duplicate_detection/routes/ai_dedupe_routes.py"},
            {"legacy": "app/routes/consolidation_list_routes.py", "new": "app/modules/duplicate_detection/routes/consolidation_list_routes.py"},
        ],
    },
    "import_batch": {
        "feature_flag": "USE_NEW_IMPORT_BATCH",
        "compat_flag": "USE_IMPORT_BATCH_COMPAT",
        "new_module": "app.modules.import_batch",
        "route_count": 80,
        "legacy_files": [
            {"legacy": "app/routes/batch_import_routes.py", "new": "app/modules/import_batch/routes/batch_import_routes.py"},
            {"legacy": "app/routes/batch_import_view_routes.py", "new": "app/modules/import_batch/routes/batch_import_view_routes.py"},
            {"legacy": "app/routes/unified_import_routes.py", "new": "app/modules/import_batch/routes/unified_import_routes.py"},
            {"legacy": "app/api/batch_processing_routes.py", "new": "app/modules/import_batch/routes/batch_processing_routes.py"},
        ],
    },
    "governance": {
        "feature_flag": "USE_NEW_GOVERNANCE",
        "compat_flag": "USE_GOVERNANCE_COMPAT",
        "new_module": "app.modules.governance",
        "route_count": 70,
        "legacy_files": [
            {"legacy": "app/routes/arb_routes.py", "new": "app/modules/governance/routes/arb_routes.py"},
            {"legacy": "app/routes/arb_workflow_routes.py", "new": "app/modules/governance/routes/arb_workflow_routes.py"},
            {"legacy": "app/routes/adm_kanban_routes.py", "new": "app/modules/governance/routes/adm_kanban_routes.py"},
            {"legacy": "app/routes/adm_kanban_view_routes.py", "new": "app/modules/governance/routes/adm_kanban_view_routes.py"},
        ],
    },
    "architecture": {
        "feature_flag": "USE_NEW_ARCHITECTURE",
        "compat_flag": "USE_ARCHITECTURE_COMPAT",
        "new_module": "app.modules.architecture",
        "route_count": 180,
        "legacy_files": [
            {"legacy": "app/routes/architecture_crud_routes.py", "new": "app/modules/architecture/routes/architecture_crud_routes.py"},
            {"legacy": "app/routes/architecture_routes.py", "new": "app/modules/architecture/routes/architecture_routes.py"},
            {"legacy": "app/routes/architecture_assistant_routes.py", "new": "app/modules/architecture/routes/architecture_assistant_routes.py"},
            {"legacy": "app/routes/archimate_export_routes.py", "new": "app/modules/architecture/routes/archimate_export_routes.py"},
            {"legacy": "app/routes/architect_ui_routes.py", "new": "app/modules/architecture/routes/architect_ui_routes.py"},
            {"legacy": "app/api/archimate_routes.py", "new": "app/modules/architecture/api/archimate_routes.py"},
            {"legacy": "app/api/viewpoint_routes.py", "new": "app/modules/architecture/api/viewpoint_routes.py"},
            {"legacy": "app/archimate_crud/", "new": "app/modules/architecture/routes/archimate_crud/"},
        ],
    },
    "capabilities": {
        "feature_flag": "USE_NEW_CAPABILITIES",
        "compat_flag": "USE_CAPABILITIES_COMPAT",
        "new_module": "app.modules.capabilities",
        "route_count": 200,
        "legacy_files": [
            {"legacy": "app/routes/capability_map_routes.py", "new": "app/modules/capabilities/routes/capability_map_routes.py"},
            {"legacy": "app/routes/capability_management_routes.py", "new": "app/modules/capabilities/routes/capability_management_routes.py"},
            {"legacy": "app/routes/capability_governance_routes.py", "new": "app/modules/capabilities/routes/capability_governance_routes.py"},
            {"legacy": "app/main/capability_maturity_routes.py", "new": "app/modules/capabilities/routes/capability_maturity_routes.py"},
            {"legacy": "app/api/capability_taxonomy_routes.py", "new": "app/modules/capabilities/routes/capability_taxonomy_routes.py"},
        ],
    },
    "ai_chat": {
        "feature_flag": "USE_NEW_AI_CHAT",
        "compat_flag": "USE_AI_CHAT_COMPAT",
        "new_module": "app.modules.ai_chat",
        "route_count": 100,
        "legacy_files": [
            {"legacy": "app/routes/unified_ai_chat_routes.py", "new": "app/modules/ai_chat/routes/chat_core.py"},
            {"legacy": "app/ai_chat/routes.py", "new": "app/modules/ai_chat/routes/chat_views.py"},
            {"legacy": "app/ai_chat/data_interaction_routes.py", "new": "app/modules/ai_chat/routes/data_interaction_routes.py"},
            {"legacy": "app/routes/ai_assistance_routes.py", "new": "app/modules/ai_chat/routes/ai_assistance_routes.py"},
        ],
    },
    "applications": {
        "feature_flag": "USE_NEW_APPLICATIONS",
        "compat_flag": "USE_APPLICATIONS_COMPAT",
        "new_module": "app.modules.applications",
        "route_count": 300,
        "legacy_files": [
            {"legacy": "app/application_mgmt/routes.py", "new": "app/modules/applications/routes/crud_routes.py"},
            {"legacy": "app/routes/unified_applications_routes.py", "new": "app/modules/applications/routes/list_views.py"},
            {"legacy": "app/routes/enterprise_crud_routes.py", "new": "app/modules/applications/routes/element_routes.py"},
        ],
    },
    "solutions_strategic": {
        "feature_flag": "USE_NEW_SOLUTIONS_STRATEGIC",
        "compat_flag": "USE_SOLUTIONS_STRATEGIC_COMPAT",
        "new_module": "app.modules.solutions_strategic",
        "route_count": 150,
        "legacy_files": [
            {"legacy": "app/routes/solution_design_routes.py", "new": "app/modules/solutions_strategic/routes/solution_design_routes.py"},
            {"legacy": "app/routes/solution_composer_routes.py", "new": "app/modules/solutions_strategic/routes/solution_composer_routes.py"},
            {"legacy": "app/routes/solution_architect_routes.py", "new": "app/modules/solutions_strategic/routes/solution_architect_routes.py"},
            {"legacy": "app/routes/strategic_routes.py", "new": "app/modules/solutions_strategic/routes/strategic_routes.py"},
            {"legacy": "app/routes/roadmap_builder_routes.py", "new": "app/modules/solutions_strategic/routes/roadmap_builder_routes.py"},
            {"legacy": "app/api/roadmap_api.py", "new": "app/modules/solutions_strategic/api/roadmap_api.py"},
        ],
    },
}


def get_mapping_table() -> Dict[str, Dict[str, Any]]:
    """Return the full legacy -> new endpoint mapping table."""
    return dict(_MODULE_MAPPINGS)


def get_module_summary() -> List[Dict[str, Any]]:
    """Return a summary list of all modules with key migration stats."""
    return [
        {
            "module": name,
            "feature_flag": info["feature_flag"],
            "compat_flag": info["compat_flag"],
            "new_module": info["new_module"],
            "route_count": info["route_count"],
            "legacy_file_count": len(info["legacy_files"]),
        }
        for name, info in _MODULE_MAPPINGS.items()
    ]


def get_total_routes() -> int:
    """Return total number of routes across all modules."""
    return sum(m["route_count"] for m in _MODULE_MAPPINGS.values())


def get_legacy_file_list() -> List[str]:
    """Return flat list of all legacy file paths."""
    files = []
    for info in _MODULE_MAPPINGS.values():
        for mapping in info["legacy_files"]:
            files.append(mapping["legacy"])
    return files


def get_new_file_list() -> List[str]:
    """Return flat list of all new module file paths."""
    files = []
    for info in _MODULE_MAPPINGS.values():
        for mapping in info["legacy_files"]:
            files.append(mapping["new"])
    return files
