"""
DEPRECATED: Import from app.modules.vendors.routes instead.
-> app.modules.vendors.routes
Backward-compat re-export. Canonical: app/modules/vendors/routes/
"""
from app.modules.vendors.routes.unified_vendor_views import unified_vendors_bp  # noqa: F401
from app.modules.vendors.routes.unified_vendor_api import unified_vendors_api_bp  # noqa: F401

# Legacy sub-modules expected by 'from . import routes, api'
from app.modules.vendors.routes import unified_vendor_views as routes  # noqa: F401
from app.modules.vendors.routes import unified_vendor_api as api  # noqa: F401
