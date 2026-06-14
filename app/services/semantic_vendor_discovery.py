"""
DEPRECATED: Import from app.modules.vendors.services instead.
-> app.modules.vendors.services.discovery_service

Backward-compat re-export. Canonical: app/modules/vendors/services/semantic_vendor_discovery.py
"""

from app.modules.vendors.services.semantic_vendor_discovery import (  # noqa: F401
    SemanticMatch,
    SemanticVendorDiscovery,
    VectorIndex,
)
