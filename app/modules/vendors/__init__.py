"""
Vendors module -- Vendor management, analysis, MDM, comparison, discovery, and catalog.

Migrated from 16 legacy files across app/routes/, app/api/, app/api_vendors.py, app/unified_vendors/.

Blueprints preserved (13):
- "vendors_api" (Flask-RESTX, url_prefix=/api/vendors)
- "vendor_analysis" (url_prefix=/vendor-analysis)
- "vendor_mdm" (url_prefix=/api/vendor-mdm)
- "vendor_management" (url_prefix=/vendor-management)
- "unified_vendors" (url_prefix=/vendors)
- "unified_vendors_api" (url_prefix=/api/vendors)
- "vendor_comparison" (url_prefix=/api/vendor-comparison)
- "legacy_vendor_redirects" (no prefix)
- "vendor_product" (url_prefix=/api/vendor)
- "vendor" (url_prefix=/api/vendors)
- "vendor_discovery" (url_prefix=/api/vendor-discovery)
- "ai_vendor_discovery" (url_prefix=/api/vendor-discovery)
- "advanced_vendor" (url_prefix=/api/advanced-vendor)
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

    # 7. Vendor comparison
    from .routes.vendor_comparison_routes import vendor_comparison_bp

    app.register_blueprint(vendor_comparison_bp)

    # 8. Legacy redirects
    from .routes.legacy_vendor_redirects import legacy_vendor_redirects_bp

    app.register_blueprint(legacy_vendor_redirects_bp)

    # 9-11. Function-based registrations
    from .api.vendor_product_routes import register_vendor_product_routes

    register_vendor_product_routes(app)

    from .api.vendor_catalog_routes import register_vendor_catalog_routes

    register_vendor_catalog_routes(app)

    from .api.vendor_discovery_routes import register_vendor_discovery_routes

    register_vendor_discovery_routes(app)

    # 12. AI vendor discovery
    from .api.ai_vendor_discovery_routes import ai_vendor_discovery_bp

    app.register_blueprint(ai_vendor_discovery_bp, url_prefix="/api/vendor-discovery")

    # 13. Advanced vendor API
    from .api.advanced_vendor_api import advanced_vendor_bp

    app.register_blueprint(advanced_vendor_bp)

    app.logger.info("[MODULE] vendors registered (13 blueprints, ~166 routes)")
