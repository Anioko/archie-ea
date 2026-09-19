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

from app.modules.intelligence.services.reason_codes import validate_reason_code
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


_INSUFFICIENT_SAMPLES_REASON = validate_reason_code("insufficient_samples_for_p95")
_ABOVE_HIGHEST_BUCKET_REASON = validate_reason_code("p95_above_highest_bucket")
_MIN_SAMPLES_FOR_P95 = 100


def read_p95_bucket_edge(
    *, query: str, depth: str, include_derived: str, min_samples: int = _MIN_SAMPLES_FOR_P95
) -> dict:
    """T-005 (D1/D3/D4): read p95 off ``INTELLIGENCE_QUERY_DURATION`` as a
    bucket-edge read for one PINNED label combination -- never widened, never
    aggregated across label values (D1/D2).

    ``histogram_quantile`` is a PromQL function; there is no Prometheus
    server in this deployment (NFR-6 forbids adding one). In-process,
    ``prometheus_client`` exposes only cumulative bucket counters, so this
    walks the histogram's own declared boundaries and reports the ``le`` of
    the first bucket whose cumulative count reaches 95% of the series'
    total -- no interpolation, no averaging, no raw-sample retention, no
    arithmetic beyond the comparison (D3). The reported value is always one
    of the histogram's declared boundaries, i.e. the metric's own value, not
    a derived statistic.

    Uses the public ``Histogram.collect()`` API (not private ``_buckets``/
    ``_upper_bounds`` attributes) so this stays correct across
    ``prometheus_client`` versions.

    Returns a dict with ``latency_seconds`` (``None`` unless a real bucket
    boundary was found), ``sample_count`` (the pinned series' total,
    ``0`` when the series has never been observed), and ``reason`` (a DE-14
    member, or ``None`` on a real reading).
    """
    from app.services.prometheus_metrics import INTELLIGENCE_QUERY_DURATION

    family = INTELLIGENCE_QUERY_DURATION.collect()[0]
    target_labels = {"query": query, "depth": depth, "include_derived": include_derived}

    bucket_samples = []
    total = None
    for sample in family.samples:
        if sample.name.endswith("_bucket") and all(
            sample.labels.get(k) == v for k, v in target_labels.items()
        ):
            bucket_samples.append((sample.labels.get("le"), sample.value))
        elif sample.name.endswith("_count") and all(
            sample.labels.get(k) == v for k, v in target_labels.items()
        ):
            total = sample.value

    sample_count = int(total) if total is not None else 0

    if sample_count < min_samples:
        return {
            "latency_seconds": None,
            "sample_count": sample_count,
            "reason": _INSUFFICIENT_SAMPLES_REASON,
        }

    threshold = 0.95 * sample_count
    # Sort buckets by their declared upper bound, +Inf last -- cumulative
    # counts are already non-decreasing across this order.
    def _sort_key(item):
        le = item[0]
        return float("inf") if le == "+Inf" else float(le)

    for le, cumulative_count in sorted(bucket_samples, key=_sort_key):
        if le == "+Inf":
            continue
        if cumulative_count >= threshold:
            return {
                "latency_seconds": float(le),
                "sample_count": sample_count,
                "reason": None,
            }

    # The 95th percentile falls in the +Inf overflow bucket: no declared
    # boundary is an honest answer (D3). Report the highest DECLARED bucket
    # as the exceeded threshold, never as if it were the measured value.
    declared = [float(le) for le, _ in bucket_samples if le != "+Inf"]
    highest_declared = max(declared) if declared else None
    return {
        "latency_seconds": None,
        "sample_count": sample_count,
        "reason": _ABOVE_HIGHEST_BUCKET_REASON,
        "p95_exceeds_seconds": highest_declared,
    }


__all__ = [
    "QueryLatencyRecord",
    "read_p95_bucket_edge",
    "record_query_latency",
]
