"""
Import Batch module -- Centralized import/batch blueprint registration.

Consolidates registration of 4 import/batch-related blueprints behind a single
feature flag (USE_NEW_IMPORT_BATCH).

Migrated from:
- app/routes/batch_import_routes.py        (26 routes, "batch_import_api" blueprint)
- app/routes/batch_import_view_routes.py   (4 routes, "batch_import_view" blueprint)
- app/api/batch_processing_routes.py       (13 routes, "batch_processing" blueprint)
- app/routes/unified_import_routes.py      (3 routes, "unified_import" blueprint)

Total: 46 routes across 4 blueprints.
"""

import logging

from flask import Flask

logger = logging.getLogger(__name__)


def register(app: Flask) -> None:
    from app import csrf

    # --- 1. Batch Processing API (job management, progress, recovery) ---
    from app.modules.import_batch.routes.batch_processing_routes import (
        register_batch_processing_routes,
    )

    register_batch_processing_routes(app)
    app.logger.info("[API] Batch processing routes registered")

    # --- 2. Batch Import API (file upload, approval workflow, SSE) ---
    from app.modules.import_batch.routes.batch_import_routes import batch_import_bp

    app.register_blueprint(batch_import_bp)
    app.logger.info("[BLUEPRINT] Batch Import API registered at /api/batch-import")

    # --- 3. Batch Import Views (UI pages) ---
    from app.modules.import_batch.routes.batch_import_view_routes import (
        batch_import_view_bp,
    )

    app.register_blueprint(batch_import_view_bp)
    app.logger.info("[BLUEPRINT] Batch Import views registered at /batch-import")

    # --- 4. Unified Import API (quick + governed modes) ---
    from app.modules.import_batch.routes.unified_import_routes import (
        bp as unified_import_bp,
    )

    app.register_blueprint(unified_import_bp)
    app.logger.info("[BLUEPRINT] Unified Import API registered at /api/import")

    app.logger.info("[MODULE] import_batch registered (46 routes, 4 blueprints)")
