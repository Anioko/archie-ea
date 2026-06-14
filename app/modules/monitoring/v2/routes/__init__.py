"""Monitoring v2 route blueprints."""

from .health_routes import health_bp_v2
from .metrics_routes import metrics_bp_v2

__all__ = ["health_bp_v2", "metrics_bp_v2"]
