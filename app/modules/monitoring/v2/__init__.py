"""
Monitoring v2 — Full guardrail-enabled module using new architecture.

Strangler Fig migration from app/modules/monitoring/ (v1).
Uses:
- app.core.decorators (guarded_route, timed_route)
- app.core.api (api_success, api_error)
- app.core.observability (request_logger, metrics_collector)
- app.core.compat (mark_blueprint_guardrailed)
- app.core.validation (schemas)

Feature flag: USE_MONITORING_V2
Fallback: v1 routes (unchanged)

Rollback: Set USE_MONITORING_V2=false → v1 routes take over instantly.
"""

from flask import Flask


def register(app: Flask) -> None:
    """Register the monitoring v2 module."""
    from .routes import health_bp_v2, metrics_bp_v2

    app.register_blueprint(health_bp_v2)
    app.register_blueprint(metrics_bp_v2)

    app.logger.info("[MODULE-V2] monitoring v2 registered (guardrail-enabled)")
