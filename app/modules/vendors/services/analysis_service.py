"""
Vendor analysis service — imports from inlined canonical sources.

Consolidates:
- vendor_analysis_service (VendorAnalysisService)
- vendor_comparison_service (VendorComparisonService)
- vendor_risk_service (VendorRiskService)
- vendor_analyzer (VendorAnalyzer)
- enhanced_vendor_analysis_service (EnhancedVendorAnalysisService)
- vendor_research_service, vendor_scoring_service, capability_based_vendor_selector
- vendor_analysis_vendor_service (VendorService)
"""

from app.modules.vendors.services.vendor_analysis_service import (  # noqa: F401
    VendorAnalysisService,
)

from app.modules.vendors.services.vendor_comparison_service import (  # noqa: F401
    VendorComparisonService,
)

from app.modules.vendors.services.vendor_risk_service import (  # noqa: F401
    VendorRiskService,
)

from app.modules.vendors.services.vendor_analyzer import (  # noqa: F401
    VendorAnalyzer,
)

from app.modules.vendors.services.enhanced_vendor_analysis_service import (  # noqa: F401
    EnhancedVendorAnalysisService,
)

from app.modules.vendors.services.vendor_research_service import (  # noqa: F401
    VendorResearchService,
)

from app.modules.vendors.services.vendor_scoring_service import (  # noqa: F401
    VendorScoringService,
)

from app.modules.vendors.services.capability_based_vendor_selector import (  # noqa: F401
    CapabilityBasedVendorSelector,
)

from app.models.business_capabilities import BusinessCapability
from app.modules.vendors.services.unified_vendors_services import UnifiedVendorService
from app.modules.vendors.services.vendor_analysis_vendor_service import (  # noqa: F401
    VendorService,
)
from app.services.advanced_risk_assessment import (  # noqa: F401
    AdvancedRiskAssessmentService,
)

class CapabilityService:
    """Module-local capability listing service for vendor analysis routes."""

    def get_capabilities(self):
        capabilities = BusinessCapability.query.order_by(BusinessCapability.name).all()
        return [
            {
                "id": capability.id,
                "name": capability.name,
                "level": capability.level,
                "description": capability.description,
                "parent_id": getattr(capability, "parent_id", None),
            }
            for capability in capabilities
        ]


class ExportService:
    """Module-local export service delegating to unified vendors service."""

    def __init__(self):
        self._unified_vendor_service = UnifiedVendorService()

    def export_analysis(self, analysis_id, format_type):
        return self._unified_vendor_service.export_analysis(analysis_id, format_type)
