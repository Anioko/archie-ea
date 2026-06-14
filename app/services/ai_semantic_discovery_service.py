"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.ai_analysis_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/ai_semantic_discovery_service.py
"""

from app.modules.ai_chat.services.ai_semantic_discovery_service import (  # noqa: F401  # dead-code-ok
    AISemanticDiscoveryService,
    LLMRecommendation,
    SemanticSearchResult,
    get_semantic_discovery_service,
)
