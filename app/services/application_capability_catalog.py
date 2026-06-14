# DEPRECATED: Import from app.modules.applications.services.application_capability_catalog instead.
"""Backward-compatibility shim. Canonical: app/modules/applications/services/application_capability_catalog.py"""
from app.modules.applications.services.application_capability_catalog import (  # noqa: F401,F403
    FunctionSpec,
    CapabilitySpec,
    CATALOG_ROOT,
    ensure_capabilities_seeded,
    get_catalog_with_ids,
    flatten_level_two_capabilities,
    build_hierarchical_catalog,
    SeedingResult,
    ApplicationCapabilityCatalogService,
)
