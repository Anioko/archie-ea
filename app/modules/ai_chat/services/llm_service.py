"""
LLM infrastructure service — imports from inlined canonical sources.

Consolidates LLM routing, caching, and cost tracking:
- llm_service_impl (LLMService)
- llm_cache (LLMCache)
- llm_cost_tracker (LLMCostTracker)
- llm_model_router (LLMModelRouter)
- llm_router (syntax error in source, lazy-load)
- llm_health_check (functions only)
- unified_ai_llm_service (UnifiedAILLMService)
"""

import logging

logger = logging.getLogger(__name__)

from app.modules.ai_chat.services.llm_service_impl import (  # noqa: F401
    LLMService,
)

from app.modules.ai_chat.services.llm_cache import (  # noqa: F401
    LLMCache,
)

from app.modules.ai_chat.services.llm_cost_tracker import (  # noqa: F401
    LLMCostTracker,
)

from app.modules.ai_chat.services.llm_model_router import (  # noqa: F401  # dead-code-ok
    LLMModelRouter,
    TaskComplexity,
    TaskPriority,
)

# llm_router has a syntax error in source
try:
    from app.modules.ai_chat.services.llm_router import *  # noqa: F401,F403
except (ImportError, SyntaxError):
    logger.exception("Failed to operation")
    pass

# llm_health_check exports functions only
try:
    from app.modules.ai_chat.services import llm_health_check as llm_health_check_module  # noqa: F401
except ImportError:
    llm_health_check_module = None  # type: ignore[assignment]

from app.modules.ai_chat.services.unified_ai_llm_service import (  # noqa: F401  # dead-code-ok
    ServiceMode,
    UnifiedAILLMService,
)
