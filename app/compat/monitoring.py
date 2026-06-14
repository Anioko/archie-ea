"""
Compatibility wrappers for the monitoring module (legacy -> v2).

Feature-flag gating: USE_MONITORING_COMPAT=true (env) enables the wrappers.
"""

from app.compat.deprecation_logger import CompatStats
from app.compat.feature_flag_gate import make_compat_config
from app.compat.mapping_registry import register_routes
from app.compat.wrapper_generator import make_legacy_wrapper

_config = make_compat_config("monitoring")


class MonitoringCompatStats(CompatStats):
    """Thread-safe hit counter for legacy monitoring endpoints."""
    pass


LEGACY_ROUTE_MAP = {
    "health.health_check":     {"url": "/api/health",          "v2": "health_v2.health_check",     "method": "GET"},
    "health.database_health":  {"url": "/api/health/database", "v2": "health_v2.database_health",  "method": "GET"},
    "health.storage_health":   {"url": "/api/health/storage",  "v2": "health_v2.storage_health",   "method": "GET"},
    "health.cache_health":     {"url": "/api/health/cache",    "v2": "health_v2.cache_health",     "method": "GET"},
    "health.llm_health":       {"url": "/api/health/llm",      "v2": "health_v2.llm_health",       "method": "GET"},
    "health.external_health":  {"url": "/api/health/external", "v2": "health_v2.external_health",  "method": "GET"},
    "health.vendor_health":    {"url": "/api/health/vendors",  "v2": "health_v2.vendor_health",    "method": "GET"},
    "health.readiness_check":  {"url": "/api/health/ready",    "v2": "health_v2.readiness_check",  "method": "GET"},
    "health.liveness_check":   {"url": "/api/health/live",     "v2": "health_v2.liveness_check",   "method": "GET"},
    "metrics.metrics":         {"url": "/metrics",             "v2": "metrics_v2.metrics",         "method": "GET"},
    "metrics.debug_metrics":   {"url": "/debug/metrics",       "v2": "metrics_v2.debug_metrics",   "method": "GET"},
    "metrics.debug_metrics_json": {"url": "/debug/metrics/json", "v2": "metrics_v2.debug_metrics_json", "method": "GET"},
}

register_routes("monitoring", LEGACY_ROUTE_MAP)

wrap_legacy_health_bp = make_legacy_wrapper(_config, MonitoringCompatStats)
wrap_legacy_metrics_bp = make_legacy_wrapper(_config, MonitoringCompatStats)
