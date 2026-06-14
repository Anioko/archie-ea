"""Dashboard v2 alias for unified duplicate detection service."""

from app.modules.duplicate_detection.services.unified_duplicate_detection_service import (
    UnifiedDuplicateDetectionService,
)

__all__ = ["UnifiedDuplicateDetectionService"]
