"""
Health Check Routes (migrated).

Thin route layer — all business logic lives in HealthService.

Migrated from: app/routes/health_routes.py
URL prefix preserved: /api/health

Endpoints:
- /api/health            — Overall system health
- /api/health/database   — Database connectivity
- /api/health/storage    — File system access
- /api/health/cache      — Redis/cache status
- /api/health/llm        — LLM service status
- /api/health/external   — External services status
- /api/health/vendors    — Vendor subsystem health
- /api/health/ready      — Kubernetes readiness probe
- /api/health/live       — Kubernetes liveness probe
"""
from datetime import datetime

from flask import Blueprint, jsonify
from sqlalchemy import text

from app.extensions import db
from ..services.health_service import HealthService

health_bp = Blueprint("health", __name__, url_prefix="/api/health")

_svc = HealthService()


@health_bp.route("", methods=["GET"])
def health_check():
    """Overall system health check."""
    payload, http_status = _svc.full_check()
    return jsonify(payload), http_status


@health_bp.route("/database", methods=["GET"])
def database_health():
    """Database-specific health check."""
    result = _svc.check_database()
    http_status = 200 if result["status"] == "healthy" else 503
    return jsonify(result), http_status


@health_bp.route("/storage", methods=["GET"])
def storage_health():
    """Storage-specific health check."""
    result = _svc.check_storage()
    http_status = 200 if result["status"] == "healthy" else 503
    return jsonify(result), http_status


@health_bp.route("/cache", methods=["GET"])
def cache_health():
    """Cache/Redis health check."""
    result = _svc.check_cache()
    http_status = 503 if result["status"] == "unhealthy" else 200
    return jsonify(result), http_status


@health_bp.route("/llm", methods=["GET"])
def llm_health():
    """LLM service health check."""
    result = _svc.check_llm()
    http_status = 200 if result["status"] == "healthy" else 503
    return jsonify(result), http_status


@health_bp.route("/external", methods=["GET"])
def external_health():
    """External services health check."""
    services = _svc.check_external_services()
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": services,
    })


@health_bp.route("/vendors", methods=["GET"])
def vendor_health():
    """Vendor subsystem health check."""
    result = _svc.check_vendors()
    http_status = 503 if result["status"] == "unhealthy" else 200
    return jsonify(result), http_status


@health_bp.route("/ready", methods=["GET"])
def readiness_check():
    """Kubernetes-style readiness probe."""
    try:
        db.session.execute(text("SELECT 1"))  # tenant-exempt: health check
        db.session.commit()
        return jsonify(
            {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
        ), 200
    except Exception as exc:
        return jsonify(
            {"status": "not_ready", "timestamp": datetime.utcnow().isoformat(), "error": str(exc)}
        ), 503


@health_bp.route("/live", methods=["GET"])
def liveness_check():
    """Kubernetes-style liveness probe."""
    return jsonify(
        {"status": "alive", "timestamp": datetime.utcnow().isoformat()}
    ), 200
