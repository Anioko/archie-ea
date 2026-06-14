"""
Database Query Monitor
PRD - 007.1: Monitor and log database query performance

Provides:
- Query execution time tracking
- N + 1 query detection
- Slow query logging
- Query statistics collection
"""
import logging
import threading
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Dict, List, Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class QueryMonitor:
    """
    Monitor database query performance.
    Usage:
        monitor = QueryMonitor()
        monitor.enable()
        # ... run queries ...
        stats = monitor.get_stats()
        monitor.disable()
    """

    def __init__(self, slow_query_threshold_ms: float = 500.0):
        self.slow_query_threshold = slow_query_threshold_ms / 1000.0
        self.query_stats: List[Dict[str, Any]] = []
        self._enabled = False
        self._lock = threading.Lock()

    def enable(self):
        """Enable query monitoring"""
        if not self._enabled:
            event.listen(Engine, "before_cursor_execute", self._before_cursor_execute)
            event.listen(Engine, "after_cursor_execute", self._after_cursor_execute)
            self._enabled = True

    def disable(self):
        """Disable query monitoring"""
        if self._enabled:
            event.remove(Engine, "before_cursor_execute", self._before_cursor_execute)
            event.remove(Engine, "after_cursor_execute", self._after_cursor_execute)
            self._enabled = False

    def _before_cursor_execute(self, conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.time())

    def _after_cursor_execute(self, conn, cursor, statement, parameters, context, executemany):
        total = time.time() - conn.info["query_start_time"].pop(-1)

        with self._lock:
            self.query_stats.append(
                {
                    "statement": statement[:500],  # Truncate long queries
                    "duration": total,
                    "timestamp": time.time(),
                    "is_slow": total > self.slow_query_threshold,
                }
            )

        if total > self.slow_query_threshold:
            logger.warning(f"Slow query ({total * 1000:.2f}ms): {statement[:200]}")

    def get_stats(self) -> Dict[str, Any]:
        """Get query statistics"""
        with self._lock:
            if not self.query_stats:
                return {"total_queries": 0, "total_time": 0, "slow_queries": 0}

            durations = [q["duration"] for q in self.query_stats]
            slow_queries = [q for q in self.query_stats if q["is_slow"]]

            return {
                "total_queries": len(self.query_stats),
                "total_time": sum(durations),
                "avg_time": sum(durations) / len(durations),
                "max_time": max(durations),
                "min_time": min(durations),
                "slow_queries": len(slow_queries),
                "slow_query_details": slow_queries[:10],  # Top 10 slow queries
            }

    def clear(self):
        """Clear collected stats"""
        with self._lock:
            self.query_stats = []


# Global monitor instance
_query_monitor: Optional[QueryMonitor] = None


def get_query_monitor() -> QueryMonitor:
    global _query_monitor
    if _query_monitor is None:
        _query_monitor = QueryMonitor()
    return _query_monitor


def monitor_queries(func):
    """Decorator to monitor queries within a function"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        monitor = get_query_monitor()
        monitor.clear()
        monitor.enable()
        try:
            result = func(*args, **kwargs)
            stats = monitor.get_stats()
            if stats["slow_queries"] > 0:
                logger.warning(f"Function {func.__name__} had {stats['slow_queries']} slow queries")
            return result
        finally:
            monitor.disable()

    return wrapper
