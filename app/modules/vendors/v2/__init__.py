"""
Vendors v2 — Guardrail-enabled thin wrapper over v1 module.

Strangler Fig migration from app/modules/vendors/ (v1).
Applies mark_blueprint_guardrailed() to all 13 blueprints registered by the
v1 module, enabling guardrail detection (is_new_module() returns True) and
request-level timing via before_request/after_request hooks.

Individual @timed_route decorators can be added to specific routes later
during Phase 4 Feature Migration.

Feature flag: USE_VENDORS_V2
Fallback: v1 routes (unchanged)
Rollback: Set USE_VENDORS_V2=false → v1 routes take over instantly.
"""

import time

from flask import Flask, request


def register(app: Flask) -> None:
    """Register the vendors v2 module (guardrail-wrapped v1 blueprints)."""
    from app import csrf
    from app.core.compat import mark_blueprint_guardrailed

    # Import all V1 blueprints
    from app.modules.vendors.api.api_vendors import vendors_api_bp
    from app.modules.vendors.routes.vendor_analysis_routes import vendor_analysis_bp
    from app.modules.vendors.routes.vendor_mdm_api import vendor_mdm_bp
    from app.modules.vendors.routes.vendor_management_routes import vendor_management_bp
    from app.modules.vendors.routes.unified_vendor_views import unified_vendors_bp
    from app.modules.vendors.routes.unified_vendor_api import unified_vendors_api_bp

    # Mark all blueprints as guardrailed BEFORE registration
    blueprints = [
        unified_vendors_api_bp,  # must be first: claims GET /api/vendors/ before Flask-RESTX root
        vendors_api_bp,
        vendor_analysis_bp,
        vendor_mdm_bp,
        vendor_management_bp,
        unified_vendors_bp,
    ]

    for bp in blueprints:
        mark_blueprint_guardrailed(bp)

    app.register_blueprint(unified_vendors_api_bp)
    app.register_blueprint(vendors_api_bp)
    app.register_blueprint(vendor_analysis_bp)
    app.register_blueprint(vendor_mdm_bp)
    app.register_blueprint(vendor_management_bp)
    app.register_blueprint(unified_vendors_bp)

    # Flask-RESTX's vendors_api.root endpoint wins GET /api/vendors/ due to
    # Werkzeug's internal rule sorting, and it calls abort(404) (swagger disabled).
    # Override the view function so whichever endpoint Werkzeug selects, the
    # request is handled by search_vendors instead of the dead RESTX root.
    from app.modules.vendors.routes.unified_vendor_api import search_vendors
    app.view_functions["vendors_api.root"] = search_vendors

    # Register function-based routes
    from app.modules.vendors.api.vendor_product_routes import (
        register_vendor_product_routes,
    )
    from app.modules.vendors.api.vendor_catalog_routes import (
        register_vendor_catalog_routes,
    )
    from app.modules.vendors.api.vendor_discovery_routes import (
        register_vendor_discovery_routes,
    )

    register_vendor_product_routes(app)
    register_vendor_catalog_routes(app)
    register_vendor_discovery_routes(app)

    app.logger.info(
        "[MODULE-V2] vendors v2 registered (guardrail-enabled, 9 blueprints)"
    )
