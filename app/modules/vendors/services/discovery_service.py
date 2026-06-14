"""
Vendor discovery service — imports from inlined canonical sources.

Consolidates:
- vendor_discovery_engine (VendorDiscoveryEngine)
- semantic_vendor_discovery (SemanticVendorDiscovery)
- vendor_mdm (VendorMDMService)
- vendor_data_population (VendorDataPopulationService)
- vendor_data_population_service (PopulationStats)
"""

from app.modules.vendors.services.vendor_discovery_engine import (  # noqa: F401
    VendorDiscoveryEngine,
)

from app.modules.vendors.services.semantic_vendor_discovery import (  # noqa: F401
    SemanticMatch,
    SemanticVendorDiscovery,
    VectorIndex,
)

from app.modules.vendors.services.vendor_mdm import (  # noqa: F401
    VendorMDMService,
)

# Data population — has broken import (scripts.vendor_seeds), lazy-load
try:
    from app.modules.vendors.services.vendor_data_population import (  # noqa: F401
        VendorDataPopulationService,
        populate_vendor_data,
    )
except ImportError:
    VendorDataPopulationService = None  # type: ignore[assignment,misc]
    populate_vendor_data = None  # type: ignore[assignment]

# Data population service v2
try:
    from app.modules.vendors.services.vendor_data_population_service import (  # noqa: F401
        PopulationStats,
        get_vendor_population_service,
    )
except ImportError:
    PopulationStats = None  # type: ignore[assignment,misc]
    get_vendor_population_service = None  # type: ignore[assignment]

from app.modules.vendors.v2.services import (  # noqa: F401
    SemanticSearchResult,
    get_pgvector_semantic_discovery_adapter,
)
