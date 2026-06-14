"""
AI Chat service — imports from inlined canonical sources.

Consolidates chat-specific services:
- ai_chat_approval_service (AIChatApprovalService)
- ai_chat_link_service (AIChatLinkService)
- ai_chat_memory_service (AIChatMemoryService)
- ai_chat_multi_model (MultiModelChatService)
- chat_entity_matching_service (ChatEntityMatchingService)
- multi_domain_chat_service (MultiDomainChatService)
"""

from app.modules.ai_chat.services.ai_chat_approval_service import (  # noqa: F401
    AIChatApprovalService,
)

from app.modules.ai_chat.services.ai_chat_link_service import (  # noqa: F401
    AIChatLinkService,
)

from app.modules.ai_chat.services.ai_chat_memory_service import (  # noqa: F401
    AIChatMemoryService,
)

from app.modules.ai_chat.services.ai_chat_multi_model import (  # noqa: F401
    ChatMessage,
    ModelConfig,
    MultiModelChatService,
)

from app.modules.ai_chat.services.chat_entity_matching_service import (  # noqa: F401
    ChatEntityMatchingService,
)

from app.modules.ai_chat.services.multi_domain_chat_service import (  # noqa: F401
    MultiDomainChatService,
)
