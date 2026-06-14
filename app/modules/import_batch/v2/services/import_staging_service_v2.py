"""
DEPRECATED: Import from app.modules.import_batch.services instead.
-> app.modules.import_batch.services.import_service

Backward-compat re-export. Canonical: app/modules/import_batch/services/import_staging_service.py
"""

from app.modules.import_batch.services.import_staging_service import (  # noqa: F401
    ImportStagingService,
    get_import_staging_service,
)
