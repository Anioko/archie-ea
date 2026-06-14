"""
In-process request metrics collector.

Tracks request counts, latency percentiles, and error rates per endpoint.
Data is held in-memory (thread-safe) and can be read via ``get_summary()``.

This is intentionally simple — no external dependencies (Prometheus, StatsD).
Wire to an external backend by subclassing or reading ``get_summary()``.

Usage::

    from app.core.observability.metrics import metrics_collector

    # In before_request / after_request hooks:
    metrics_collector.record(request.endpoint, response.status_code, duration_ms)

    # Read aggregated data:
    summary = metrics_collector.get_summary()
"""

import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional


class MetricsCollector:
    """Thread-safe in-memory request metrics."""

    def __init__(self, max_latencies: int = 1000):
        self._lock = threading.Lock()
        self._max_latencies = max_latencies
        self._counts: Dict[str, int] = defaultdict(int)
        self._errors: Dict[str, int] = defaultdict(int)
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._start_time = time.time()

    def record(
        self,
        endpoint: Optional[str],
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record a single request metric."""
        key = endpoint or "unknown"
        with self._lock:
            self._counts[key] += 1
            if status_code >= 400:
                self._errors[key] += 1
            lats = self._latencies[key]
            lats.append(duration_ms)
            if len(lats) > self._max_latencies:
                self._latencies[key] = lats[-self._max_latencies:]

    def get_summary(self) -> Dict[str, Any]:
        """Return aggregated metrics snapshot."""
        with self._lock:
            total_requests = sum(self._counts.values())
            total_errors = sum(self._errors.values())

            endpoints = {}
            for key in self._counts:
                lats = sorted(self._latencies.get(key, []))
                endpoints[key] = {
                    "requests": self._counts[key],
                    "errors": self._errors[key],
                    "error_rate": round(self._errors[key] / max(self._counts[key], 1), 4),
                    "p50_ms": _percentile(lats, 50),
                    "p95_ms": _percentile(lats, 95),
                    "p99_ms": _percentile(lats, 99),
                }

            return {
                "uptime_seconds": round(time.time() - self._start_time, 1),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "overall_error_rate": round(total_errors / max(total_requests, 1), 4),
                "endpoints": endpoints,
            }

    def reset(self) -> None:
        """Clear all collected metrics."""
        with self._lock:
            self._counts.clear()
            self._errors.clear()
            self._latencies.clear()
            self._start_time = time.time()


def _percentile(sorted_values: List[float], pct: int) -> float:
    """Compute *pct*-th percentile from a pre-sorted list."""
    if not sorted_values:
        return 0.0
    idx = int(len(sorted_values) * pct / 100)
    idx = min(idx, len(sorted_values) - 1)
    return round(sorted_values[idx], 2)


metrics_collector = MetricsCollector()
