"""
Capability core service — imports from inlined canonical sources.

Consolidates:
- capability_mapping_service (CapabilityMappingService)
- capability_taxonomy_service (CapabilityTaxonomyService)
- capability_governance_service (CapabilityGovernanceService)
- capability_tagging_service (CapabilityTagService)
- dual_capability_mapping_service (DualCapabilityMappingService)
- apqc_capability_mapping_service (APQCCapabilityMappingService)
"""

from app.modules.capabilities.services.capability_mapping_service import (  # noqa: F401
    CapabilityMappingService,
)

from app.modules.capabilities.services.capability_taxonomy_service import (  # noqa: F401
    CapabilityTaxonomyService,
    ValidationResult,
    ValidationViolation,
)

from app.modules.capabilities.services.capability_governance_service import (  # noqa: F401
    CapabilityGovernanceService,
)

from app.modules.capabilities.services.capability_tagging_service import (  # noqa: F401
    CapabilityTagService,
)

from app.modules.capabilities.services.dual_capability_mapping_service import (  # noqa: F401
    DualCapabilityMappingService,
)

from app.modules.capabilities.services.apqc_capability_mapping_service import (  # noqa: F401
    APQCCapabilityMappingRules,
    APQCCapabilityMappingService,
    AuditEntry,
    MappingConfidenceCalculator,
    MappingValidationResult,
)
