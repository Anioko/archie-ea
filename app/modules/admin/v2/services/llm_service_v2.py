"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.llm_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/llm_service_impl.py
"""

import logging

from app.modules.ai_chat.services.llm_service_impl import (  # noqa: F401  # dead-code-ok
    LLMService,
)

logger = logging.getLogger(__name__)

try:
    from app.modules.ai_chat.services.llm_service_impl import test_api_key  # noqa: F401  # dead-code-ok
except ImportError:
    logger.exception("Failed to operation")
    pass
