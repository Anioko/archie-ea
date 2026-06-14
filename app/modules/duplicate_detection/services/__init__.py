"""
Duplicate detection services — consolidated from 6 legacy files (~173KB) into 2 modules.

Modules:
- detection_service:    Core detection, unified service, utils, import detector
- ai_detection_service: AI/ML-powered detection (semantic, business context, adaptive learning)

Usage::

    from app.modules.duplicate_detection.services import (
        UnifiedDuplicateDetectionService,
        UnifiedDuplicateService,
        DuplicateDetectionUtils,
        AIDuplicateDetectionService,
    )
"""

from app.modules.duplicate_detection.services.detection_service import (  # noqa: F401
    DuplicateAnalysisResult,
    DuplicateDetectionConfig,
    DuplicateDetectionService,
    DuplicateDetectionUtils,
    DuplicateDetector,
    DuplicateInfo,
    DuplicateMatch,
    SimilarityResult,
    SimilarityWeights,
    UnifiedDuplicateDetectionService,
    UnifiedDuplicateService,
)

from app.modules.duplicate_detection.services.ai_detection_service import (  # noqa: F401
    AdaptiveLearningEngine,
    AIDuplicateDetectionService,
    BusinessContextEngine,
    SemanticDetectionEngine,
)

__all__ = [
    # Core detection
    "UnifiedDuplicateDetectionService",
    "UnifiedDuplicateService",
    "DuplicateDetectionService",
    "SimilarityResult",
    "SimilarityWeights",
    # Utilities
    "DuplicateDetectionUtils",
    "DuplicateDetectionConfig",
    "DuplicateMatch",
    # Import-phase detection
    "DuplicateDetector",
    "DuplicateInfo",
    "DuplicateAnalysisResult",
    # AI detection
    "AIDuplicateDetectionService",
    "SemanticDetectionEngine",
    "BusinessContextEngine",
    "AdaptiveLearningEngine",
]
