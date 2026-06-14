"""
DEPRECATED: Canonical location is app.modules.duplicate_detection.services

Backward-compat re-export — all consumers should migrate to:
    from app.modules.duplicate_detection.services import UnifiedDuplicateService
"""

from app.modules.duplicate_detection.services.unified_duplicate_service import (  # noqa: F401
    UnifiedDuplicateService,
    with_retry,
)
