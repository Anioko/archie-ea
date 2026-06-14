"""
Dashboard module -- Overview dashboards, generators, and enterprise service UIs.

Migrated from:
- app/dashboard/views.py (17 routes, "dashboard" blueprint)
- app/dashboard/routes.py (9 routes, "dashboard_api" blueprint, nested in dashboard)
- app/api/dashboard_routes.py (40 routes, "dashboard_pages" blueprint)

Total: 66 routes across 3 blueprints.
"""
from flask import Flask


def register(app: Flask) -> None:
    from .routes.dashboard_views import dashboard_bp
    from .routes.dashboard_pages_routes import dashboard_pages_bp

    # dashboard_api is nested inside dashboard_bp (done in dashboard_views.py)
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    # dashboard_pages is registered separately
    app.register_blueprint(dashboard_pages_bp)

    app.logger.info("[MODULE] dashboard registered (66 routes, 3 blueprints)")
