"""
Import Batch v2 — Guardrail-enabled thin wrapper over v1 module.

Strangler Fig migration from app/modules/import_batch/ (v1).
Applies mark_blueprint_guardrailed() to all blueprints registered by the
v1 module, enabling guardrail detection and request-level timing.

Feature flag: USE_IMPORT_BATCH_V2
Fallback: v1 routes (unchanged)
Rollback: Set USE_IMPORT_BATCH_V2=false → v1 routes take over instantly.
"""

from flask import Flask


def register(app: Flask) -> None:
    """Register the import_batch v2 module (guardrail-wrapped v1 blueprints)."""
    from app import csrf
    from app.core.compat import mark_blueprint_guardrailed

    # Import all V1 blueprints
    from app.modules.import_batch.routes.batch_import_routes import batch_import_bp
    from app.modules.import_batch.routes.batch_import_view_routes import (
        batch_import_view_bp,
    )
    from app.modules.import_batch.routes.unified_import_routes import (
        bp as unified_import_bp,
    )

    # Mark blueprints as guardrailed BEFORE registration
    blueprints = [batch_import_bp, batch_import_view_bp, unified_import_bp]

    for bp in blueprints:
        mark_blueprint_guardrailed(bp)

    # Register blueprints
    app.register_blueprint(batch_import_bp)
    app.register_blueprint(batch_import_view_bp)
    app.register_blueprint(unified_import_bp)

    # Register function-based routes
    from app.modules.import_batch.routes.batch_processing_routes import (
        register_batch_processing_routes,
    )

    register_batch_processing_routes(app)

    app.logger.info(
        "[MODULE-V2] import_batch v2 registered (guardrail-enabled, 46 routes, 4 blueprints)"
    )
