"""
Health Check Routes

Provides comprehensive health check endpoints for monitoring system status.
"""

import logging
import time
from datetime import datetime, timedelta  # dead-code-ok
from flask import Blueprint, jsonify, current_app

from app import db
from app.monitoring.metrics_service import MetricsService
from app.monitoring.security_monitoring import SecurityMonitoringService
from app.models.feature_flags import FeatureFlag

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/monitoring")


@monitoring_bp.route("/health", methods=["GET"])
def health_check():
    """
    Basic health check endpoint.

    Returns minimal health status for load balancers and basic monitoring.
    """
    try:
        # Check database connection
        db.session.execute(db.text("SELECT 1"))  # tenant-exempt: health check
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    # Check application status
    app_status = "healthy" if db_status == "healthy" else "unhealthy"

    return jsonify(
        {
            "status": app_status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": current_app.config.get("VERSION", "unknown"),
            "checks": {"database": db_status},
        }
    ), 200 if app_status == "healthy" else 503


@monitoring_bp.route("/health/detailed", methods=["GET"])
def detailed_health_check():
    """
    Detailed health check endpoint.

    Returns comprehensive health status for all system components.
    """
    start_time = time.time()
    health_results = {}

    # Database health
    try:
        db_start = time.time()
        db.session.execute(db.text("SELECT 1"))  # tenant-exempt: health check
        db_time = (time.time() - db_start) * 1000

        # Check table counts
        tables = {}
        try:
            result = db.session.execute(  # tenant-exempt: health check
            """
                SELECT table_name, row_count
                FROM (
                    SELECT 'application_components' as table_name, COUNT(*) as row_count FROM application_components
                    UNION ALL
                    SELECT 'vendor_organizations' as table_name, COUNT(*) as row_count FROM vendor_organizations
                    UNION ALL
                    SELECT 'unified_capabilities' as table_name, COUNT(*) as row_count FROM unified_capabilities
                ) as counts
            """)
            for row in result:
                tables[row[0]] = row[1]
        except Exception as e:
            logger.warning(f"Table count check failed: {e}")

        health_results["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_time, 2),
            "tables": tables,
        }
    except Exception as e:
        logger.error(f"Database detailed health check failed: {e}")
        health_results["database"] = {"status": "unhealthy", "error": str(e)}

    # File system health
    try:
        import os

        upload_dir = current_app.config.get("UPLOAD_FOLDER", "app/uploads")
        if os.path.exists(upload_dir):
            free_space = (
                os.statvfs(upload_dir).f_bavail * os.statvfs(upload_dir).f_frsize
            )
            health_results["filesystem"] = {
                "status": "healthy",
                "upload_directory": upload_dir,
                "free_space_bytes": free_space,
                "free_space_gb": round(free_space / (1024**3), 2),
            }
        else:
            health_results["filesystem"] = {
                "status": "unhealthy",
                "error": f"Upload directory {upload_dir} does not exist",
            }
    except Exception as e:
        logger.error(f"Filesystem health check failed: {e}")
        health_results["filesystem"] = {"status": "unhealthy", "error": str(e)}

    # Memory usage
    try:
        import psutil

        memory = psutil.virtual_memory()
        health_results["memory"] = {
            "status": "healthy" if memory.percent < 90 else "warning",
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "percent_used": memory.percent,
        }
    except Exception as e:
        logger.warning(f"Memory health check failed: {e}")
        health_results["memory"] = {"status": "unknown", "error": str(e)}

    # External services health
    health_results["external_services"] = {}

    # LLM Service health
    try:
        from app.services.llm_service import LLMService

        llm_service = LLMService()
        # Try to get available providers
        providers = llm_service.get_available_providers()
        health_results["external_services"]["llm"] = {
            "status": "healthy" if providers else "warning",
            "available_providers": len(providers),
            "providers": list(providers.keys()) if providers else [],
        }
    except Exception as e:
        logger.warning(f"LLM service health check failed: {e}")
        health_results["external_services"]["llm"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Calculate overall status
    all_statuses = []
    for category, checks in health_results.items():
        if isinstance(checks, dict) and "status" in checks:
            all_statuses.append(checks["status"])

    if "unhealthy" in all_statuses:
        overall_status = "unhealthy"
        status_code = 503
    elif "warning" in all_statuses:
        overall_status = "warning"
        status_code = 200
    else:
        overall_status = "healthy"
        status_code = 200

    response_time = (time.time() - start_time) * 1000

    return jsonify(
        {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "response_time_ms": round(response_time, 2),
            "checks": health_results,
        }
    ), status_code


@monitoring_bp.route("/metrics", methods=["GET"])
def get_metrics():
    """
    Metrics endpoint for Prometheus-style monitoring.

    Returns system metrics in Prometheus format.
    """
    try:
        metrics_service = MetricsService()
        metrics = metrics_service.get_all_metrics()

        # Convert to Prometheus format
        prometheus_metrics = []

        for metric_name, metric_data in metrics.items():
            if isinstance(metric_data, dict):
                if "value" in metric_data:
                    # Simple gauge metric
                    prometheus_metrics.append(
                        f"# HELP {metric_name} {metric_data.get('help', metric_name)}\n"
                        f"# TYPE {metric_name} gauge\n"
                        f"{metric_name} {metric_data['value']}"
                    )
                elif "count" in metric_data and "rate" in metric_data:
                    # Counter with rate
                    prometheus_metrics.append(
                        f"# HELP {metric_name} {metric_data.get('help', metric_name)}\n"
                        f"# TYPE {metric_name} counter\n"
                        f"{metric_name}_total {metric_data['count']}\n"
                        f"{metric_name}_rate {metric_data['rate']}"
                    )

        return "\n\n".join(prometheus_metrics), 200, {"Content-Type": "text/plain"}

    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        return jsonify({"error": "Failed to collect metrics"}), 500


@monitoring_bp.route("/alerts", methods=["GET"])
def get_alerts():
    """
    Get active alerts.

    Returns list of active alerts and their status.
    """
    try:
        alerting_service = AlertingService()
        alerts = alerting_service.get_active_alerts()

        return jsonify(
            {
                "alerts": alerts,
                "count": len(alerts),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Alerts endpoint failed: {e}")
        return jsonify({"error": "Failed to get alerts"}), 500


@monitoring_bp.route("/security-events", methods=["GET"])
def get_security_events():
    """
    Get recent security events.

    Returns list of recent security events for monitoring.
    """
    try:
        security_service = SecurityMonitoringService()
        events = security_service.get_recent_events(limit=100)

        return jsonify(
            {
                "events": events,
                "count": len(events),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Security events endpoint failed: {e}")
        return jsonify({"error": "Failed to get security events"}), 500


@monitoring_bp.route("/feature-flags/cache", methods=["GET"])
def get_feature_flag_cache_metrics():
    """
    Get feature flag cache performance metrics.

    Returns:
        JSON with cache statistics including hit rate, size, and request counts
    """
    try:
        metrics = FeatureFlag.get_cache_metrics()

        return jsonify(
            {
                "cache_metrics": metrics,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "healthy" if metrics["hit_rate"] > 0.5 else "warning",
            }
        )

    except Exception as e:
        logger.error(f"Feature flag cache metrics endpoint failed: {e}")
        return jsonify({"error": "Failed to get cache metrics"}), 500
