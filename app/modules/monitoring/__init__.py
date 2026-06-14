"""
Monitoring module — Health checks, metrics, and system monitoring.

Migrated from:
- app/routes/health_routes.py (9 routes)
- app/routes/metrics_routes.py (3 routes)

URL prefixes preserved:
- /api/health/*   (health checks, k8s probes)
- /metrics        (Prometheus scraping)
- /debug/metrics  (human-readable metrics)
"""
from flask import Flask


def register(app: Flask) -> None:
    """Register the monitoring module with the Flask app.

    Args:
        app: Flask application instance.
    """
    from .routes.health_routes import health_bp
    from .routes.metrics_routes import metrics_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(metrics_bp)

    app.logger.info("[MODULE] monitoring registered (health + metrics)")
