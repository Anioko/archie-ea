"""
Vendor core service — imports from inlined canonical sources.

Consolidates:
- unified_vendor_services (UnifiedVendorServices)
- unified_vendors_services (UnifiedVendorService, VendorCatalogService, etc.)
- vendor_product_service (VendorProductService)
- vendor_onboarding_service (VendorOnboardingService)
- vendor_product_template_service (VendorProductTemplateService)
"""

from app.modules.vendors.services.unified_vendor_services import (  # noqa: F401
    UnifiedVendorServices,
    get_unified_vendor_services,
)

from app.modules.vendors.services.unified_vendors_services import (  # noqa: F401
    AnalysisResult,
    UnifiedVendorService,
    VendorCatalogService,
    VendorDataQualityService,
    VendorExtractionResult as UnifiedVendorExtractionResult,
    VendorIntelligenceService,
    VendorIntegrationService as UnifiedVendorIntegrationService,
    VendorMatchResult,
)

from app.modules.vendors.services.vendor_product_service import (  # noqa: F401
    VendorExtractionResult,
    VendorProductService,
)

from app.modules.vendors.services.vendor_onboarding_service import (  # noqa: F401
    VendorOnboardingService,
    get_vendor_organization_model,
)

from app.modules.vendors.services.vendor_product_template_service import (  # noqa: F401
    VendorProductTemplateService,
)
