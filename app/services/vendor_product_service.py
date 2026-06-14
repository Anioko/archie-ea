"""
DEPRECATED: Import from app.modules.vendors.services instead.
-> app.modules.vendors.services.vendor_service

Backward-compat re-export. Canonical: app/modules/vendors/services/vendor_product_service.py
"""

from app.modules.vendors.services.vendor_product_service import (  # noqa: F401
    VendorExtractionResult,
    VendorProductService,
)
