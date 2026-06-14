"""
DEPRECATED: Import from app.modules.import_batch.services instead.
-> app.modules.import_batch.services.batch_service

Backward-compat re-export. Canonical: app/modules/import_batch/services/batch_processing_service.py
"""

from app.modules.import_batch.services.batch_processing_service import (  # noqa: F401
    BatchJobConfig,
    BatchJobProgress,
    BatchJobResult,
    BatchProcessingService,
)
