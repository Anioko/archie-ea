"""
Capabilities v2 — Guardrail-enabled thin wrapper over v1 module.

Strangler Fig migration from app/modules/capabilities/ (v1).
Applies mark_blueprint_guardrailed() to all blueprints registered by the
v1 module, enabling guardrail detection and request-level timing.

Feature flag: USE_CAPABILITIES_V2
Fallback: v1 routes (unchanged)
Rollback: Set USE_CAPABILITIES_V2=false → v1 routes take over instantly.
"""

from flask import Flask


def register(app: Flask) -> None:
    """Register the capabilities v2 module (guardrail-wrapped v1 blueprints)."""
    from app import csrf
    from app.core.compat import mark_blueprint_guardrailed

    # Import all V1 blueprints
    from app.modules.capabilities.routes import capability_map
    from app.modules.capabilities.routes.enterprise_api_routes import (
        enterprise_api_bp as enterprise_entity_api_bp,
    )
    from app.modules.capabilities.routes.enterprise_crud_routes import (
        enterprise_crud_bp,
    )
    from app.modules.capabilities.routes.abacus_consolidation import (
        bp as abacus_consolidation_bp,
    )
    from app.modules.capabilities.routes.maturity_routes import maturity_management
    from app.modules.capabilities.api.acm_routes import acm_bp

    # Mark all blueprints as guardrailed BEFORE registration
    blueprints = [
        capability_map,
        enterprise_entity_api_bp,
        enterprise_crud_bp,
        abacus_consolidation_bp,
        maturity_management,
        acm_bp,
    ]

    for bp in blueprints:
        mark_blueprint_guardrailed(bp)

    # Register all blueprints
    app.register_blueprint(capability_map, url_prefix="/capability-map")
    app.register_blueprint(enterprise_entity_api_bp)
    app.register_blueprint(enterprise_crud_bp)
    app.register_blueprint(abacus_consolidation_bp)
    app.register_blueprint(maturity_management)
    app.register_blueprint(acm_bp)

    # Register function-based routes
    from app.modules.capabilities.api.capability_taxonomy_routes import (
        register_capability_taxonomy_routes,
    )

    register_capability_taxonomy_routes(app)

    app.logger.info(
        "[MODULE-V2] capabilities v2 registered (guardrail-enabled, 141 routes, 7 blueprints)"
    )
