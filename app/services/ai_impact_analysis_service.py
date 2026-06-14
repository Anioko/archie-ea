"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.ai_impact_analysis_service

Backward-compat re-export.
"""

from app.modules.ai_chat.services.ai_impact_analysis_service import (  # noqa: F401  # dead-code-ok
    AIImpactAnalysisService,
)

try:
    from app.modules.ai_chat.services.ai_impact_analysis_service import (  # noqa: F401  # dead-code-ok
        get_analysis_types,
    )
except ImportError:
    pass
