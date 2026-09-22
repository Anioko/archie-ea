"""
Vendors module -- Vendor management, analysis, MDM, comparison, discovery, and catalog.

Migrated from 16 legacy files across app/routes/, app/api/, app/api_vendors.py, app/unified_vendors/.

Blueprints preserved (9):
- "vendors_api" (Flask-RESTX, url_prefix=/api/vendors)
- "vendor_analysis" (url_prefix=/vendor-analysis)
- "vendor_mdm" (url_prefix=/api/vendor-mdm)
- "vendor_management" (url_prefix=/vendor-management)
- "unified_vendors" (url_prefix=/vendors)
- "unified_vendors_api" (url_prefix=/api/vendors)
- "vendor_product" (url_prefix=/api/vendor)
- "vendor" (url_prefix=/api/vendors)
- "vendor_discovery" (url_prefix=/api/vendor-discovery)

vendor_comparison, legacy_vendor_redirects, ai_vendor_discovery and
advanced_vendor were deliberately deleted in the consolidation into
unified_vendors_api (COM-015, BPM-001 waves 1-2, zero callers) -- see
app/_bootstrap/blueprints.py's _register_vendors().
"""

from flask import Flask


def register(app: Flask) -> None:
    from app import csrf

    # 1. Flask-RESTX vendors API
    from .api.api_vendors import vendors_api_bp

    app.register_blueprint(vendors_api_bp)

    # 2. Vendor analysis
    from .routes.vendor_analysis_routes import vendor_analysis_bp

    app.register_blueprint(vendor_analysis_bp)

    # 3. Vendor MDM
    from .routes.vendor_mdm_api import vendor_mdm_bp

    app.register_blueprint(vendor_mdm_bp)

    # 4. Vendor management
    from .routes.vendor_management_routes import vendor_management_bp

    app.register_blueprint(vendor_management_bp)

    # 5-6. Unified vendors
    from .routes.unified_vendor_views import unified_vendors_bp
    from .routes.unified_vendor_api import unified_vendors_api_bp

    app.register_blueprint(unified_vendors_bp)
    app.register_blueprint(unified_vendors_api_bp)

    # 7-9. Function-based registrations
    from .api.vendor_product_routes import register_vendor_product_routes

    register_vendor_product_routes(app)

    from .api.vendor_catalog_routes import register_vendor_catalog_routes

    register_vendor_catalog_routes(app)

    from .api.vendor_discovery_routes import register_vendor_discovery_routes

    register_vendor_discovery_routes(app)

    app.logger.info("[MODULE] vendors registered (9 blueprints, ~166 routes)")
