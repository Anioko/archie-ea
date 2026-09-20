"""T-002: recurring scheduled run of the existing capability projection.

WHY THIS FILE EXISTS
=====================
``app/commands/project_capabilities.py`` already projects ``business_capability``
into ``unified_capabilities`` (source of the maturity authority pair
``current_maturity_level`` / ``target_maturity_level``), and PR #23 wired it into
a one-shot deploy-time run plus write-time ORM sync listeners on
``BusinessCapability``. Neither covers the three raw-SQL maturity writers in
``app/modules/capabilities/routes/maturity_routes.py`` (~:177-199, :269-273,
:313-318) — a raw ``UPDATE`` never fires an ORM event, so those writes are
invisible to the listeners PR #23 added. This module closes that gap by putting
the *existing* producer on a schedule.

This is deliberately NOT run through ``app.jobs.tenant_safe_job.run_for_each_tenant``:
``_protect_reference_capability_writes`` (``app/models/unified_capability.py``)
raises ``PermissionError`` for a ``UnifiedCapability`` row whose
``organization_id`` differs from ``g.current_org_id``, and the projection is
explicitly all-tenant in one pass. Setting a tenant context per org would refuse
on the first foreign row. Instead this uses ``job_lock`` alone — no tenant
context is ever set, matching the module docstring in
``project_capabilities.py`` that the command "can only run outside a request
context."

Do not modify ``app/commands/project_capabilities.py`` from this module. This
file only imports and calls its existing public callable.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.extensions import db
from app.jobs.tenant_safe_job import JobLockUnavailable, job_lock

logger = logging.getLogger(__name__)

JOB_NAME = "capability_projection"

# Module-level record of the last successful run, read by the staleness signal.
# Deliberately in-process state, not a new column/table/cache (CLAUDE.md: no
# new store for this task) — it resets on process restart, which is
# acceptable because a restart is followed by the interval firing again well
# inside OA-3's one-cycle objective.
_last_success_at: Optional[_dt.datetime] = None


@dataclass
class CapabilityProjectionRun:
    """Outcome of one invocation of the scheduled job — a measurement, not a log line."""

    job_name: str
    started_at: _dt.datetime
    finished_at: _dt.datetime | None = None
    status: str = "pending"  # "ok" | "failed" | "skipped_locked"
    payload: dict = field(default_factory=dict)
    error: str | None = None

    @property
    def duration_ms(self) -> int:
        if self.finished_at is None:
            return 0
        return int((self.finished_at - self.started_at).total_seconds() * 1000)

    def as_dict(self) -> dict:
        return {
            "job_name": self.job_name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            # Staleness signal (deliverable 4): reused straight from the
            # projection's own plan measurement rather than a second query.
            "stale_row_count": (self.payload or {}).get("plan", {}).get("to_update"),
            "last_successful_run_at": (
                _last_success_at.isoformat() if _last_success_at else None
            ),
            "writes": (self.payload or {}).get("writes"),
        }


def last_successful_run_at() -> Optional[_dt.datetime]:
    """The timestamp of the last successful projection run, for observability."""
    return _last_success_at


def run_capability_projection_job() -> CapabilityProjectionRun:
    """Run the existing projection once, inside a cross-process advisory lock.

    Sets no tenant context. Must be called inside an ``app.app_context()`` (the
    caller — the scheduler registration or a test — is responsible for that;
    this function does not open one itself so tests can assert on ``g`` from
    the same context).
    """
    global _last_success_at

    from app.commands.project_capabilities import ProjectionBlocked, execute_projection_with_audit

    run = CapabilityProjectionRun(job_name=JOB_NAME, started_at=_dt.datetime.utcnow())

    try:
        with job_lock(JOB_NAME, required=True):
            payload = execute_projection_with_audit(
                db.engine, report_path=None, apply=True
            )
            run.payload = payload
            run.status = "ok"
            _last_success_at = _dt.datetime.utcnow()
            logger.info(
                "capability_projection_job: ran ok writes=%s stale_before_run=%s",
                payload.get("writes"),
                payload.get("plan", {}).get("to_update"),
            )
    except JobLockUnavailable:
        run.status = "skipped_locked"
        logger.info("capability_projection_job: skipped — advisory lock held elsewhere")
    except ProjectionBlocked as exc:
        run.status = "failed"
        run.error = str(exc)
        logger.error("capability_projection_job: blocked: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive; never report as success
        run.status = "failed"
        run.error = repr(exc)
        logger.exception("capability_projection_job: unexpected failure")
    finally:
        run.finished_at = _dt.datetime.utcnow()

    return run
