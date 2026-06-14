"""
AI Chat module -- Centralized AI chat blueprint registration.

Consolidates registration of 4 AI chat-related blueprints behind a single
feature flag (USE_NEW_AI_CHAT).

Migrated from:
- app/routes/unified_ai_chat_routes.py       (66 routes, "unified_ai_chat" blueprint)
- app/ai_chat/data_interaction_routes.py     (14 routes, "ai_data_interaction" blueprint)
- app/routes/ai_assistance_routes.py         (7 routes, "ai_assistance" blueprint)
- app/routes/ai_gap_detection_routes.py      (9 routes, "ai_gap_detection" blueprint)

Total: 96 routes across 4 blueprints.
"""

import logging

from flask import Flask

logger = logging.getLogger(__name__)


def register(app: Flask) -> None:
    # --- 1. Unified AI Chat (decomposed into 8 sub-modules) ---
    from .routes import unified_ai_chat_bp

    app.register_blueprint(unified_ai_chat_bp)

    # --- 2. AI Data Interaction (CRUD operations for AI chat) ---
    from .routes.data_interaction_routes import ai_data_interaction

    app.register_blueprint(ai_data_interaction)
    app.logger.info(
        "[BLUEPRINT] AI Data Interaction API registered at /ai-chat/data (CSRF protected)"
    )

    # --- 3. AI Assistance API (context-aware helpers, content safety) ---
    from .routes.ai_assistance_routes import ai_assistance_bp

    app.register_blueprint(ai_assistance_bp)
    app.logger.info("[BLUEPRINT] AI Assistance API registered at /api/ai-assistance")

    # --- 4. AI Gap Detection API ---
    try:
        from .routes.ai_gap_detection_routes import ai_gap_detection_bp

        app.register_blueprint(ai_gap_detection_bp)
        app.logger.info(
            "[BLUEPRINT] AI Gap Detection API registered at /api/ai-gap-detection"
        )
    except ImportError as e:
        app.logger.warning(f"[BLUEPRINT] AI Gap Detection API not available: {e}")

    app.logger.info("[MODULE] ai_chat registered (96 routes, 4 blueprints)")
