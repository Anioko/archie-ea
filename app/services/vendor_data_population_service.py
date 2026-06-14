"""
DEPRECATED: Import from app.modules.vendors.services instead.
-> app.modules.vendors.services.discovery_service

Backward-compat re-export. Canonical: app/modules/vendors/services/vendor_data_population_service.py
"""

from app.modules.vendors.services.vendor_data_population_service import (  # noqa: F401
    PopulationStats,
    get_vendor_population_service,
)
