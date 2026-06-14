"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.llm_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/llm_service_impl.py
"""

from app.modules.ai_chat.services.llm_service_impl import (  # noqa: F401
    LLMService,
)

try:
    from app.modules.ai_chat.services.llm_service_impl import test_api_key  # noqa: F401
except ImportError:
    pass
