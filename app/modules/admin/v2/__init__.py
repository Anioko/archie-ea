"""
Admin v2 — Full guardrail-enabled module using new architecture.

Strangler Fig migration from app/modules/admin/ (v1).
Uses:
- app.core.decorators (timed_route)
- app.core.compat (mark_blueprint_guardrailed)

Blueprints preserved (same names as v1 for url_for compatibility):
- "admin" (url_prefix=/admin)
- "sidebar_mgmt" (url_prefix=/api/admin/sidebar)
- "deprecation" (url_prefix=/admin/deprecation)

Feature flag: USE_ADMIN_V2
Fallback: v1 routes (unchanged)

Rollback: Set USE_ADMIN_V2=false → v1 routes take over instantly.
"""

from flask import Flask


def register(app: Flask) -> None:
    """Register the admin v2 module (all 3 blueprints)."""
    from .routes import admin_bp_v2, sidebar_mgmt_bp_v2, deprecation_bp_v2
    from app.modules.admin.connector_routes import m365_connector_bp

    app.register_blueprint(admin_bp_v2, url_prefix="/admin")
    app.register_blueprint(sidebar_mgmt_bp_v2)
    app.register_blueprint(deprecation_bp_v2)
    app.register_blueprint(m365_connector_bp)

    app.logger.info(
        "[MODULE-V2] admin v2 registered (guardrail-enabled, 3 blueprints)"
    )
