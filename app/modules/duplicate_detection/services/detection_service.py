"""
Duplicate detection service — imports from inlined canonical sources.

Consolidates:
- unified_duplicate_detection_service (UnifiedDuplicateDetectionService)
- unified_duplicate_service (UnifiedDuplicateService)
- duplicate_detection_service (DuplicateDetectionService)
- duplicate_detection_utils (DuplicateDetectionUtils)
- duplicate_detector (DuplicateDetector)
"""

# Unified detection service — primary/canonical
from app.modules.duplicate_detection.services.unified_duplicate_detection_service import (  # noqa: F401
    SimilarityResult,
    SimilarityWeights,
    UnifiedDuplicateDetectionService,
)

# Unified duplicate service
from app.modules.duplicate_detection.services.unified_duplicate_service import (  # noqa: F401
    UnifiedDuplicateService,
)

# Legacy detection service
from app.modules.duplicate_detection.services.duplicate_detection_service import (  # noqa: F401
    DuplicateDetectionService,
)

# Detection utilities
from app.modules.duplicate_detection.services.duplicate_detection_utils import (  # noqa: F401
    DuplicateDetectionConfig,
    DuplicateDetectionUtils,
    DuplicateMatch,
)

# Import-phase duplicate detector
from app.modules.duplicate_detection.services.duplicate_detector import (  # noqa: F401
    DuplicateAnalysisResult,
    DuplicateDetector,
    DuplicateInfo,
)
