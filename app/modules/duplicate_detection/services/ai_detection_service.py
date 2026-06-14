"""
AI duplicate detection service — imports from inlined canonical source.

Consolidates:
- ai_duplicate_detection_service (AIDuplicateDetectionService)
  Includes: SemanticDetectionEngine, BusinessContextEngine, AdaptiveLearningEngine
"""

from app.modules.duplicate_detection.services.ai_duplicate_detection_service import (  # noqa: F401
    AdaptiveLearningEngine,
    AIDuplicateDetectionService,
    BusinessContextEngine,
    SemanticDetectionEngine,
)
