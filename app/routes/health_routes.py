"""
Health check endpoints for load balancer and Kubernetes liveness/readiness probes.
No authentication required — these must be reachable without a session.
"""
import time
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.services.platform_slo_service import get_platform_slo_status
from app.services.prometheus_metrics import track_http_request_by_rule

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Liveness probe — confirms the Flask process is alive."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "archie",
    }), 200


@health_bp.route("/health/db", methods=["GET"])
def health_db():
    """Readiness probe — confirms DB connectivity is healthy."""
    try:
        db.session.execute(db.text("SELECT 1"))  # tenant-exempt: health check
        return jsonify({
            "status": "ok",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "database": "unreachable",
            "detail": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }), 503


@health_bp.route("/health/slo", methods=["GET"])
def health_slo():
    """Internal platform SLO attainment (TB-0165, REQ-NFR-005).

    Unauthenticated like /health and /health/db — production watch alerts on
    this. Returns only aggregate objective numbers: no organisation names,
    user data or request paths (see app/services/platform_slo_service.py).
    """
    return jsonify(get_platform_slo_status()), 200


def _wire_slo_request_metrics(app):
    """Record every request's method/route/status/duration into the shared
    HTTP counters that ``platform_slo_service`` reads (CLAUDE.md ADR 0008 —
    no second metrics store). ``health_bp`` is registered unconditionally at
    boot (app/_bootstrap/blueprints.py), so this hook fires for the whole
    app, not just this blueprint's own routes.
    """

    @app.before_request
    def _slo_metrics_start():
        g._platform_slo_start = time.monotonic()

    @app.after_request
    def _slo_metrics_record(response):
        start = getattr(g, "_platform_slo_start", None)
        # request.url_rule is None for a 404 (no route matched) — nothing to
        # attribute the sample to, so it is skipped rather than mislabeled.
        if start is not None and request.url_rule is not None:
            duration_seconds = time.monotonic() - start
            track_http_request_by_rule(
                request.method,
                request.url_rule.rule,
                response.status_code,
                duration_seconds,
            )
        return response


health_bp.record_once(lambda state: _wire_slo_request_metrics(state.app))
