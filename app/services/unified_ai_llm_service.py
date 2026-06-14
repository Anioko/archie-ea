"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.llm_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/unified_ai_llm_service.py
"""

from app.modules.ai_chat.services.unified_ai_llm_service import (  # noqa: F401
    ServiceMode,
    UnifiedAILLMService,
    create_unified_service,
    get_available_services,
)
