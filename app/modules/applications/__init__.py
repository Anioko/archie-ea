"""
Applications module -- Centralized application blueprint registration.

Consolidates registration of 3 application-related blueprints behind a single
feature flag (USE_NEW_APPLICATIONS).

Migrated from:
- app/routes/unified_applications_routes.py    (98 routes, "unified_applications" blueprint)
- app/api/application_merging_routes.py        (5 routes, "application_merging" blueprint)
- app/implementation_planning/                 (26 routes, "implementation_planning" blueprint)

Total: 129 routes across 3 blueprints.

Note: dynamic_dashboards is NOT included here because it is tightly coupled
to the sidebar context processor (MODEL_REGISTRY import).
"""
import logging

from flask import Flask

logger = logging.getLogger(__name__)


def register(app: Flask) -> None:
    # --- 1. Unified Applications (decomposed into 11 sub-files) ---
    from .routes import unified_applications_bp

    app.register_blueprint(unified_applications_bp)

    # --- 2. Application Merging ---
    from app.api.application_merging_routes import merging_bp

    app.register_blueprint(merging_bp)

    # --- 3. Implementation Planning ---
    from app.implementation_planning import implementation_planning

    app.register_blueprint(implementation_planning)

    app.logger.info(
        "[MODULE] applications registered (129 routes, 3 blueprints)"
    )
