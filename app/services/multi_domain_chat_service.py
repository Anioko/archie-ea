"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.chat_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/multi_domain_chat_service.py
"""

from app.modules.ai_chat.services.multi_domain_chat_service import (  # noqa: F401  # dead-code-ok
    MultiDomainChatService,
    PERSONA_CONFIGS,
)
