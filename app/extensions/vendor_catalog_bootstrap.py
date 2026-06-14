import os


def bootstrap_vendor_catalog(app):
    """Dev bootstrap to register vendor catalog API behind a feature flag.
    This avoids touching app/__init__.py while enabling dev verification.
    """
    try:
        dev_flag = os.environ.get("DEV_VEND_CATALOG", "0") == "1" or app.config.get(
            "DEV_VEND_CATALOG", False
        )
        from app.api.vendor_catalog_api import vendor_catalog_api_bp

        if dev_flag:
            # Check if blueprint is already registered to prevent duplicates
            if "vendor_catalog_api" not in app.blueprints:
                app.register_blueprint(vendor_catalog_api_bp, url_prefix="/api/vendor-catalog")
                app.logger.info("[DEV] Vendor Catalog API registered at /api/vendor-catalog")
            else:
                app.logger.info("[DEV] Vendor Catalog API already registered, skipping")
        else:
            app.logger.info("[DEV] Vendor Catalog API not registered (DEV_VEND_CATALOG flag off)")
    except Exception as e:
        app.logger.warning(f"[DEV] Vendor Catalog bootstrap failed: {e}")
