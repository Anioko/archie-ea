"""
AI Chat v2 — Guardrail-enabled thin wrapper over v1 module.

Strangler Fig migration from app/modules/ai_chat/ (v1).
Applies mark_blueprint_guardrailed() to all blueprints registered by the
v1 module, enabling guardrail detection and request-level timing.

Feature flag: USE_AI_CHAT_V2
Fallback: v1 routes (unchanged)
Rollback: Set USE_AI_CHAT_V2=false → v1 routes take over instantly.
"""

from flask import Flask


def register(app: Flask) -> None:
    """Register the ai_chat v2 module (guardrail-wrapped v1 blueprints)."""
    from app.core.compat import mark_blueprint_guardrailed

    # Import all V1 blueprints
    from app.modules.ai_chat.routes import unified_ai_chat_bp
    from app.modules.ai_chat.routes.data_interaction_routes import ai_data_interaction
    from app.modules.ai_chat.routes.ai_assistance_routes import ai_assistance_bp
    from app.modules.ai_chat.routes.ai_gap_detection_routes import ai_gap_detection_bp

    # Mark all blueprints as guardrailed BEFORE registration
    blueprints = [
        unified_ai_chat_bp,
        ai_data_interaction,
        ai_assistance_bp,
        ai_gap_detection_bp,
    ]

    for bp in blueprints:
        mark_blueprint_guardrailed(bp)

    # Register all blueprints
    app.register_blueprint(unified_ai_chat_bp)
    app.register_blueprint(ai_data_interaction)
    app.register_blueprint(ai_assistance_bp)
    app.register_blueprint(ai_gap_detection_bp)

    app.logger.info(
        "[MODULE-V2] ai_chat v2 registered (guardrail-enabled, 96 routes, 4 blueprints)"
    )
