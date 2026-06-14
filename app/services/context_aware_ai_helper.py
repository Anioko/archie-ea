"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.ai_assistant_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/context_aware_ai_helper.py
"""

from app.modules.ai_chat.services.context_aware_ai_helper import (  # noqa: F401
    ContextAwareAIHelper,
    ContextType,
    get_ai_helper,
)
