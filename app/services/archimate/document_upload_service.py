"""
DEPRECATED: Import from app.modules.architecture.services instead.
-> app.modules.architecture.services.document_upload_service
Backward-compat re-export. Canonical: app/modules/architecture/services/document_upload_service.py
"""
from app.modules.architecture.services.document_upload_service import (  # noqa: F401
    DocumentUploadService,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
)
