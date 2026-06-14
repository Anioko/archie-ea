"""
Application factory — slim orchestrator.

All heavy lifting is delegated to ``app._bootstrap.*`` helpers so that this
file stays small and easy to reason about.  Backward-compatible re-exports
of Flask extension instances are kept at module level.
"""

import logging
import os

logger = logging.getLogger(__name__)

# All extension instances live in app/extensions/__init__.py.
# Re-exported here for backward compatibility (from app import csrf, db, ...).
from app.extensions import compress, csrf, db, login_manager, mail  # noqa: F401

# Import appropriate config based on environment
if os.environ.get("FLASK_CONFIG") == "codespaces":
    from config_codespaces import config as Config
else:
    from config import config as Config


def create_app(config=None):
    from flask import Flask

    from app._bootstrap.assets import init_assets
    from app._bootstrap.blueprints import init_blueprints
    from app._bootstrap.cli import init_cli
    from app._bootstrap.context_processors import init_context_processors
    from app._bootstrap.extensions import init_extensions, init_scheduler
    from app._bootstrap.routes import init_inline_routes
    from app._bootstrap.security import init_security
    from app._bootstrap.services import init_services
    from app._bootstrap.swagger import init_swagger

    app = Flask(__name__)

    if config is None or not isinstance(config, str):
        config_name = os.getenv("FLASK_CONFIG", "default")
    else:
        config_name = config

    app.config.from_object(Config[config_name])
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    Config[config_name].init_app(app)

    # 1. Extensions (db, csrf, mail, login_manager, compress, migrate, rq, cache)
    init_extensions(app)

    # 1a. Background scheduler (APScheduler for EA workflow schedules)
    init_scheduler(app)

    # 1b. Multi-tenancy: tenant context (before_request) + query isolation (ORM events)
    from app.middleware.tenant_context import install_tenant_context
    from app.middleware.tenant_isolation import install_tenant_filter
    install_tenant_context(app)
    install_tenant_filter(app)

    # 1c. Usage metering: non-blocking after_request event recording
    from app.middleware.usage_tracking import install_usage_tracking
    install_usage_tracking(app)

    # 1d. PostHog product analytics: auto-pageview tracking (COM-013)
    from app.middleware.analytics_middleware import install_analytics
    install_analytics(app)

    # 1d. SOC 2 audit logging: SQLAlchemy mapper events for controlled models
    from app.middleware.audit_middleware import install_audit_logging
    install_audit_logging(app)

    # 2. Security headers, guardrails, batch config
    init_security(app)

    # 3. Inline routes (health check, API auth endpoints)
    init_inline_routes(app, config_name)

    # 4. Template utilities and context processors
    init_context_processors(app)

    # 5. Asset pipeline (Flask-Assets)
    init_assets(app)

    # 6. Services (SSL, LLM validation, error handlers, template filters,
    #              job queue, audit, prometheus, LLM health check)
    init_services(app, config_name)

    # 7. All blueprints and feature-flagged modules
    init_blueprints(app)

    # 7a. Solution AI Prompt admin (separate from admin_routes.py to survive deploys)
    try:
        from app.modules.admin.routes.solution_prompt_admin import solution_prompt_admin_bp
        app.register_blueprint(solution_prompt_admin_bp)
    except Exception as e:
        app.logger.warning("Solution Prompt Admin blueprint failed: %s", e)

    # 7b. Code Workbench — registered in _bootstrap/blueprints.py (removed duplicate)

    # 8. OpenAPI/Swagger documentation (feature-flagged)
    init_swagger(app)

    # 9. CLI commands (seed, archimate, capabilities, ACM, feature flags, vendors)
    init_cli(app)

    # 10. Startup endpoint validation — catches template url_for() regressions at boot
    _validate_critical_endpoints(app)

    # 10b. OPS-003: self-heal the shared admin password to the configured
    # ADMIN_PASSWORD on every boot (corrects multi-agent rotation drift).
    try:
        from app._bootstrap.admin_bootstrap import reconcile_admin_password
        reconcile_admin_password(app)
    except Exception as _adm_exc:  # noqa: BLE001 — never block boot
        app.logger.warning("admin password reconciliation skipped: %s", _adm_exc)

    # 11. Global session teardown — prevent InFailedSqlTransaction cascading across requests
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        from app import db as _db
        if exception:
            _db.session.rollback()
        _db.session.remove()

    return app


def _validate_critical_endpoints(app):
    """Warn at startup if any endpoint referenced by core templates is missing.

    Templates reference these endpoints via url_for() inside admin_base.html /
    admin_sidebar.html — a missing registration silently breaks every admin page.
    This check surfaces the problem immediately at boot rather than on first request.
    """
    REQUIRED_ENDPOINTS = [
        "dashboard.health_scorecard",
        "dashboard_pages.rationalization_scorecard",
        "unified_applications.application_list",
    ]
    with app.app_context():
        missing = [ep for ep in REQUIRED_ENDPOINTS if ep not in app.view_functions]
        if missing:
            app.logger.warning(
                "[STARTUP] Missing critical endpoints (url_for will fail at runtime): %s",
                missing,
            )
