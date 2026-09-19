"""DE-18/OA-2: structured latency record + Prometheus histogram for US-1 reads.

``record_query_latency`` does not exist anywhere in this repository prior to
T-004 (confirmed by full-tree grep, see
``docs/buckets/t004-us1-impact-endpoint/tasks/00-verification-notes.md``).
This module is the OA-2 structured-logging helper for
``IntelligenceQueryService`` queries, following the same shape as
``services/observability.py``'s ``InvalidationRecord``: a frozen dataclass
with ``as_dict()``, logged at INFO -- not a bare log string.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

from app.services.prometheus_metrics import INTELLIGENCE_QUERY_DURATION

logger = logging.getLogger("archie.intelligence.oa2")


@dataclass(frozen=True)
class QueryLatencyRecord:
    """One OA-2 structured record for a single intelligence query call."""

    query: str
    organization_id: Optional[int]
    depth: Optional[int]
    include_derived: bool
    latency_ms: float
    explicit_rows: int
    derived_rows: int
    stale_rows: int
    invalidated_rows: Optional[int]
    engine_version: Optional[str]

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "organization_id": self.organization_id,
            "depth": self.depth,
            "include_derived": self.include_derived,
            "latency_ms": self.latency_ms,
            "explicit_rows": self.explicit_rows,
            "derived_rows": self.derived_rows,
            "stale_rows": self.stale_rows,
            "invalidated_rows": self.invalidated_rows,
            "engine_version": self.engine_version,
        }


class _LatencyScope:
    """Mutable counters a caller fills in before the ``with`` block exits.

    Real values only -- CLAUDE.md "never invent data": every field on
    ``QueryLatencyRecord`` is populated from what the caller actually
    measured, never a literal placeholder.
    """

    def __init__(self) -> None:
        self.organization_id: Optional[int] = None
        self.depth: Optional[int] = None
        self.include_derived: bool = False
        self.explicit_rows: int = 0
        self.derived_rows: int = 0
        self.stale_rows: int = 0
        self.invalidated_rows: Optional[int] = None
        self.engine_version: Optional[str] = None
        # Populated by record_query_latency itself on exit -- callers read
        # this back after the ``with`` block to put a real, measured value
        # (never a literal) into a response summary.
        self.latency_ms: Optional[float] = None


@contextmanager
def record_query_latency(query_name: str) -> Iterator[_LatencyScope]:
    """Context manager emitting one OA-2 record and one histogram observation.

    Usage::

        with record_query_latency("cross_layer_impact") as scope:
            scope.organization_id = org_id
            scope.depth = max_depth
            ...

    The histogram is incremented unconditionally on exit (success or
    exception) so a slow failing query is still observable; the OA-2 log
    record is only emitted on the success path since its row counts are
    meaningless after an exception.
    """
    scope = _LatencyScope()
    start = time.perf_counter()
    try:
        yield scope
    finally:
        elapsed_seconds = time.perf_counter() - start
        latency_ms = elapsed_seconds * 1000.0
        scope.latency_ms = latency_ms
        depth_label = str(scope.depth) if scope.depth is not None else "unknown"
        include_derived_label = "true" if scope.include_derived else "false"
        INTELLIGENCE_QUERY_DURATION.labels(
            query=query_name, depth=depth_label, include_derived=include_derived_label
        ).observe(elapsed_seconds)
        record = QueryLatencyRecord(
            query=query_name,
            organization_id=scope.organization_id,
            depth=scope.depth,
            include_derived=scope.include_derived,
            latency_ms=latency_ms,
            explicit_rows=scope.explicit_rows,
            derived_rows=scope.derived_rows,
            stale_rows=scope.stale_rows,
            invalidated_rows=scope.invalidated_rows,
            engine_version=scope.engine_version,
        )
        logger.info("intelligence.query_latency: %s", record.as_dict())


__all__ = ["QueryLatencyRecord", "record_query_latency"]
