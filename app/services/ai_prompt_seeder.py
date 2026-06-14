"""
DEPRECATED: Import from app.modules.ai_chat.services instead.
-> app.modules.ai_chat.services.ai_assistant_service

Backward-compat re-export. Canonical: app/modules/ai_chat/services/ai_prompt_seeder.py
"""

from app.modules.ai_chat.services.ai_prompt_seeder import (  # noqa: F401
    seed_default_ai_prompt_templates,
)
