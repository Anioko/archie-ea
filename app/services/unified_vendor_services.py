"""
DEPRECATED: Import from app.modules.vendors.services instead.
-> app.modules.vendors.services.vendor_service

Backward-compat re-export. Canonical: app/modules/vendors/services/unified_vendor_services.py
"""

from app.modules.vendors.services.unified_vendor_services import (  # noqa: F401
    UnifiedVendorServices,
    get_unified_vendor_services,
)
