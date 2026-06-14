"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.ai_assistant_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/real_ai_apqc_service.py
"""

from app.modules.ai_chat.services.real_ai_apqc_service import (  # noqa: F401
    classify_apqc_text_real,
    get_real_ai_status,
)
