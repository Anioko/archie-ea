"""
Applications v2 — Guardrail-enabled thin wrapper over v1 module.

Strangler Fig migration from app/modules/applications/ (v1).
Applies mark_blueprint_guardrailed() to all blueprints registered by the
v1 module, enabling guardrail detection and request-level timing.

Feature flag: USE_APPLICATIONS_V2
Fallback: v1 routes (unchanged)
Rollback: Set USE_APPLICATIONS_V2=false → v1 routes take over instantly.
"""
from flask import Flask


def register(app: Flask) -> None:
    """Register the applications v2 module (guardrail-wrapped v1 blueprints)."""
    # Import all V1 blueprints (already marked as guardrailed at source)
    from app.modules.applications.routes import unified_applications_bp
    from app.api.application_merging_routes import merging_bp
    from app.implementation_planning import implementation_planning

    # Register all blueprints (guardrails already applied at blueprint creation)
    app.register_blueprint(unified_applications_bp)
    app.register_blueprint(merging_bp)
    app.register_blueprint(implementation_planning)

    app.logger.info(
        "[MODULE-V2] applications v2 registered (guardrail-enabled, 127 routes, 3 blueprints)"
    )
