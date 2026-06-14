"""
DEPRECATED: Import from app.modules.import_batch.services instead.
-> app.modules.import_batch.services.import_service

Backward-compat re-export. Canonical: app/modules/import_batch/services/import_recovery_service.py
"""

from app.modules.import_batch.services.import_recovery_service import (  # noqa: F401
    ImportRecoveryService,
    get_import_recovery_service,
)
