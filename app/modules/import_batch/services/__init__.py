"""
Import/Batch services — consolidated from 19 legacy files (~329KB) into 3 modules.

Modules:
- import_service:         Core import (Abacus, staging, preview, audit, recovery, rollback, validation)
- batch_service:          Batch processing (import, approval, processing, processor, recovery)
- unified_import_service: Unified import sub-package (orchestrator, parser, cost, dedup, AI gen)

Usage:
    from app.modules.import_batch.services.import_service import AbacusImportService
    from app.modules.import_batch.services.batch_service import BatchProcessingService
    from app.modules.import_batch.services.unified_import_service import ImportOrchestrator
"""
