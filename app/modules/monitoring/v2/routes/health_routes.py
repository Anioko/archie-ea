"""
Health Check Routes v2 — guardrail-enabled.

Uses the new architecture:
- Standardized api_success/api_error responses
- @timed_route for automatic metrics collection
- Observability (request_id in responses)
- Consistent error handling via exception mappers

URL prefix preserved: /api/health (same as v1)
Blueprint name: health_v2 (distinct from v1 to allow coexistence)
"""

from datetime import datetime

from flask import Blueprint, jsonify
from flask_login import current_user, login_required  # dead-code-ok
from sqlalchemy import text

from app.core.api import api_error, api_success
from app.core.compat import mark_blueprint_guardrailed
from app.core.decorators import timed_route
from app.extensions import db
from app.modules.monitoring.services.health_service import HealthService

health_bp_v2 = Blueprint("health_v2", __name__, url_prefix="/api/health")
mark_blueprint_guardrailed(health_bp_v2)

_svc = HealthService()


@health_bp_v2.route("", methods=["GET"])
@login_required
@timed_route
def health_check():
    """Overall system health check — requires authentication.

    Returns full component-level details only to authenticated users
    to prevent infrastructure fingerprinting (ISS-003).
    """
    payload, http_status = _svc.full_check()
    if http_status >= 500:
        return api_error(
            payload.get("status", "unhealthy"),
            status_code=http_status,
            errors=payload.get("components"),
        )
    return api_success(payload, status_code=http_status)


@health_bp_v2.route("/database", methods=["GET"])
@login_required
@timed_route
def database_health():
    """Database-specific health check — requires authentication (ISS-003)."""
    result = _svc.check_database()
    status_code = 200 if result["status"] == "healthy" else 503
    return api_success(result, status_code=status_code)


@health_bp_v2.route("/storage", methods=["GET"])
@login_required
@timed_route
def storage_health():
    """Storage-specific health check — requires authentication (ISS-003)."""
    result = _svc.check_storage()
    status_code = 200 if result["status"] == "healthy" else 503
    return api_success(result, status_code=status_code)


@health_bp_v2.route("/cache", methods=["GET"])
@login_required
@timed_route
def cache_health():
    """Cache/Redis health check — requires authentication (ISS-003)."""
    result = _svc.check_cache()
    status_code = 200 if result["status"] != "unhealthy" else 503
    return api_success(result, status_code=status_code)


@health_bp_v2.route("/llm", methods=["GET"])
@login_required
@timed_route
def llm_health():
    """LLM service health check — requires authentication (ISS-003)."""
    result = _svc.check_llm()
    status_code = 200 if result["status"] == "healthy" else 503
    return api_success(result, status_code=status_code)


@health_bp_v2.route("/external", methods=["GET"])
@login_required
@timed_route
def external_health():
    """External services health check — requires authentication (ISS-003)."""
    services = _svc.check_external_services()
    return api_success(
        {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": services,
        }
    )


@health_bp_v2.route("/vendors", methods=["GET"])
@login_required
@timed_route
def vendor_health():
    """Vendor subsystem health check — requires authentication (ISS-003)."""
    result = _svc.check_vendors()
    status_code = 200 if result["status"] != "unhealthy" else 503
    return api_success(result, status_code=status_code)


@health_bp_v2.route("/ready", methods=["GET"])
@timed_route
def readiness_check():
    """Kubernetes-style readiness probe."""
    try:
        db.session.execute(text("SELECT 1"))  # tenant-exempt: health check
        db.session.commit()
        return jsonify(
            {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ), 200
    except Exception:
        return jsonify(
            {
                "status": "not_ready",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ), 503


@health_bp_v2.route("/live", methods=["GET"])
@timed_route
def liveness_check():
    """Kubernetes-style liveness probe."""
    return jsonify(
        {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat(),
        }
    ), 200
