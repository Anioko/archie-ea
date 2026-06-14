"""
Core observability package.

Provides structured logging and metrics collection for new modular endpoints.
Legacy modules are unaffected — observability hooks are opt-in via decorators.

Modules:
- logging: Structured request/response logging with correlation IDs
- metrics: In-process request metrics (latency, error rates)

Usage::

    from app.core.observability import request_logger, metrics_collector
    from app.core.observability.logging import StructuredLogger
    from app.core.observability.metrics import MetricsCollector
"""

from .logging import StructuredLogger, request_logger
from .metrics import MetricsCollector, metrics_collector

__all__ = [
    "StructuredLogger",
    "request_logger",
    "MetricsCollector",
    "metrics_collector",
]
