"""
Duplicate Detection v2 — Full guardrail-enabled module using new architecture.

Strangler Fig migration from app/modules/duplicate_detection/ (v1).
Uses:
- app.core.decorators (timed_route)
- app.core.compat (mark_blueprint_guardrailed)

Blueprints preserved (same names as v1 for url_for compatibility):
- "unified_duplicate" (url_prefix=/duplicate-detection, 36 routes)
- "ai" (url_prefix=/duplicate-detection/ai, 8 routes)

Feature flag: USE_DEDUPE_V2
Fallback: v1 routes (unchanged)
Rollback: Set USE_DEDUPE_V2=false → v1 routes take over instantly.
"""
from flask import Flask


def register(app: Flask) -> None:
    """Register the duplicate_detection v2 module (2 blueprints, 44 routes)."""
    from .routes import unified_duplicate_bp_v2, ai_dedupe_bp_v2

    app.register_blueprint(unified_duplicate_bp_v2)

    try:
        app.register_blueprint(ai_dedupe_bp_v2, url_prefix="/duplicate-detection/ai")
        app.logger.info("[BLUEPRINT-V2] AI Dedupe routes registered at /duplicate-detection/ai")
    except ImportError as e:
        app.logger.warning(f"[BLUEPRINT-V2] AI Dedupe routes not available: {e}")

    app.logger.info(
        "[MODULE-V2] duplicate_detection v2 registered (guardrail-enabled, 44 routes, 2 blueprints)"
    )
