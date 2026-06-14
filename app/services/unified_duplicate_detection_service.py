"""
DEPRECATED: Canonical location is app.modules.duplicate_detection.services

Backward-compat re-export — all consumers should migrate to:
    from app.modules.duplicate_detection.services import (
        UnifiedDuplicateDetectionService,
        SimilarityResult,
        SimilarityWeights,
    )
"""

from app.modules.duplicate_detection.services.unified_duplicate_detection_service import (  # noqa: F401
    ESTIMATED_SAVINGS_PER_REDUNDANT_APP,
    SimilarityResult,
    SimilarityWeights,
    UnifiedDuplicateDetectionService,
    unified_duplicate_bp,
)
