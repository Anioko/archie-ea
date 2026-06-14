"""
DEPRECATED: Canonical location is app.modules.duplicate_detection.services

Backward-compat re-export — all consumers should migrate to:
    from app.modules.duplicate_detection.services import (
        DuplicateDetectionUtils, DuplicateDetectionConfig, DuplicateMatch,
    )
"""

from app.modules.duplicate_detection.services.duplicate_detection_utils import (  # noqa: F401
    DuplicateDetectionConfig,
    DuplicateDetectionUtils,
    DuplicateMatch,
)
