"""
DEPRECATED: Import from app.modules.import_batch.services instead.
-> app.modules.import_batch.services.import_service

Backward-compat re-export. Canonical: app/modules/import_batch/services/abacus_import_service.py
"""

from app.modules.import_batch.services.abacus_import_service import (  # noqa: F401
    AbacusImportService,
    create_import_service,
)
