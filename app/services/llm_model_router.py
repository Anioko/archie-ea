"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.llm_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/llm_model_router.py
"""

from app.modules.ai_chat.services.llm_model_router import (  # noqa: F401
    LLMModelRouter,
    TaskComplexity,
    TaskPriority,
)
