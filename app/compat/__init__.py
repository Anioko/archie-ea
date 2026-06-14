"""
Compatibility package — deprecation wrappers and redirect handlers.

During migration, old URLs are preserved via compatibility wrappers that
add deprecation headers, logging, and usage tracking without changing
any legacy behavior.

Modules (13 total):
- **monitoring** — wraps legacy health_bp and metrics_bp
- **account** — wraps legacy account blueprint
- **admin** — wraps legacy admin, sidebar_mgmt, deprecation blueprints
- **dashboard** — wraps legacy dashboard and dashboard_pages blueprints
- **vendors** — wraps legacy vendor API blueprints
- **duplicate_detection** — wraps legacy dedupe blueprints
- **import_batch** — wraps legacy batch import blueprints
- **governance** — wraps legacy governance blueprints
- **architecture** — wraps legacy architecture blueprints
- **capabilities** — wraps legacy capability blueprints
- **ai_chat** — wraps legacy AI chat blueprints
- **applications** — wraps legacy applications blueprints
- **solutions_strategic** — wraps legacy solutions/strategic blueprints

All wrappers add:
- ``X-Deprecated`` response header with migration pointer
- ``X-Migrate-To`` response header with the v2 flag name
- Structured WARNING log on each hit
- Thread-safe hit counter per endpoint

Usage in app/__init__.py:
    from app.compat import register_compat_redirects
    register_compat_redirects(app)
"""
from flask import Flask


_COMPAT_STATS_MODULES = [
    ("monitoring", "MonitoringCompatStats"),
    ("admin", "AdminCompatStats"),
    ("account", "AccountCompatStats"),
    ("dashboard", "DashboardCompatStats"),
    ("vendors", "VendorsCompatStats"),
    ("duplicate_detection", "DedupeCompatStats"),
    ("import_batch", "ImportBatchCompatStats"),
    ("governance", "GovernanceCompatStats"),
    ("architecture", "ArchitectureCompatStats"),
    ("capabilities", "CapabilitiesCompatStats"),
    ("ai_chat", "AIChatCompatStats"),
    ("applications", "ApplicationsCompatStats"),
    ("solutions_strategic", "SolutionsStrategicCompatStats"),
]


def register_compat_redirects(app: Flask) -> None:
    """Register all compatibility stats endpoints.

    Call this from create_app() AFTER registering new modules.
    Only active during migration — remove after Phase 10 cleanup.

    Args:
        app: Flask application instance.
    """
    import importlib

    from flask import jsonify

    registered = 0
    for mod_name, stats_cls_name in _COMPAT_STATS_MODULES:
        try:
            mod = importlib.import_module(f".{mod_name}", package="app.compat")
            stats_cls = getattr(mod, stats_cls_name)

            endpoint_name = f"_compat_{mod_name}_stats"
            url = f"/api/compat/{mod_name.replace('_', '-')}/stats"

            def _make_handler(cls):
                def handler():
                    return jsonify(cls.get_stats())
                handler.__name__ = f"compat_{mod_name}_stats"
                return handler

            app.add_url_rule(url, endpoint=endpoint_name, view_func=_make_handler(stats_cls))
            registered += 1
        except Exception:
            pass

    app.logger.info("[COMPAT] Compatibility layer registered (%d stats endpoints)", registered)
