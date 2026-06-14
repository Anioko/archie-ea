"""
Capability services — consolidated from 18 legacy files (~332KB) into 3 modules.

Modules:
- capability_service: Core mapping, taxonomy, governance, tagging, APQC mapping
- analysis_service:   Gap analysis, health, heatmap, roadmap, naming, discovery agent
- seeder_service:     Business/technical seeders, ACM, ArchiMate template

Usage::

    from app.modules.capabilities.services import (
        CapabilityTaxonomyService,
        CapabilityGapAnalysisService,
        ACMTechnicalCapabilityService,
    )
"""

from app.modules.capabilities.services.capability_service import (  # noqa: F401
    APQCCapabilityMappingRules,
    APQCCapabilityMappingService,
    AuditEntry,
    CapabilityGovernanceService,
    CapabilityMappingService,
    CapabilityTagService,
    CapabilityTaxonomyService,
    DualCapabilityMappingService,
    MappingConfidenceCalculator,
    MappingValidationResult,
    ValidationResult,
    ValidationViolation,
)
from app.modules.capabilities.services.analysis_service import (  # noqa: F401
    CapabilityClassification,
    CapabilityDiscoveryAgent,
    CapabilityGapAnalysisService,
    CapabilityHealthService,
    CapabilityHeatmapService,
    CapabilityNamingService,
    CapabilityNamingValidator,
    CapabilityRoadmapDashboardService,
    DiscoveredCapability,
    NamingIssue,
)
from app.modules.capabilities.services.seeder_service import (  # noqa: F401
    ACMTechnicalCapabilityService,
    BusinessCapabilityMapper,
    BusinessCapabilitySeeder,
    CapabilityTemplateService,
    TechnicalCapabilitySeeder,
)

__all__ = [
    # Core services
    "CapabilityMappingService",
    "CapabilityTaxonomyService",
    "CapabilityGovernanceService",
    "CapabilityTagService",
    "DualCapabilityMappingService",
    "APQCCapabilityMappingService",
    "APQCCapabilityMappingRules",
    "MappingConfidenceCalculator",
    "MappingValidationResult",
    "AuditEntry",
    "ValidationResult",
    "ValidationViolation",
    # Analysis services
    "CapabilityGapAnalysisService",
    "CapabilityHealthService",
    "CapabilityHeatmapService",
    "CapabilityRoadmapDashboardService",
    "CapabilityNamingService",
    "CapabilityNamingValidator",
    "NamingIssue",
    "CapabilityDiscoveryAgent",
    "CapabilityClassification",
    "DiscoveredCapability",
    # Seeder services
    "BusinessCapabilityMapper",
    "BusinessCapabilitySeeder",
    "TechnicalCapabilitySeeder",
    "ACMTechnicalCapabilityService",
    "CapabilityTemplateService",
]
