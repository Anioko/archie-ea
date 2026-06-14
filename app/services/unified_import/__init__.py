"""
Unified Import Services

Shared services layer for both Quick Mode (modal, direct commit) and
Governed Mode (dashboard, approval workflow) application imports.

This module consolidates duplicate code from:
- batch_import_service.py (Governed Mode)
- unified_applications_import_routes.py (Quick Mode)
"""

from app.services.unified_import.ai_element_generator import AIElementGenerator, GenerationMetrics
from app.services.unified_import.cost_estimator import CostEstimate, CostEstimator
from app.services.unified_import.duplicate_detector import (
    DuplicateAnalysisResult,
    DuplicateDetector,
)
from app.services.unified_import.file_parser import FileParser, FileStats
from app.services.unified_import.import_orchestrator import (
    ImportAnalysisResult,
    ImportMode,
    ImportOrchestrator,
    QuickImportResult,
    check_import_idempotency,
    store_import_idempotency,
)

__all__ = [
    "FileParser",
    "FileStats",
    "DuplicateDetector",
    "DuplicateAnalysisResult",
    "CostEstimator",
    "CostEstimate",
    "AIElementGenerator",
    "GenerationMetrics",
    "ImportOrchestrator",
    "ImportMode",
    "ImportAnalysisResult",
    "QuickImportResult",
    "check_import_idempotency",
    "store_import_idempotency",
]
