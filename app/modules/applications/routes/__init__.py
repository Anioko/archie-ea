"""
Applications routes -- decomposed from unified_applications_routes.py (10,736 lines).

The ``unified_applications_bp`` Blueprint is defined here and shared across all
sub-modules.  Each sub-module imports it and registers its routes.

Sub-modules:
- list_views:                    List/dashboard/table views (6 routes)
- crud_routes:                   Create, detail, edit, delete, bulk ops (8 routes)
- update_routes:                 CSRF-exempt AJAX updates (5 routes)
- vendor_display_routes:         Vendor list, create, detail pages (3 routes)
- import_export_routes:          Import page, AI review, export CSV (8 routes)
- import_sophisticated_routes:   Sophisticated import modal (8 routes)
- document_routes:               Document upload/download/delete, capability mapping (6 routes)
- vendor_api_routes:             Vendor matching, analysis, dashboard APIs (15 routes)
- element_routes:                ArchiMate element addition (16 routes)
- auto_mapping_routes:           Semantic linking, APQC enrichment, auto-map (8 routes)
- rationalization_api_routes:    Rationalization dashboard, element CRUD, templates (15 routes)
"""

from flask import Blueprint

unified_applications_bp = Blueprint(
    "unified_applications", __name__, url_prefix="/applications"
)

# Mark as guardrailed BEFORE routes are registered
from app.core.compat import mark_blueprint_guardrailed
mark_blueprint_guardrailed(unified_applications_bp)

# Import sub-modules to register their routes on the shared blueprint.
from . import (  # noqa: F401, E402
    auto_mapping_routes,
    crud_routes,
    document_routes,
    element_routes,
    import_export_routes,
    import_sophisticated_routes,
    list_views,
    rationalization_api_routes,
    update_routes,
    vendor_api_routes,
    vendor_display_routes,
)
