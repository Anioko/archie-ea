"""
DEPRECATED: Canonical location is app.modules.duplicate_detection.services

Backward-compat re-export — all consumers should migrate to:
    from app.modules.duplicate_detection.services import (
        DuplicateDetector, DuplicateInfo, DuplicateAnalysisResult,
    )
"""

from app.modules.duplicate_detection.services.duplicate_detector import (  # noqa: F401
    DuplicateAnalysisResult,
    DuplicateDetector,
    DuplicateInfo,
)
