"""
Application capability service — imports from inlined canonical sources.

Consolidates:
- application_capability_catalog (ApplicationCapabilityCatalogService)
- application_capability_mapper (ApplicationCapabilityMapperService)
- application_capability_seeder (ApplicationCapabilitySeeder)
"""

from app.modules.applications.services.application_capability_catalog import (  # noqa: F401
    ApplicationCapabilityCatalogService,
    CapabilitySpec,
    FunctionSpec,
    SeedingResult,
    build_hierarchical_catalog,
    ensure_capabilities_seeded,
    flatten_level_two_capabilities,
    get_catalog_with_ids,
)

from app.modules.applications.services.application_capability_mapper import (  # noqa: F401
    ApplicationCapabilityMapperService,
)

# Capability seeder — has broken import (application_capability_seed_data), lazy-load
try:
    from app.modules.applications.services.application_capability_seeder import (  # noqa: F401
        ApplicationCapabilitySeeder,
    )
except ImportError:
    ApplicationCapabilitySeeder = None  # type: ignore[assignment,misc]
