"""
DEPRECATED: Import from app.modules.vendors.services instead.
-> app.modules.vendors.services.seeder_service

Backward-compat re-export. Canonical: app/modules/vendors/services/vendor_json_domain_importer.py
"""

from app.modules.vendors.services.vendor_json_domain_importer import (  # noqa: F401
    DomainImportSummary,
    VendorJsonDomainImporter,
)
