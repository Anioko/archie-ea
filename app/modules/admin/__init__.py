"""
Admin module - User management, API settings, feature flags, and system administration.

Migrated from:
- app/admin/views.py (38 route decorators, 1853 lines)
- app/admin/sidebar_mgmt_routes.py (5 routes, sidebar_mgmt_bp)
- app/routes/admin/deprecation_routes.py (7 routes, deprecation_bp)
- app/admin/forms.py (6 WTForms classes)

Blueprints preserved:
- "admin" (url_prefix=/admin)
- "sidebar_mgmt" (url_prefix=/api/admin/sidebar)
- "deprecation" (url_prefix=/admin/deprecation)
"""
from flask import Flask


def register(app: Flask) -> None:
    """Register all admin module blueprints with the Flask app.

    Args:
        app: Flask application instance.
    """
    from .routes.admin_routes import admin_bp
    from .routes.sidebar_mgmt_routes import sidebar_mgmt_bp
    from .routes.deprecation_routes import deprecation_bp
    from .billing_routes import billing_bp
    from .team_routes import team_bp
    # user_role_bp was defined but never registered. Its own comment said "this
    # will be imported by admin_routes" and nothing ever imported it, so
    # /admin/user/<id>/role did not exist and a platform admin could not assign
    # an enterprise_role at all. That column drives the sidebar, the dashboard
    # cards and the permission checks, so the feature that onboards a team was
    # unreachable in the running app.
    from .routes.user_role_routes import user_role_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(sidebar_mgmt_bp)
    app.register_blueprint(deprecation_bp)
    app.register_blueprint(billing_bp, url_prefix="/admin/billing")
    app.register_blueprint(team_bp, url_prefix="/admin")
    app.register_blueprint(user_role_bp, url_prefix="/admin")

    app.logger.info("[MODULE] admin registered (58 routes, 5 blueprints)")
