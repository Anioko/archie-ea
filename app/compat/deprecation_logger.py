"""
Shared deprecation logging and usage tracking for the compatibility layer.

Provides ``CompatStats`` — a thread-safe hit counter base class that tracks
per-endpoint call counts and last-hit timestamps so operators can verify
zero traffic before removing legacy code.

Usage in per-module compat files::

    from app.compat.deprecation_logger import CompatStats

    class MonitoringCompatStats(CompatStats):
        pass

Each subclass gets its own independent counters via ``__init_subclass__``.
"""

import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict


class CompatStats:
    """Thread-safe hit counter base class for legacy endpoint tracking.

    Each subclass automatically gets its own independent state (lock, hits,
    timestamps) via ``__init_subclass__``, so modules don't share counters.

    Interface (all classmethods):
        - ``record(endpoint)`` — increment hit count for an endpoint
        - ``get_stats()`` — return dict with uptime, total hits, per-endpoint breakdown
        - ``reset()`` — clear all counters (useful in tests)
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._lock = threading.Lock()
        cls._hits: Dict[str, int] = defaultdict(int)
        cls._last_hit: Dict[str, str] = {}
        cls._start_time: float = time.time()

    @classmethod
    def record(cls, endpoint: str) -> None:
        """Record a hit on a legacy endpoint."""
        with cls._lock:
            cls._hits[endpoint] += 1
            cls._last_hit[endpoint] = datetime.utcnow().isoformat()

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Return usage statistics for this module's legacy endpoints."""
        with cls._lock:
            return {
                "uptime_seconds": round(time.time() - cls._start_time, 1),
                "total_legacy_hits": sum(cls._hits.values()),
                "endpoints": {
                    ep: {"hits": cls._hits[ep], "last_hit": cls._last_hit.get(ep)}
                    for ep in sorted(cls._hits)
                },
            }

    @classmethod
    def reset(cls) -> None:
        """Clear all counters (primarily for test isolation)."""
        with cls._lock:
            cls._hits.clear()
            cls._last_hit.clear()
            cls._start_time = time.time()
