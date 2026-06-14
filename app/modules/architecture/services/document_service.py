"""
Architecture document service — imports from inlined canonical sources.

Consolidates document processing services:
- app.services.archimate.document_analysis_service (DocumentAnalysisService — 183KB)
- app.services.archimate.document_processor (DocumentProcessor — 44KB)
- app.services.archimate.document_text_extractor (DocumentTextExtractor — 26KB)
- app.services.archimate.document_chunking_service (DocumentChunkingService — 10KB)
- app.services.archimate.document_comparison_service (DocumentComparisonService — 9KB)
- app.services.archimate.document_upload_service (DocumentUploadService — 7KB)
- app.services.archimate.tabular_data_extractor (TabularDataExtractor — 18KB)
- app.services.archimate.data_model_validation_service (DataModelValidationService — 40KB)
"""

from app.modules.architecture.services.document_analysis_service import (  # noqa: F401
    DocumentAnalysisService,
)

from app.modules.architecture.services.document_processor import (  # noqa: F401
    DocumentProcessor,
)

# document_text_extractor has no class — it exports functions only
try:
    from app.modules.architecture.services import document_text_extractor as document_text_extractor_module  # noqa: F401
except ImportError:
    document_text_extractor_module = None  # type: ignore[assignment]

from app.modules.architecture.services.document_chunking_service import (  # noqa: F401
    DocumentChunkingService,
)

from app.modules.architecture.services.document_comparison_service import (  # noqa: F401
    DocumentComparisonService,
)

from app.modules.architecture.services.document_upload_service import (  # noqa: F401
    DocumentUploadService,
)

from app.modules.architecture.services.tabular_data_extractor import (  # noqa: F401
    TabularDataExtractor,
)

# data_model_validation_service has a syntax error in source, lazy-load
try:
    from app.modules.architecture.services.data_model_validation_service import (  # noqa: F401
        DataModelValidationService,
    )
except (ImportError, SyntaxError):
    DataModelValidationService = None  # type: ignore[assignment,misc]
