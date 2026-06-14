"""
AI assistant service — imports from inlined canonical sources.

Consolidates AI assistants, suggestions, and helper services:
- unified_ai_assistant (UnifiedAIAssistant)
- ai_suggestion_service (AISuggestionService)
- context_aware_ai_helper (ContextAwareAIHelper)
- workspace_ai_service (WorkspaceAIService)
- solution_ai_service (SolutionAIService)
- ai_prompt_seeder (functions only)
- real_ai_apqc_service (functions only)
"""

from app.modules.ai_chat.services.unified_ai_assistant import (  # noqa: F401
    UnifiedAIAssistant,
)

from app.modules.ai_chat.services.ai_suggestion_service import (  # noqa: F401
    AISuggestionService,
)

from app.modules.ai_chat.services.context_aware_ai_helper import (  # noqa: F401
    ContextAwareAIHelper,
    ContextType,
)

try:
    from app.modules.ai_chat.services.workspace_ai_service import (  # noqa: F401
        WorkspaceAIService,
    )
except ImportError:
    WorkspaceAIService = None  # type: ignore[assignment,misc]

from app.modules.ai_chat.services.solution_ai_service import (  # noqa: F401
    SolutionAIService,
)

# Function-only modules
try:
    from app.modules.ai_chat.services import ai_prompt_seeder as ai_prompt_seeder_module  # noqa: F401
except ImportError:
    ai_prompt_seeder_module = None  # type: ignore[assignment]

try:
    from app.modules.ai_chat.services import real_ai_apqc_service as real_ai_apqc_module  # noqa: F401
except ImportError:
    real_ai_apqc_module = None  # type: ignore[assignment]
