"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.ai_analysis_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/ai_import_service.py
"""

from app.modules.ai_chat.services.ai_import_service import (  # noqa: F401
    AIImportResult,
    AIImportService,
    get_ai_import_service,
)
