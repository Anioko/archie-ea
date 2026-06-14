"""
Capability analysis service — imports from inlined canonical sources.

Consolidates:
- capability_gap_service (CapabilityGapAnalysisService)
- capability_health_service (CapabilityHealthService)
- capability_heatmap_service (CapabilityHeatmapService)
- capability_roadmap_dashboard_service (CapabilityRoadmapDashboardService)
- capability_naming_service (CapabilityNamingService)
- capability_naming_validator (CapabilityNamingValidator)
- capability_discovery_agent (CapabilityDiscoveryAgent)
"""

from app.modules.capabilities.services.capability_gap_service import (  # noqa: F401
    CapabilityGapAnalysisService,
)

from app.modules.capabilities.services.capability_health_service import (  # noqa: F401
    CapabilityHealthService,
)

from app.modules.capabilities.services.capability_heatmap_service import (  # noqa: F401
    CapabilityHeatmapService,
)

from app.modules.capabilities.services.capability_roadmap_dashboard_service import (  # noqa: F401
    CapabilityRoadmapDashboardService,
)

from app.modules.capabilities.services.capability_naming_service import (  # noqa: F401
    CapabilityNamingService,
)

from app.modules.capabilities.services.capability_naming_validator import (  # noqa: F401
    CapabilityNamingValidator,
    NamingIssue,
)

from app.modules.capabilities.services.capability_discovery_agent import (  # noqa: F401
    CapabilityClassification,
    CapabilityDiscoveryAgent,
    DiscoveredCapability,
)
