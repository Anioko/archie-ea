"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.chat_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/ai_chat_memory_service.py
"""

from app.modules.ai_chat.services.ai_chat_memory_service import (  # noqa: F401
    AIChatMemoryService,
    get_chat_memory_service,
)
