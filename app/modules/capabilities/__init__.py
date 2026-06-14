"""
Capabilities module -- Centralized capability blueprint registration.

Phase 4 decomposition: capability_map_routes.py (6,562 lines) split into 9 focused
route files sharing the ``capability_map`` Blueprint. Other 6 blueprints moved as-is.

Consolidates 7 blueprints behind USE_NEW_CAPABILITIES feature flag:
- capability_map    (67 routes, decomposed into 9 files)
- enterprise_api    (5 routes)
- enterprise_crud   (13 routes)
- abacus_consolidation (7 routes)
- maturity_management  (9 routes)
- capability_taxonomy  (10 routes, function-registered)
- acm                  (18 routes)

Total: 129+ routes across 7 blueprints.
"""

import logging

from flask import Flask

logger = logging.getLogger(__name__)


def register(app: Flask) -> None:
    from app import csrf

    # --- 1. Capability Map (decomposed monolith — single blueprint, 9 files) ---
    from .routes import capability_map

    app.register_blueprint(capability_map, url_prefix="/capability-map")
    app.logger.info(
        "[BLUEPRINT] Capability Map registered at /capability-map (decomposed)"
    )

    # --- 2. Enterprise Entity API (Unified Mapping Modal support) ---
    from .routes.enterprise_api_routes import (
        enterprise_api_bp as enterprise_entity_api_bp,
    )

    app.register_blueprint(enterprise_entity_api_bp)
    app.logger.info("[BLUEPRINT] Enterprise Entity API registered at /api/enterprise")

    # --- 3. Enterprise CRUD (capability and compliance management) ---
    from .routes.enterprise_crud_routes import enterprise_crud_bp

    app.register_blueprint(enterprise_crud_bp)
    app.logger.info("[BLUEPRINT] Enterprise CRUD registered at /enterprise")

    # --- 4. Abacus Capability Consolidation ---
    try:
        from .routes.abacus_consolidation import bp as abacus_consolidation_bp

        app.register_blueprint(abacus_consolidation_bp)
        app.logger.info(
            "[BLUEPRINT] Abacus Consolidation registered at /admin/abacus/consolidation"
        )
    except ImportError as e:
        app.logger.warning(f"Abacus Consolidation blueprint not available: {e}")

    # --- 5. Capability Maturity Management ---
    from .routes.maturity_routes import maturity_management

    app.register_blueprint(maturity_management)

    # --- 6. Capability Taxonomy API ---
    try:
        from .api.capability_taxonomy_routes import (
            register_capability_taxonomy_routes,
        )

        register_capability_taxonomy_routes(app)
        app.logger.info("[API] Capability taxonomy routes registered")
    except Exception as e:
        app.logger.warning(f"[API] Failed to register capability taxonomy routes: {e}")

    # --- 7. ACM (Application Capability Model) API ---
    try:
        from .api.acm_routes import acm_bp

        app.register_blueprint(acm_bp)
        app.logger.info("[API] ACM Technical Capability API registered at /api/acm")
    except Exception as e:
        app.logger.warning(f"[API] Failed to register ACM routes: {e}")

    app.logger.info("[MODULE] capabilities registered (7 blueprints, decomposed)")
