"""
Unified import service — imports from inlined canonical sources.

Consolidates unified_import sub-package services:
- import_orchestrator (ImportOrchestrator)
- file_parser (FileParser)
- cost_estimator (CostEstimator)
- ai_element_generator (AIElementGenerator)
- duplicate_detector — deprecated, re-exports from duplicate_detection module
"""

from app.modules.import_batch.services.import_orchestrator import (  # noqa: F401
    ImportAnalysisResult,
    ImportMode,
    ImportOrchestrator,
    QuickImportResult,
)

from app.modules.import_batch.services.file_parser import (  # noqa: F401
    FileParser,
    FileStats,
)

from app.modules.import_batch.services.cost_estimator import (  # noqa: F401
    CostBreakdown,
    CostEstimate,
    CostEstimator,
)

# Duplicate detector — deprecated stub, re-exports from duplicate_detection module
from app.modules.import_batch.v2.services.unified_import.duplicate_detector_v2 import (  # noqa: F401
    DuplicateAnalysisResult,
    DuplicateDetector,
    DuplicateInfo,
)

from app.modules.import_batch.services.ai_element_generator import (  # noqa: F401
    AIElementGenerator,
    GenerationMetrics,
)
