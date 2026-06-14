"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.llm_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/llm_health_check.py
"""

from app.modules.ai_chat.services.llm_health_check import (  # noqa: F401
    is_ai_available,
    validate_llm_config,
)
