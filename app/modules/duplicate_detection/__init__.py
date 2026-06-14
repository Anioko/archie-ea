"""
Duplicate Detection module -- Centralized duplicate detection blueprint registration.

Consolidates registration of 2 duplicate detection blueprints behind a single
feature flag (USE_NEW_DEDUPE).

Migrated from:
- app/routes/unified_duplicate_routes.py  (36 routes, "unified_duplicate" blueprint)
- app/routes/ai_dedupe_routes.py          (8 routes, "ai" blueprint)

Total: 44 routes across 2 blueprints.

Note: app/routes/dedupe_routes.py is already DEPRECATED and not registered.
"""

import logging

from flask import Flask

from app.extensions import db  # noqa: F401 — re-exported for submodule imports

logger = logging.getLogger(__name__)


def register(app: Flask) -> None:
    # --- 1. Unified Duplicate Detection (enterprise + simple + AI) ---
    from app.modules.duplicate_detection.routes.unified_duplicate_routes import (
        unified_duplicate_bp,
    )

    app.register_blueprint(unified_duplicate_bp)

    app.logger.info("[MODULE] duplicate_detection registered (unified blueprint)")
