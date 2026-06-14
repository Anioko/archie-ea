"""
Dashboard v2 — Full guardrail-enabled module using new architecture.

Strangler Fig migration from app/modules/dashboard/ (v1).
Uses:
- app.core.decorators (timed_route)
- app.core.compat (mark_blueprint_guardrailed)

Blueprints preserved (same names as v1 for url_for compatibility):
- "dashboard" (url_prefix=/dashboard, includes nested "dashboard_api")
- "dashboard_pages" (url_prefix=/dashboard)

Feature flag: USE_DASHBOARD_V2
Fallback: v1 routes (unchanged)

Rollback: Set USE_DASHBOARD_V2=false → v1 routes take over instantly.
"""

from flask import Flask


def register(app: Flask) -> None:
    """Register the dashboard v2 module (2 top-level blueprints)."""
    from app.core.compat import mark_blueprint_guardrailed

    from .routes import dashboard_bp_v2, dashboard_pages_bp_v2

    mark_blueprint_guardrailed(dashboard_bp_v2)
    mark_blueprint_guardrailed(dashboard_pages_bp_v2)

    app.register_blueprint(dashboard_bp_v2, url_prefix="/dashboard")
    app.register_blueprint(dashboard_pages_bp_v2)

    app.logger.info(
        "[MODULE-V2] dashboard v2 registered (guardrail-enabled, 66 routes, 3 blueprints)"
    )
