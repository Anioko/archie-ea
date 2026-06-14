"""
DEPRECATED: Import from app.modules.import_batch.services instead.
-> app.modules.import_batch.services.import_service

Backward-compat re-export. Canonical: app/modules/import_batch/services/import_audit_service.py
"""

from app.modules.import_batch.services.import_audit_service import (  # noqa: F401
    ImportAuditService,
    log_batch_approval,
    log_file_upload,
    log_import_analysis,
    log_import_commit,
)
