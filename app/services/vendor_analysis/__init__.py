"""
Vendor Options Analysis Services

This package provides comprehensive vendor analysis and comparison services for Enterprise architects.
"""

try:
    from .options_analysis_service import OptionsAnalysisService
except ImportError:
    OptionsAnalysisService = None

try:
    from .vendor_scoring_service import VendorScoringService
except ImportError:
    VendorScoringService = None

try:
    from .vendor_research_service import VendorResearchService
except ImportError:
    VendorResearchService = None

try:
    from .recommendation_engine import RecommendationEngine
except ImportError:
    RecommendationEngine = None

try:
    from .open_data_service import OpenVendorDataService
except ImportError:
    OpenVendorDataService = None

from .capability_based_vendor_selector import CapabilityBasedVendorSelector

__all__ = [
    'OptionsAnalysisService',
    'VendorScoringService',
    'VendorResearchService',
    'RecommendationEngine',
    'OpenVendorDataService',
    'CapabilityBasedVendorSelector',
]
