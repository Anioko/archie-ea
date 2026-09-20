"""DE-3/OA-2: structured operational record for invalidation and recompute.

**New module.** ``record_query_latency`` — the function the T-003 brief's
OA-2 deliverable names as something to extend — does not exist anywhere in
this repository (verified by full-tree grep; see
``docs/buckets/t003-derived-fact-store/tasks/00-verification-notes-and-sr1.md``).
There is therefore no existing OA-2 structured record to extend. This module
is what that deliverable actually is: a new, minimal structured-logging
helper following the same "measurement, not a log line" shape used elsewhere
in this task (``app/jobs/tenant_safe_job.py``'s ``JobRun``,
``app/jobs/capability_projection_job.py``'s ``CapabilityProjectionRun``) —
a dataclass with an ``as_dict()``, logged at INFO, not a bare log string.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("archie.intelligence.oa2")


@dataclass(frozen=True)
class InvalidationRecord:
    """One batched-invalidation event (DE-3, FR-4, OA-2).

    ``organization_id`` is ``Optional``: a bulk write observed with no tenant
    context at all (e.g. a CLI command) marks every tenant's store, so the
    record itself carries no single organization. ``invalidated_rows`` is
    ``Optional`` for the same reason on the count side: the database driver
    reporting an unknown/negative rowcount is a genuinely different fact from
    "marked zero rows" and must not be coerced into it (round-1 refuter
    finding D9) -- CLAUDE.md "never invent data" applies to this record too.
    """

    organization_id: Optional[int]
    invalidated_rows: Optional[int]
    recorded_at: _dt.datetime

    def as_dict(self) -> dict:
        return {
            "organization_id": self.organization_id,
            "invalidated_rows": self.invalidated_rows,
            "recorded_at": self.recorded_at.isoformat(),
        }


def record_invalidation(
    *, organization_id: Optional[int], invalidated_rows: Optional[int]
) -> InvalidationRecord:
    """Emit the OA-2 structured record for one batched ``UPDATE``.

    Called by ``invalidation.py`` immediately after the single ``UPDATE`` it
    issues per flush, with the real ``rowcount`` — never a literal, per
    CLAUDE.md "never invent data". ``invalidated_rows=None`` records an
    explicit unknown count rather than silently reporting zero.
    """
    record = InvalidationRecord(
        organization_id=organization_id,
        invalidated_rows=invalidated_rows,
        recorded_at=_dt.datetime.utcnow(),
    )
    logger.info("derived_facts.invalidation: %s", record.as_dict())
    return record


@dataclass(frozen=True)
class ShapeBTriggerRecord:
    """T-005 (D11, ADR-009): a dated, logged Shape-B trigger event.

    Fired when the NFR-5 measurement point's p95 breaches its
    ``threshold_seconds`` (2.0s). This is exactly the pattern
    ``InvalidationRecord`` above and ``latency_probe.QueryLatencyRecord``
    already establish -- a frozen dataclass with ``as_dict()``, logged
    structurally, not a bare log string. It is deliberately NOT a new
    workflow, queue entry, build/work item or state change: it opens a
    decision for a human, it does not start work, and it does not reuse
    ``intelligence_derivation_runs`` -- that store answers a different
    question (D11).
    """

    measured_p95_seconds: float
    threshold_seconds: float
    sample_count: int
    query: str
    depth: str
    include_derived: str
    recorded_at: _dt.datetime

    def as_dict(self) -> dict:
        return {
            "measured_p95_seconds": self.measured_p95_seconds,
            "threshold_seconds": self.threshold_seconds,
            "sample_count": self.sample_count,
            "query": self.query,
            "depth": self.depth,
            "include_derived": self.include_derived,
            "recorded_at": self.recorded_at.isoformat(),
        }


def record_shape_b_trigger(
    *,
    measured_p95_seconds: float,
    threshold_seconds: float,
    sample_count: int,
    query: str,
    depth: str,
    include_derived: str,
) -> ShapeBTriggerRecord:
    """Emit the ADR-009 Shape-B trigger event at WARNING (it is a breach,
    unlike the INFO-level records above), and return the record so the
    caller can echo it into the yield endpoint's response body."""
    record = ShapeBTriggerRecord(
        measured_p95_seconds=measured_p95_seconds,
        threshold_seconds=threshold_seconds,
        sample_count=sample_count,
        query=query,
        depth=depth,
        include_derived=include_derived,
        recorded_at=_dt.datetime.utcnow(),
    )
    logger.warning("intelligence.shape_b_trigger: %s", record.as_dict())
    return record


__all__ = [
    "InvalidationRecord",
    "ShapeBTriggerRecord",
    "record_invalidation",
    "record_shape_b_trigger",
]
