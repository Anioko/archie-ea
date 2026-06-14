"""
DEPRECATED: Import from app.modules.vendors.services instead.
-> app.modules.vendors.services.seeder_service

Backward-compat re-export. Canonical: app/modules/vendors/services/capability_vendor_app_mapping_seeder.py
"""

from app.modules.vendors.services.capability_vendor_app_mapping_seeder import (  # noqa: F401
    ApplicationVendorProductMappingSeeder,
    CapabilityApplicationMappingSeeder,
    CapabilityVendorMappingSeeder,
    CapabilityVendorOrganizationMappingSeeder,
    seed_all_capability_vendor_app_mappings,
)
